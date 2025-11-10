# app/api/routes/users_me.py
from fastapi import APIRouter, Depends
from app.core.security import get_current_user
from app.db.models import Personnel

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/me")
def users_me(user: Personnel = Depends(get_current_user)):
    roles = [r.role.value for r in getattr(user, "roles", [])] or ["AGENT"]
    full_name = f"{getattr(user, 'prenom', '')} {getattr(user, 'nom', '')}".strip()
    return {
        "id": user.id,
        "email": user.email,
        "full_name": full_name or user.email,
        "equipe_id": getattr(user, "equipe_id", None),
        "roles": roles,
    }
