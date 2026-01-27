from __future__ import annotations

from typing import List
from sqlalchemy.orm import Session

from app.core.mailer import build_validation_html, send_mail

# IMPORTANT: adapte ces imports selon ton projet
from app.db.session import SessionLocal  # souvent SessionLocal / get_sessionmaker

# IMPORTANT: adapte selon tes modèles
from app.db.models import User  # et éventuellement Role


FIXED_VALIDATION_RECIPIENT = "operation-st-lo@sdis50.fr"


def _get_officier_emails(db: Session) -> List[str]:
    """
    Retourne les emails des utilisateurs ayant le rôle OFFICIER.
    Cette fonction tente plusieurs schémas courants.
    Adapte la requête au besoin si ton modèle est différent.
    """

    # 1) Cas simple : champ texte "role" dans User (ex: "OFFICIER")
    if hasattr(User, "role"):
        rows = db.query(User.email).filter(User.role == "OFFICIER").all()
        return [r[0] for r in rows if r and r[0]]

    # 2) Cas JSON/ARRAY: champ "roles" (liste de strings) -> dépend du type exact
    # Exemple Postgres ARRAY: User.roles.any("OFFICIER")
    if hasattr(User, "roles"):
        try:
            rows = db.query(User.email).filter(User.roles.any("OFFICIER")).all()  # type: ignore[attr-defined]
            return [r[0] for r in rows if r and r[0]]
        except Exception:
            pass

    # 3) Cas many-to-many User <-> Role via relation "roles"
    # Nécessite un modèle Role avec champ name et une relation User.roles.
    try:
        from app.db.models import Role  # import tardif pour éviter de casser si absent

        rows = (
            db.query(User.email)
            .join(User.roles)  # type: ignore[attr-defined]
            .filter(Role.name == "OFFICIER")
            .all()
        )
        return [r[0] for r in rows if r and r[0]]
    except Exception:
        return []


def send_validation_notification(mois_label: str, equipe_label: str, validateur: str) -> None:
    """
    Ouvre sa propre session DB (robuste pour BackgroundTasks),
    récupère les OFFICIER + ajoute operation-st-lo@sdis50.fr,
    et envoie l’email HTML de validation.
    """
    db = SessionLocal()
    try:
        officier_emails = _get_officier_emails(db)

        recipients = {FIXED_VALIDATION_RECIPIENT}
        recipients.update(e.strip() for e in officier_emails if e and e.strip())

        subject = f"Validation feuille de garde – {mois_label} – {equipe_label}"
        html = build_validation_html(mois_label=mois_label, equipe_label=equipe_label, validateur=validateur)

        # On passe db=db pour lire la config mail en BDD si tu l'utilises (AppSetting)
        send_mail(to=sorted(recipients), subject=subject, html=html, db=db)

    finally:
        db.close()
