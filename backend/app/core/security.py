# app/core/security.py
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Iterable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.api.deps import get_session
from app.db.models import RoleEnum, Garde, Personnel

# ====== CONFIG (mets ça dans tes settings si tu veux) ======
ALGO = "HS256"
JWT_SECRET = "CHANGE_ME_SUPER_SECRET"   # ← mets une vraie clé / variable d'env
JWT_EXPIRE_MINUTES = 60 * 8

# ====== PASSWORD HASHING ======
_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return _pwd_ctx.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_ctx.verify(plain, hashed)

# ====== JWT ======
def create_access_token(subject: str, roles: List[str]) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "roles": roles,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=JWT_EXPIRE_MINUTES)).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=ALGO)

# ====== AUTH DEP (Bearer) ======
_http_bearer = HTTPBearer(auto_error=False)

def _decode_token(token: str) -> dict:
    try:
        # lève JWTError si invalide/expiré
        return jwt.decode(token, JWT_SECRET, algorithms=[ALGO])
    except JWTError as e:
        raise HTTPException(status_code=401, detail="Token invalide ou expiré") from e

def get_current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_http_bearer),
    db: Session = Depends(get_session),
) -> Personnel:
    """
    Dépendance FastAPI qui:
      - lit Authorization: Bearer <token>
      - décode le JWT
      - charge le Personnel via sub==email
      - renvoie l'objet Personnel (ou 401)
    """
    if creds is None or not creds.credentials:
        raise HTTPException(status_code=401, detail="Identification requise")
    payload = _decode_token(creds.credentials)
    email = payload.get("sub")
    if not email:
        raise HTTPException(status_code=401, detail="Token sans sujet")

    user = db.query(Personnel).filter_by(email=email).first()
    if not user:
        raise HTTPException(status_code=401, detail="Utilisateur inconnu")
    if getattr(user, "is_active", True) is False:
        raise HTTPException(status_code=401, detail="Compte inactif")
    return user

def user_roles_set(user: Personnel) -> set[RoleEnum]:
    """Retourne l'ensemble des rôles du user depuis la BDD (fiable)."""
    if not user or not getattr(user, "roles", None):
        return set()
    return {r.role for r in user.roles}

def _normalize_roles_list(raw: Iterable) -> set[str]:
    roles: set[str] = set()
    for r in (raw or []):
        val = None
        # objet avec attribut 'code' (ex: r.code == "ADMIN")
        if hasattr(r, "code"):
            val = getattr(r, "code", None)
        # objet avec attribut 'role' (ex: r.role == RoleEnum.ADMIN ou "ADMIN")
        elif hasattr(r, "role"):
            role_attr = getattr(r, "role", None)
            if role_attr is not None:
                # Enum -> .name ; sinon str()
                val = getattr(role_attr, "name", None) or str(role_attr)
        # Enum directement
        elif hasattr(r, "name"):
            val = getattr(r, "name", None)
        # string
        elif isinstance(r, str):
            val = r
        # fallback
        else:
            try:
                val = str(r)
            except Exception:
                val = None

        if val:
            roles.add(str(val).upper().strip())
    return roles

def user_has_any_role(user: Personnel, *roles: RoleEnum) -> bool:
    """
    True si l'utilisateur possède au moins un des rôles passés.
    On travaille en RoleEnum des deux côtés.
    """
    have = user_roles_set(user)          # set[RoleEnum] depuis la BDD
    wanted = set(roles)                  # set[RoleEnum]
    return bool(have & wanted)


def ensure_admin_off(user: Personnel) -> None:
    """Autorise uniquement ADMIN / OFFICIER, sinon 403."""
    print("[DEBUG ensure_admin_off]", getattr(user, "id", None), getattr(user, "roles", None))
    if not user_has_any_role(user, RoleEnum.ADMIN, RoleEnum.OFFICIER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Réservé aux rôles ADMIN ou OFFICIER",
        )

def ensure_can_validate_for_team(user: Personnel, equipe_id: int | None) -> int | None:
    """
    Valider une FEUILLE (mois) :
      - ADMIN / OFFICIER : autorisés pour toute équipe (equipe_id optionnel).
      - CHEF_EQUIPE / ADJ_CHEF_EQUIPE : autorisés UNIQUEMENT pour leur équipe.
    """
    if user_has_any_role(user, RoleEnum.ADMIN, RoleEnum.OFFICIER):
        return equipe_id

    if user_has_any_role(user, RoleEnum.CHEF_EQUIPE, RoleEnum.ADJ_CHEF_EQUIPE):
        if user.equipe_id is None:
            raise HTTPException(status_code=400, detail="Votre compte n'est associé à aucune équipe")
        if equipe_id is None:
            return user.equipe_id
        if equipe_id != user.equipe_id:
            raise HTTPException(status_code=403, detail="Vous ne pouvez valider que pour votre équipe")
        return equipe_id

    raise HTTPException(status_code=403, detail="Vous n'êtes pas autorisé à valider")

def ensure_can_modify_garde(user: Personnel, garde: Garde) -> None:
    """
    Interdit de modifier une garde validée, sauf ADMIN / OFFICIER.
    À appeler dans les routes d'affectations (create/delete) et autres modifs.
    """
    if getattr(garde, "validated", False) and not user_has_any_role(user, RoleEnum.ADMIN, RoleEnum.OFFICIER):
        # 423 Locked = ressource verrouillée (logique métier)
        raise HTTPException(status_code=423, detail="Garde validée : modification réservée à ADMIN/OFFICIER")

    
def require_roles(*roles: RoleEnum):
    """
    Dépendance FastAPI : bloque si l'utilisateur n'a aucun des rôles donnés.
    Usage : @router.get(..., dependencies=[Depends(require_roles(RoleEnum.ADMIN))])
    """
    def _dep(user: Personnel = Depends(get_current_user)):
        if not user_has_any_role(user, *roles):
            raise HTTPException(status_code=403, detail="Droits insuffisants")
        return user
    return _dep
