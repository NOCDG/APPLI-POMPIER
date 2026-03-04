"""
Service de récupération et synchronisation du CSV export ST-LO via Gmail IMAP.

Flux :
  1. Connexion Gmail IMAP → téléchargement pièce jointe CSV
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
import unicodedata
from datetime import date as DateType, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.db.models import Affectation, DispoAgatt, Garde, Personnel

logger = logging.getLogger(__name__)

IMPORT_TYPES = {"DN", "DJ", "DAN", "DAJ", "G24"}


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
            reader = csv.DictReader(io.StringIO(text), delimiter=";")
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

    logger.info("[gmail_fetcher] Connexion IMAP Gmail…")

    mail = imaplib.IMAP4_SSL("imap.gmail.com")
    try:
        mail.login(settings.GMAIL_IMAP_USER, settings.GMAIL_IMAP_PASSWORD)
        mail.select("inbox")

        search_criteria = (
            f'FROM "{settings.GMAIL_CSV_SENDER}" '
            f'SUBJECT "{settings.GMAIL_CSV_SUBJECT}"'
        )
        status, data = mail.search(None, search_criteria)
        if status != "OK" or not data[0]:
            raise FileNotFoundError(
                f"Aucun email trouvé de {settings.GMAIL_CSV_SENDER} "
                f"avec le sujet « {settings.GMAIL_CSV_SUBJECT} »"
            )

        latest_id = data[0].split()[-1]
        status, msg_data = mail.fetch(latest_id, "(RFC822)")
        if status != "OK":
            raise RuntimeError("Impossible de récupérer l'email")

        msg = email.message_from_bytes(msg_data[0][1])

        csv_content: bytes | None = None
        for part in msg.walk():
            if "attachment" not in part.get("Content-Disposition", ""):
                continue
            filename = part.get_filename() or ""
            if filename.lower().endswith(".csv"):
                csv_content = part.get_payload(decode=True)
                break

        if csv_content is None:
            raise FileNotFoundError("Aucune pièce jointe CSV dans l'email")

    finally:
        try:
            mail.logout()
        except Exception:
            pass

    # Parse + sync BDD
    csv_entries = _parse_csv_bytes(csv_content)
    if not csv_entries:
        raise ValueError("CSV vide ou aucune entrée utile (DN/DJ/DAN/DAJ/G24)")

    with SessionLocal() as db:
        inserted, deleted, aff_removed = _sync_to_db(db, csv_entries)

    msg_ok = (
        f"Sync OK — {len(csv_entries)} entrées CSV, "
        f"+{inserted} insérées, -{deleted} supprimées"
        + (f", {aff_removed} affectation(s) G24 retirée(s)" if aff_removed else "")
    )
    logger.info(f"[gmail_fetcher] {msg_ok}")
    return msg_ok
