from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, constr
from sqlalchemy.orm import Session
import logging
from app.api.deps import get_session
from app.core.security import verify_password, create_access_token, hash_password, create_reset_token, verify_reset_token
from app.db.models import Personnel

from app.core.email_utils import send_email
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: constr(min_length=8) # type: ignore

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    roles: list[str]

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_session)):
    user = db.query(Personnel).filter_by(email=payload.email).first()
    if not user or not user.hashed_password:
        raise HTTPException(status_code=401, detail="Identifiants invalides")
    if not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Mot de passe incorrect")

    roles = [r.role.value for r in user.roles] or ["AGENT"]
    token = create_access_token(subject=user.email, roles=roles)

    # 🔥 TRÈS IMPORTANT: retourner explicitement un objet/dict
    print("DEBUG login ok")
    return TokenResponse(access_token=token, roles=roles)

@router.post("/forgot-password")
async def forgot_password(
    payload: ForgotPasswordRequest,
    db: Session = Depends(get_session),
):
    """
    Étape 1 : l'utilisateur donne son email.
    On génère un token de reset et on envoie un mail avec un lien.
    Même si l'envoi échoue, on renvoie 200 côté client.
    """
    user = db.query(Personnel).filter_by(email=payload.email).first()

    # Ne pas révéler si l’email existe ou non
    if not user:
        return {"message": "Si cette adresse existe, un email de réinitialisation a été envoyé."}

    token = create_reset_token(payload.email)

    frontend_base = getattr(settings, "FRONTEND_URL", "https://pompier.gandouur.org")
    reset_link = f"{frontend_base}/reset-password?token={token}"

    subject = "Réinitialisation de votre mot de passe - FEUILLE_GARDE"

    text_body = f"""Bonjour,

Vous avez demandé à réinitialiser votre mot de passe.

Cliquez sur ce lien pour choisir un nouveau mot de passe :
{reset_link}

Ce lien est valable 30 minutes.

Si vous n'êtes pas à l'origine de cette demande, vous pouvez ignorer cet email.

Cordialement,
L'application FEUILLE_GARDE
"""

    html_body = f"""
    <p>Bonjour,</p>
    <p>Vous avez demandé à réinitialiser votre mot de passe.</p>
    <p>
        Cliquez sur ce bouton pour choisir un nouveau mot de passe :<br/>
        <a href="{reset_link}" style="display:inline-block;padding:10px 16px;
           background-color:#d32f2f;color:white;text-decoration:none;
           border-radius:4px;margin-top:8px;">
           Réinitialiser mon mot de passe
        </a>
    </p>
    <p>Ou copiez-collez ce lien dans votre navigateur :</p>
    <p><code>{reset_link}</code></p>
    <p>Ce lien est valable 30 minutes.</p>
    <p>Si vous n'êtes pas à l'origine de cette demande, vous pouvez ignorer cet email.</p>
    <p>Cordialement,<br/>L'application FEUILLE_GARDE</p>
    """

    try:
        # on envoie en HTML, les clients mail qui ne lisent pas le HTML
        # pourront quand même cliquer sur le lien en clair
        await send_email(
            subject=subject,
            recipients=[payload.email],
            body=html_body,
            html=True,
        )
    except Exception as e:
        logger.exception("[FORGOT_PASSWORD] Erreur lors de l'envoi du mail: %s", e)

    # Toujours 200 côté front
    return {"message": "Si cette adresse existe, un email de réinitialisation a été envoyé."}

@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_session)):
    """
    Étape 2 : l'utilisateur a cliqué sur le lien, donne son nouveau mot de passe.
    On vérifie le token et on met à jour le mot de passe.
    """
    email = verify_reset_token(payload.token)

    user = db.query(Personnel).filter_by(email=email).first()
    if not user:
        raise HTTPException(status_code=400, detail="Utilisateur introuvable")

    # ⚠️ ADAPTE le nom du champ suivant ta BDD :
    # ex: user.hashed_password, user.password_hash, etc.
    user.hashed_password = hash_password(payload.new_password)

    db.add(user)
    db.commit()

    return {"status": "success", "message": "Mot de passe mis à jour"}