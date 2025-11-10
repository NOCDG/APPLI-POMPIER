from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.api.deps import get_session
from app.core.security import verify_password, create_access_token
from app.db.models import Personnel

router = APIRouter(prefix="/auth", tags=["auth"])

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    roles: list[str]

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
