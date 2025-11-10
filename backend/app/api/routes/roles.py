# app/api/roles.py
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.api.deps import get_session
from app.core.security import get_current_user
from app.db.models import Personnel, PersonnelRole, RoleEnum

router = APIRouter(prefix="/roles", tags=["roles"])

# --- helpers d'auth simple ---
def _is_admin_or_officier(user) -> bool:
    rs = {ur.role for ur in getattr(user, "roles", [])}
    return RoleEnum.ADMIN in rs or RoleEnum.OFFICIER in rs

class AssignRolePayload(BaseModel):
    personnel_id: int
    role: RoleEnum

# ---------- LISTE DES RÔLES (pour le formulaire) ----------
@router.get("")
def list_all_roles():
    # renvoie la liste des rôles disponibles sous forme de strings
    return [r.value for r in RoleEnum]

# ---------- LISTER LES RÔLES D’UN UTILISATEUR ----------
@router.get("/{personnel_id}")
def list_personnel_roles(personnel_id: int, db: Session = Depends(get_session), user=Depends(get_current_user)):
    # Option : limiter la visibilité (ex: admin/officier), sinon enlève ce check
    # if not _is_admin_or_officier(user): raise HTTPException(403, "Accès réservé")
    p = db.get(Personnel, personnel_id)
    if not p: raise HTTPException(404, "Personnel introuvable")
    roles = [r.role.value for r in p.roles]
    return roles or ["AGENT"]

# ---------- LISTER TOUS LES UTILISATEURS + RÔLES (déjà présent chez toi) ----------
@router.get("/list-users")
@router.get("list-users")
def list_users(db: Session = Depends(get_session), user=Depends(get_current_user)):
    if not _is_admin_or_officier(user): raise HTTPException(403, "Accès réservé")
    rows = db.query(Personnel).all()
    return [
        {
            "id": p.id,
            "email": getattr(p, "email", None),
            "equipe_id": p.equipe_id,
            "roles": [r.role.value for r in p.roles] or ["AGENT"]
        }
        for p in rows
    ]

# ---------- ASSIGN (POST avec JSON body) ----------
@router.post("/assign")
def assign_role(payload: AssignRolePayload, db: Session = Depends(get_session), user=Depends(get_current_user)):
    if not _is_admin_or_officier(user): raise HTTPException(403, "Accès réservé")
    p = db.get(Personnel, payload.personnel_id)
    if not p: raise HTTPException(404, "Personnel introuvable")
    if payload.role == RoleEnum.AGENT:
        # AGENT = rôle par défaut implicite -> rien à insérer
        return {"ok": True}
    if any(pr.role == payload.role for pr in p.roles):
        return {"ok": True}  # déjà présent
    db.add(PersonnelRole(personnel_id=p.id, role=payload.role))
    db.commit()
    return {"ok": True}

# ---------- REVOKE (DELETE avec query params, pour coller à api.ts) ----------
@router.delete("/assign")
def remove_role_from_personnel(
    personnel_id: int = Query(...),
    role: RoleEnum = Query(...),
    db: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    if not _is_admin_or_officier(user): raise HTTPException(403, "Accès réservé")
    p = db.get(Personnel, personnel_id)
    if not p: raise HTTPException(404, "Personnel introuvable")
    if role == RoleEnum.AGENT:
        return {"ok": True}  # on ne supprime pas "AGENT" (implicite)
    pr = next((pr for pr in p.roles if pr.role == role), None)
    if pr:
        db.delete(pr)
        db.commit()
    return {"ok": True}

# ---------- (Optionnel) Compat avec POST /roles/revoke en body JSON ----------
@router.post("/revoke")
def revoke_role(
    # ✅ accepte soit un body JSON…
    payload: Optional[AssignRolePayload] = Body(None),
    # ✅ …soit des query params (compat front existant)
    personnel_id: Optional[int] = Query(None),
    role: Optional[RoleEnum] = Query(None),
    db: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    if not _is_admin_or_officier(user):
        raise HTTPException(403, "Accès réservé")

    # Unifier les entrées
    if payload is not None:
        pid = payload.personnel_id
        r = payload.role
    else:
        if personnel_id is None or role is None:
            raise HTTPException(422, "personnel_id et role sont requis (body ou query)")
        pid = personnel_id
        r = role

    p = db.get(Personnel, pid)
    if not p:
        raise HTTPException(404, "Personnel introuvable")

    if r == RoleEnum.AGENT:
        # AGENT est implicite, rien à retirer
        return {"ok": True}

    pr = next((pr for pr in p.roles if pr.role == r), None)
    if pr:
        db.delete(pr)
        db.commit()
    return {"ok": True}