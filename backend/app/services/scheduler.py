# app/services/scheduler.py
# Job cron : envoi du récapitulatif mensuel le 25 de chaque mois (gardes du mois suivant)
from datetime import date, datetime

from sqlalchemy import select, extract

from app.db.session import SessionLocal
from app.db.models import Affectation, Equipe, Garde, Personnel, Piquet
from app.core.mailer import send_mail, build_html_monthly_reminder


def _next_month(d: date) -> tuple[int, int]:
    if d.month == 12:
        return d.year + 1, 1
    return d.year, d.month + 1


def send_monthly_reminder() -> None:
    """
    Envoie à chaque agent affecté le récapitulatif de ses gardes du mois suivant.
    Appelé automatiquement le 25 de chaque mois à 08h00.
    """
    today = date.today()
    ny, nm = _next_month(today)
    mois_label = datetime(ny, nm, 1).strftime("%B %Y").capitalize()

    print(f"[CRON] Envoi rappel mensuel pour {mois_label}…")

    with SessionLocal() as db:
        # Toutes les affectations du mois suivant
        affs = db.scalars(
            select(Affectation)
            .join(Garde, Garde.id == Affectation.garde_id)
            .where(
                extract("year", Garde.date) == ny,
                extract("month", Garde.date) == nm,
            )
        ).all()

        if not affs:
            print(f"[CRON] Aucune affectation pour {mois_label}, aucun mail envoyé.")
            return

        # Préchargement des entités liées
        garde_ids = {a.garde_id for a in affs}
        piquet_ids = {a.piquet_id for a in affs}

        gardes = {g.id: g for g in db.scalars(select(Garde).where(Garde.id.in_(garde_ids))).all()}
        piquets = {p.id: p for p in db.scalars(select(Piquet).where(Piquet.id.in_(piquet_ids))).all()}

        equipe_ids = {g.equipe_id for g in gardes.values() if g.equipe_id}
        equipes = {e.id: e for e in db.scalars(select(Equipe).where(Equipe.id.in_(equipe_ids))).all()}

        # Grouper par personnel
        pers_affs: dict[int, list] = {}
        for a in affs:
            pers_affs.setdefault(a.personnel_id, []).append(a)

        personnels = db.scalars(
            select(Personnel).where(
                Personnel.id.in_(pers_affs.keys()),
                Personnel.is_active.is_(True),
                Personnel.email.is_not(None),
            )
        ).all()

        sent, errors = 0, 0
        for p in personnels:
            if not p.email:
                continue

            rows: list[tuple[str, str, str, str]] = []
            for a in sorted(
                pers_affs[p.id],
                key=lambda x: (gardes[x.garde_id].date, gardes[x.garde_id].slot.value),
            ):
                g = gardes.get(a.garde_id)
                pq = piquets.get(a.piquet_id)
                if not g or not pq:
                    continue
                eq = equipes.get(g.equipe_id) if g.equipe_id else None
                equipe_label = (eq.code or eq.libelle) if eq else "—"
                rows.append((
                    g.date.strftime("%d/%m/%Y"),
                    g.slot.value,
                    equipe_label,
                    pq.libelle or pq.code,
                ))

            if not rows:
                continue

            fullname = f"{p.prenom} {p.nom}".strip()
            html = build_html_monthly_reminder(fullname, mois_label, rows)
            subject = f"Vos gardes – {mois_label}"
            try:
                send_mail(p.email, subject, html, db=db)
                sent += 1
            except Exception as e:
                print(f"[CRON] ⚠️ Erreur envoi à {p.email}: {e}")
                errors += 1

    print(f"[CRON] Rappel {mois_label} terminé : {sent} envoyés, {errors} erreur(s).")
