"""
Service de récupération et synchronisation du CSV export ST-LO via Gmail IMAP.

Flux :
  1. Connexion Gmail IMAP → téléchargement pièce jointe CSV
     (mail envoyé directement OU transféré depuis une autre boîte)
  2. Parse du CSV (uniquement DN, DJ, DAN, DAJ, G24)
  3. Sync BDD :
     - INSERT les entrées présentes dans CSV mais absentes de la BDD
     - DELETE les entrées présentes en BDD mais absentes du CSV
       (= quelqu'un a supprimé sa dispo dans Agatt)
"""
import csv
import email
import imaplib
import io
import logging
import re
import unicodedata
from datetime import date as DateType, datetime
from email.header import decode_header, make_header
from email.message import Message

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.db.models import Affectation, DispoAgatt, Garde, Personnel

logger = logging.getLogger(__name__)

IMPORT_TYPES = {"DN", "DJ", "DAN", "DAJ", "G24"}

# Séparateurs CSV possibles, testés sur la ligne d'en-tête
_CSV_DELIMITERS = (";", ",", "\t", "|")

# Préfixes ajoutés par les clients mail lors d'un transfert (TR:, FW:, Fwd:…)
_FORWARD_PREFIX_RE = re.compile(r"^(?:\s*(?:tr|fw|fwd|re|rép|rep)\s*:\s*)+", re.IGNORECASE)

# Nombre de messages récents inspectés par dossier
_MAX_CANDIDATES = 30

# Repli sur le sujet : nombre minimum de mots communs entre le sujet attendu
# et celui du message. Couvre les sujets tronqués ou reformulés par le client
# mail lors d'un transfert (« Export_Agatt_base_ST-LO » → « Export_base_ST-LO »).
_MIN_SUBJECT_TOKENS = 2


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _normalize(s: str) -> str:
    """Supprime les accents et met en majuscules."""
    return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().upper().strip()


def _parse_csv_date(raw: str) -> str | None:
    """
    Convertit la date du CSV en ISO YYYY-MM-DD.
    Formats acceptés :
      - "2026/04/25 00:00:00"  → "2026-04-25"
      - "2026/04/25"           → "2026-04-25"
      - "25/04/2026"           → "2026-04-25"
    Retourne None si non parsable.
    """
    raw = raw.strip().split(" ")[0]
    if "/" not in raw:
        return raw if len(raw) == 10 else None
    parts = raw.split("/")
    if len(parts) != 3:
        return None
    if len(parts[0]) == 4:
        return f"{parts[0]}-{parts[1]}-{parts[2]}"
    return f"{parts[2]}-{parts[1]}-{parts[0]}"


def _detect_delimiter(header_line: str) -> str:
    """
    Devine le séparateur d'après la ligne d'en-tête : celui qui produit le
    plus de colonnes. L'export a changé de « ; » à « , » sans prévenir, et
    les noms de colonnes ne contiennent aucun de ces caractères.
    """
    return max(_CSV_DELIMITERS, key=lambda d: len(header_line.split(d)))


def _parse_csv_bytes(content: bytes) -> set[tuple[DateType, str, str, str]]:
    """
    Parse le contenu CSV (bytes) et retourne un set de tuples
    (date, nom_norm, prenom_norm, type_occ) pour les types utiles uniquement.
    """
    entries: set[tuple[DateType, str, str, str]] = set()

    encodings = ["utf-8-sig", "utf-8", "latin-1", "cp1252"]
    for enc in encodings:
        try:
            text = content.decode(enc)
            delimiter = _detect_delimiter(text.splitlines()[0] if text else "")
            reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
            for row in reader:
                type_occ = (row.get("Type Occupation") or "").strip()
                if type_occ not in IMPORT_TYPES:
                    continue
                raw_date = (row.get("Date Occupation") or "").strip()
                date_iso = _parse_csv_date(raw_date)
                if not date_iso:
                    continue
                try:
                    d = DateType.fromisoformat(date_iso)
                except ValueError:
                    continue
                nom = _normalize((row.get("Nom") or "").strip())
                prenom = _normalize((row.get("Prénom") or "").strip())
                if nom:
                    entries.add((d, nom, prenom, type_occ))
            return entries  # décodage réussi
        except UnicodeDecodeError:
            continue

    logger.warning("[gmail_fetcher] Impossible de décoder le CSV (encodage inconnu)")
    return entries


def _remove_affectations_for_g24(
    db: Session, removed_g24: list[tuple[DateType, str, str]]
) -> int:
    """
    Pour chaque G24 supprimé (date, nom_norm, prenom_norm),
    supprime les affectations sur les gardes non validées de cette date.
    Retourne le nombre d'affectations supprimées.
    """
    if not removed_g24:
        return 0

    all_persons: list[Personnel] = db.scalars(
        select(Personnel).where(Personnel.is_active == True)
    ).all()

    total_removed = 0
    for (d, nom_norm, prenom_norm) in removed_g24:
        # Trouve le personnel correspondant
        matching = [
            p for p in all_persons
            if _normalize(p.nom) == nom_norm and _normalize(p.prenom) == prenom_norm
        ]
        if not matching:
            continue
        person = matching[0]

        # Gardes non validées pour cette date
        gardes: list[Garde] = db.scalars(
            select(Garde).where(
                Garde.date == d,
                Garde.validated == False,
            )
        ).all()

        for garde in gardes:
            affs: list[Affectation] = db.scalars(
                select(Affectation).where(
                    Affectation.garde_id == garde.id,
                    Affectation.personnel_id == person.id,
                )
            ).all()
            for aff in affs:
                db.delete(aff)
                total_removed += 1
                logger.info(
                    f"[gmail_fetcher] G24 retiré → suppression affectation "
                    f"garde {garde.id} ({d} {garde.slot}) pour {person.prenom} {person.nom}"
                )

    return total_removed


def _sync_to_db(db: Session, csv_entries: set[tuple[DateType, str, str, str]]) -> tuple[int, int, int]:
    """
    Synchronise les entrées CSV avec la BDD.
    Retourne (nb_insérés, nb_supprimés, nb_affectations_retirées).
    """
    now = datetime.utcnow()

    existing: list[DispoAgatt] = db.scalars(select(DispoAgatt)).all()
    existing_set = {(e.date, e.nom, e.prenom, e.type_occ): e for e in existing}

    to_delete = [obj for key, obj in existing_set.items() if key not in csv_entries]
    to_insert = [key for key in csv_entries if key not in existing_set]

    # G24 supprimés → retirer affectations sur gardes non validées
    g24_removed = [(obj.date, obj.nom, obj.prenom) for obj in to_delete if obj.type_occ == "G24"]
    aff_removed = _remove_affectations_for_g24(db, g24_removed)

    for obj in to_delete:
        db.delete(obj)

    for (d, nom, prenom, type_occ) in to_insert:
        db.add(DispoAgatt(
            date=d, nom=nom, prenom=prenom, type_occ=type_occ, imported_at=now,
        ))

    db.commit()
    return len(to_insert), len(to_delete), aff_removed


# ──────────────────────────────────────────────
# Récupération du mail (IMAP)
# ──────────────────────────────────────────────

def _decode(raw: str | None) -> str:
    """Décode un en-tête MIME (=?utf-8?B?...?=) en texte lisible."""
    if not raw:
        return ""
    try:
        return str(make_header(decode_header(raw)))
    except Exception:
        return raw


def _strip_forward_prefixes(subject: str) -> str:
    """Retire les préfixes « TR: », « FW: », « Fwd: »… d'un sujet (même répétés)."""
    return _FORWARD_PREFIX_RE.sub("", subject).strip()


def _subject_tokens(subject: str) -> set[str]:
    """Découpe un sujet en mots significatifs (≥ 3 caractères, minuscules)."""
    return {
        t for t in re.split(r"[^0-9a-zA-Z\-]+", _strip_forward_prefixes(subject).lower())
        if len(t) >= 3
    }


def _subject_matches_loosely(subject: str, expected_tokens: set[str]) -> bool:
    """
    Vrai si le sujet partage assez de mots avec le sujet attendu.

    Sert de repli quand la recherche IMAP exacte ne donne rien : un transfert
    peut tronquer ou reformuler le sujet d'origine.
    """
    if not expected_tokens:
        return True
    return len(_subject_tokens(subject) & expected_tokens) >= _MIN_SUBJECT_TOKENS


def _find_csv_attachment(msg: Message) -> bytes | None:
    """
    Cherche une pièce jointe .csv dans le message, y compris à l'intérieur
    d'un message transféré en pièce jointe (message/rfc822).
    """
    for part in msg.walk():
        if part.get_content_maintype() == "multipart":
            continue

        filename = _decode(part.get_filename())
        if filename.lower().endswith(".csv"):
            payload = part.get_payload(decode=True)
            if payload:
                return payload

        # Transfert « en pièce jointe » : on descend dans le message imbriqué
        if part.get_content_type() == "message/rfc822":
            for sub in part.get_payload():
                if isinstance(sub, Message):
                    found = _find_csv_attachment(sub)
                    if found:
                        return found

    return None


def _matches_sender(msg: Message, senders: list[str]) -> bool:
    """
    Vrai si le message provient d'un des expéditeurs autorisés.

    Couvre les 3 cas :
      - envoi direct           → From = expéditeur d'origine
      - redirection Exchange   → From d'origine conservé
      - transfert (« TR: »)    → From = la personne qui transfère ; l'adresse
                                 d'origine reste citée dans les en-têtes de
                                 transfert ou dans le bloc « De : … » du corps
    """
    if not senders:
        return True

    headers = " ".join(
        _decode(msg.get(h))
        for h in ("From", "Sender", "Reply-To", "Return-Path", "X-Forwarded-For", "Resent-From")
    ).lower()

    if any(sender.lower() in headers for sender in senders):
        return True

    # Transfert : l'adresse d'origine apparaît dans le corps du message
    for part in msg.walk():
        if part.get_content_maintype() != "text":
            continue
        payload = part.get_payload(decode=True)
        if not payload:
            continue
        try:
            body = payload.decode(part.get_content_charset() or "utf-8", errors="ignore").lower()
        except LookupError:
            body = payload.decode("utf-8", errors="ignore").lower()
        if any(sender.lower() in body for sender in senders):
            return True

    return False


def _fetch_csv_bytes() -> tuple[bytes, str, str]:
    """
    Parcourt les dossiers IMAP configurés, du message le plus récent au plus
    ancien, et retourne la première pièce jointe CSV trouvée dans un message
    dont le sujet et l'expéditeur correspondent.

    Retourne (contenu_csv, dossier, uid) — le dossier et l'UID servent à
    marquer le message comme lu une fois la synchro BDD réussie.
    """
    senders = settings.gmail_csv_senders
    subject = _strip_forward_prefixes(settings.GMAIL_CSV_SUBJECT or "")
    expected_tokens = _subject_tokens(subject)

    stats = {"inspected": 0, "rejected_sender": 0, "rejected_subject": 0}
    seen_subjects: list[str] = []

    def scan(mail: imaplib.IMAP4_SSL, folder: str, uids: list[bytes], loose: bool):
        """Inspecte les messages du plus récent au plus ancien."""
        for raw_uid in reversed(uids):
            uid = raw_uid.decode()
            status, msg_data = mail.uid("FETCH", uid, "(BODY.PEEK[])")
            if status != "OK" or not msg_data or not msg_data[0]:
                continue

            msg = email.message_from_bytes(msg_data[0][1])
            msg_subject = _decode(msg.get("Subject"))
            stats["inspected"] += 1
            if len(seen_subjects) < 10:
                seen_subjects.append(msg_subject)

            if not _matches_sender(msg, senders):
                stats["rejected_sender"] += 1
                continue

            # En repli, le sujet n'a pas été filtré par le serveur : on vérifie
            # qu'il ressemble bien à celui attendu.
            if loose and not _subject_matches_loosely(msg_subject, expected_tokens):
                stats["rejected_subject"] += 1
                continue

            csv_content = _find_csv_attachment(msg)
            if csv_content is None:
                continue

            logger.info(
                f"[gmail_fetcher] CSV trouvé — dossier « {folder} », uid {uid}, "
                f"de « {_decode(msg.get('From'))} », sujet « {msg_subject} »"
                + (" (correspondance approchée sur le sujet)" if loose else "")
            )
            return csv_content, folder, uid
        return None

    logger.info("[gmail_fetcher] Connexion IMAP Gmail…")
    mail = imaplib.IMAP4_SSL("imap.gmail.com")
    try:
        mail.login(settings.GMAIL_IMAP_USER, settings.GMAIL_IMAP_PASSWORD)

        # Passe 1 : sujet exact (sous-chaîne) côté serveur — le cas nominal.
        # Passe 2 : repli sur les derniers messages du dossier, filtrés en
        # Python. Rattrape les transferts dont le sujet a été tronqué ou
        # reformulé, cas qu'une recherche IMAP par sous-chaîne ne peut pas voir.
        for loose in (False, True):
            for folder in settings.gmail_imap_folders:
                # readonly : la recherche ne doit rien marquer comme lu, seul un
                # traitement complet le fera (voir _mark_seen).
                status, _ = mail.select(f'"{folder}"', readonly=True)
                if status != "OK":
                    if not loose:
                        logger.info(f"[gmail_fetcher] Dossier « {folder} » introuvable — ignoré")
                    continue

                # On travaille en UID : stable d'une session IMAP à l'autre.
                if loose:
                    status, data = mail.uid("SEARCH", None, "ALL")
                else:
                    status, data = mail.uid("SEARCH", None, "SUBJECT", f'"{subject}"')
                if status != "OK" or not data or not data[0]:
                    continue

                found = scan(mail, folder, data[0].split()[-_MAX_CANDIDATES:], loose)
                if found:
                    return found

            if not loose:
                logger.info(
                    "[gmail_fetcher] Sujet exact introuvable — repli sur "
                    "correspondance approchée"
                )

        raise FileNotFoundError(
            f"Aucun email avec pièce jointe CSV trouvé "
            f"(sujet « {subject} », expéditeurs acceptés : {', '.join(senders) or 'tous'}, "
            f"dossiers : {', '.join(settings.gmail_imap_folders)}). "
            f"{stats['inspected']} message(s) inspecté(s), "
            f"{stats['rejected_sender']} écarté(s) sur l'expéditeur, "
            f"{stats['rejected_subject']} sur le sujet. "
            f"Derniers sujets vus : {' | '.join(seen_subjects) or 'aucun'}"
        )
    finally:
        try:
            mail.logout()
        except Exception:
            pass


def _mark_seen(folder: str, uid: str) -> None:
    """
    Marque le message comme lu, une fois la synchro BDD terminée avec succès.

    Un mail resté « non lu » dans la boîte signale donc un traitement qui n'a
    pas abouti. L'échec du marquage n'invalide pas la synchro : on se contente
    de le tracer.
    """
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        try:
            mail.login(settings.GMAIL_IMAP_USER, settings.GMAIL_IMAP_PASSWORD)
            status, _ = mail.select(f'"{folder}"')  # écriture
            if status != "OK":
                logger.warning(f"[gmail_fetcher] Marquage lu impossible : dossier « {folder} » inaccessible")
                return
            status, _ = mail.uid("STORE", uid, "+FLAGS", "(\\Seen)")
            if status != "OK":
                logger.warning(f"[gmail_fetcher] Marquage lu refusé par le serveur (uid {uid})")
            else:
                logger.info(f"[gmail_fetcher] Mail marqué comme lu (dossier « {folder} », uid {uid})")
        finally:
            try:
                mail.logout()
            except Exception:
                pass
    except Exception as e:
        logger.warning(f"[gmail_fetcher] Marquage lu échoué (uid {uid}) : {e}")


# ──────────────────────────────────────────────
# Point d'entrée principal
# ──────────────────────────────────────────────

def fetch_csv_from_gmail() -> str:
    """
    Se connecte à Gmail via IMAP, récupère la pièce jointe CSV
    et synchronise la BDD. Retourne un message de statut.
    """
    if not all([
        settings.GMAIL_IMAP_USER,
        settings.GMAIL_IMAP_PASSWORD,
        settings.GMAIL_CSV_SENDER,
        settings.GMAIL_CSV_SUBJECT,
    ]):
        raise ValueError(
            "Configuration IMAP incomplète "
            "(GMAIL_IMAP_USER / GMAIL_IMAP_PASSWORD / GMAIL_CSV_SENDER / GMAIL_CSV_SUBJECT)"
        )

    csv_content, folder, uid = _fetch_csv_bytes()

    # Parse + sync BDD
    csv_entries = _parse_csv_bytes(csv_content)
    if not csv_entries:
        raise ValueError("CSV vide ou aucune entrée utile (DN/DJ/DAN/DAJ/G24)")

    with SessionLocal() as db:
        inserted, deleted, aff_removed = _sync_to_db(db, csv_entries)

    # Traitement abouti → le mail passe en « lu » : un mail non lu dans la
    # boîte signale une récupération qui n'a pas fonctionné.
    _mark_seen(folder, uid)

    msg_ok = (
        f"Sync OK — {len(csv_entries)} entrées CSV, "
        f"+{inserted} insérées, -{deleted} supprimées"
        + (f", {aff_removed} affectation(s) G24 retirée(s)" if aff_removed else "")
    )
    logger.info(f"[gmail_fetcher] {msg_ok}")
    return msg_ok
