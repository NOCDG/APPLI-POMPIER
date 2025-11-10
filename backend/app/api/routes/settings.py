from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api.deps import get_session
from app.schemas.settings import AppSettings
from app.services.settings_store import load_settings, save_settings, patch_settings

router = APIRouter(prefix="/settings", tags=["settings"])

@router.get("", response_model=AppSettings)
def get_settings(db: Session = Depends(get_session)):
    return load_settings(db)

@router.put("", response_model=AppSettings)
def put_settings(payload: dict, db: Session = Depends(get_session)):
    """
    Reçoit un Partial[AppSettings] depuis le front et applique un patch.
    On accepte dict pour ne pas forcer tous les champs.
    """
    try:
        return patch_settings(db, payload)
    except Exception as e:
        raise HTTPException(400, f"Paramètres invalides: {e}")

@router.post("/test_email")
def test_email(payload: dict, db: Session = Depends(get_session)):
    to = (payload or {}).get("to")
    if not to:
        raise HTTPException(400, "Destinataire manquant")
    # Exemple d’appel au service d’e-mail
    from app.services.mailer import Mailer
    settings = load_settings(db)
    mailer = Mailer.from_settings(settings)
    mailer.send_html(
        to=to,
        subject="Test e-mail – Paramètres OK",
        html="<p>✅ Test e-mail depuis Feuille de Garde</p>"
    )
    return {"ok": True}
