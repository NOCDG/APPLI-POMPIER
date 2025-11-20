# app/core/security.py
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Iterable, Set

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.api.deps import get_session
from app.db.models import RoleEnum, Garde, Personnel

# ====== CONFIG (mets ça dans tes settings si tu veux) ======
ALGO = "HS256"
JWT_SECRET = "pfM6%7&ZaKXNSx@G^5nK"       # ← à mettre en variable d'env
JWT_EXPIRE_MINUTES = 60 * 8                # 8h

# ====== RESET PASSWORD TOKEN ======
RESET_SECRET = "KFfuy4%pBaPWrpRSX^w^"    # ← à mettre en variable d'env
RESET_EXPIRE_MINUTES = 30                  # 30 minutes de validité

# ====== PASSWORD HASHING ======
_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return _pwd_ctx.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_ctx.verify(plain, hashed)


# ====== JWT (LOGIN) ======
def create_access_token(subject: str, roles: List[str]) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "roles": roles,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=JWT_EXPIRE_MINUTES)).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=ALGO)


# ====== JWT (RESET PASSWORD) ======
def create_reset_token(email: str) -> str:
    """
    Token spécifique au reset de mot de passe.
    scope="password_reset", valable RESET_EXPIRE_MINUTES.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": email,
        "scope": "password_reset",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=RESET_EXPIRE_MINUTES)).timestamp()),
    }
    return jwt.encode(payload, RESET_SECRET, algorithm=ALGO)


def verify_reset_token(token: str) -> str:
    """
    Vérifie le token de reset et renvoie l'email s'il est valide.
    Lève HTTP 400 sinon.
    """
    try:
        data = jwt.decode(token, RESET_SECRET, algorithms=[ALGO])
        if data.get("scope") != "password_reset":
            raise JWTError("Scope invalide")
        email = data.get("sub")
        if not email:
            raise JWTError("Token sans sujet")
        return email
    except JWTError:
        raise HTTPException(status_code=400, detail="Token invalide ou expiré")


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


# ====== ROLES / AUTORISATIONS ======
def user_roles_set(user: Personnel) -> Set[RoleEnum]:
    """Retourne l'ensemble des rôles du user depuis la BDD (RoleEnum)."""
    if not user or not getattr(user, "roles", None):
        return set()
    return {r.role for r in user.roles}


def _normalize_roles_args(*roles: Iterable) -> Set[str]:
    """
    Normalise une liste de rôles (RoleEnum, str, liste/tuple...) en set de str UPPER().
    Permet de passer indifféremment RoleEnum.ADMIN ou "ADMIN" ou [RoleEnum.ADMIN, ...].
    """
    result: Set[str] = set()

    def _add_one(val) -> None:
        if val is None:
            return
        # Enum -> .name
        if hasattr(val, "name"):
            result.add(str(val.name).upper().strip())
        # string
        elif isinstance(val, str):
            result.add(val.upper().strip())
        else:
            try:
                result.add(str(val).upper().strip())
            except Exception:
                pass

    for r in roles:
        if r is None:
            continue
        if isinstance(r, (list, tuple, set, frozenset)):
            for sub in r:
                _add_one(sub)
        else:
            _add_one(r)
    return result


def user_has_any_role(user: Personnel, *roles) -> bool:
    """
    True si l'utilisateur possède au moins un des rôles passés.
    roles peut contenir des RoleEnum, str, listes/tuples...
    """
    have = _normalize_roles_args(user_roles_set(user))  # rôles du user
    wanted = _normalize_roles_args(*roles)              # rôles demandés
    return bool(have & wanted)


def ensure_admin_off(user: Personnel) -> None:
    """Autorise uniquement ADMIN / OFFICIER, sinon 403."""
    print(
        "[DEBUG ensure_admin_off]",
        getattr(user, "id", None),
        getattr(user, "roles", None),
    )
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
        * Si equipe_id est None, on le déduit de user.equipe_id.
        * Si equipe_id != user.equipe_id -> 403.
      - Autres : 403.
    Retourne l'equipe_id éventuellement déduit.
    """
    if user_has_any_role(user, RoleEnum.ADMIN, RoleEnum.OFFICIER):
        return equipe_id

    if user_has_any_role(user, RoleEnum.CHEF_EQUIPE, RoleEnum.ADJ_CHEF_EQUIPE):
        if user.equipe_id is None:
            raise HTTPException(
                status_code=400,
                detail="Votre compte n'est associé à aucune équipe",
            )
        if equipe_id is None:
            return user.equipe_id
        if equipe_id != user.equipe_id:
            raise HTTPException(
                status_code=403,
                detail="Vous ne pouvez valider que pour votre équipe",
            )
        return equipe_id

    raise HTTPException(status_code=403, detail="Vous n'êtes pas autorisé à valider")


def ensure_can_modify_garde(user: Personnel, garde: Garde) -> None:
    """
    Interdit de modifier une garde validée, sauf ADMIN / OFFICIER.
    À appeler dans les routes d'affectations (create/delete) et autres modifs.
    """
    if getattr(garde, "validated", False) and not user_has_any_role(
        user, RoleEnum.ADMIN, RoleEnum.OFFICIER
    ):
        # 423 Locked = ressource verrouillée (logique métier)
        raise HTTPException(
            status_code=423,
            detail="Garde validée : modification réservée à ADMIN/OFFICIER",
        )


def require_roles(*roles):
    """
    Dépendance FastAPI : bloque si l'utilisateur n'a aucun des rôles donnés.
    Usage :
        @router.get(..., dependencies=[Depends(require_roles(RoleEnum.ADMIN))])
    ou:
        @router.get(..., dependencies=[Depends(require_roles("ADMIN", "OFFICIER"))])
    """
    def _dep(user: Personnel = Depends(get_current_user)):
        if not user_has_any_role(user, *roles):
            raise HTTPException(status_code=403, detail="Droits insuffisants")
        return user

    return _dep
