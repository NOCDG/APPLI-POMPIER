# app/core/security_deps.py
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.api.deps import get_session
from app.core.security import get_current_user
from app.core.permissions import is_full_access, can_read_all, can_read_team, can_edit_team
from app.db.models import Garde

def _garde_team_id(db: Session, garde_id: int) -> int | None:
    g = db.get(Garde, garde_id)
    return getattr(g, "equipe_id", None) if g else None

def require_full_access(user=Depends(get_current_user)):
    if not is_full_access(user):
        raise HTTPException(status_code=403, detail="Accès réservé ADMIN/OFFICIER")
    return user

def require_read_all(user=Depends(get_current_user)):
    if not can_read_all(user):
        raise HTTPException(status_code=403, detail="Lecture globale réservée (OPÉ/ADMIN/OFFICIER)")
    return user

def require_read_team(team_id: int):
    def dep(user=Depends(get_current_user)):
        if not can_read_team(user, team_id):
            raise HTTPException(status_code=403, detail="Lecture restreinte à votre équipe")
        return user
    return dep

def require_edit_garde(garde_id: int):
    """Autorise ADMIN/OFFICIER, sinon CHEF/ADJ de la même équipe que la garde."""
    def dep(db: Session = Depends(get_session), user=Depends(get_current_user)):
        team_id = _garde_team_id(db, garde_id)
        if not can_edit_team(user, team_id):
            raise HTTPException(status_code=403, detail="Modification limitée à votre équipe")
        return user
    return dep
