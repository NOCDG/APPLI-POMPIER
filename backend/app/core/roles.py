from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.api.deps import get_session
from app.core.security import get_current_user
from app.db.models import PersonnelRole, RoleEnum

def require_roles(*roles: RoleEnum):
    def _dep(user = Depends(get_current_user), db: Session = Depends(get_session)):
        rs = db.scalars(select(PersonnelRole.role).where(PersonnelRole.personnel_id == user.id)).all()
        user_roles = set([r.value if hasattr(r, "value") else str(r) for r in rs])
        needed = set([r.value if hasattr(r, "value") else str(r) for r in roles])
        if user_roles.isdisjoint(needed):
            raise HTTPException(status_code=403, detail="Accès réservé aux administrateurs")
        return user
    return _dep
