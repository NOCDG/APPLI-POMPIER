# app/api/routes/password_reset.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, constr
from sqlalchemy.orm import Session

from app.api.deps import get_session
from app.db.models import Personnel
from app.core.security import (
    hash_password,
    create_reset_token,
    verify_reset_token,
)

# ⚠️ Adapte ces imports selon ton projet
from app.core.mailer import send_email, build_html_reset_password
from app.core.config import settings      # si tu as un settings.FRONTEND_URL

router = APIRouter(prefix="/auth", tags=["auth"])


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: constr(min_length=8) # type: ignore


@router.post("/forgot-password")
def forgot_password(
    payload: ForgotPasswordRequest,
    db: Session = Depends(get_session),
):
    """
    Étape 1 : l'utilisateur donne son email.
    On génère un token de reset et on envoie un mail avec un lien.
    """
    user = db.query(Personnel).filter_by(email=payload.email).first()

    # Ne pas révéler si le mail existe ou non
    if not user:
        return {"message": "Si cette adresse existe, un email de réinitialisation a été envoyé."}

    token = create_reset_token(payload.email)

    # URL du frontend
    frontend_base = getattr(settings, "FRONTEND_URL", "https://pompier.gandour.org")
    reset_link = f"{frontend_base}/reset-password?token={token}"

    subject = "Réinitialisation de votre mot de passe - FEUILLE_GARDE"

    html_body = build_html_reset_password(reset_link)

    send_email(
        to=payload.email,
        subject=subject,
        text_body=f"Réinitialisez votre mot de passe : {reset_link}",
        html_body=html_body,
    )

    return {"message": "Si cette adresse existe, un email de réinitialisation a été envoyé."}


@router.post("/reset-password")
def reset_password(
    payload: ResetPasswordRequest,
    db: Session = Depends(get_session),
):
    """
    Étape 2 : l'utilisateur a cliqué sur le lien, donne son nouveau mot de passe.
    On vérifie le token et on met à jour le mot de passe.
    """
    email = verify_reset_token(payload.token)

    user = db.query(Personnel).filter_by(email=email).first()
    if not user:
        raise HTTPException(status_code=400, detail="Utilisateur introuvable")

    # ⚠️ ADAPTE le nom du champ suivant ton modèle Personnel
    user.hashed_password = hash_password(payload.new_password)

    db.add(user)
    db.commit()

    return {"status": "success", "message": "Mot de passe mis à jour"}
