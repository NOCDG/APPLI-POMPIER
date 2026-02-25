from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_session
from app.core.security import get_current_user, user_has_any_role
from app.db.models import Garde, Indisponibilite, Personnel

router = APIRouter(prefix="/indisponibilites", tags=["indisponibilites"])


class IndispoRead(BaseModel):
    id: int
    garde_id: int
    personnel_id: int
    model_config = {"from_attributes": True}


class IndispoCreate(BaseModel):
    garde_id: int
    personnel_id: int


def _is_privileged(user: Personnel) -> bool:
    return user_has_any_role(user, "ADMIN", "OFFICIER", "CHEF_EQUIPE", "ADJ_CHEF_EQUIPE")


@router.get("", response_model=list[IndispoRead])
def list_indisponibilites(
    garde_id: int | None = Query(None),
    personnel_id: int | None = Query(None),
    db: Session = Depends(get_session),
    user: Personnel = Depends(get_current_user),
):
    q = select(Indisponibilite)
    if garde_id is not None:
        q = q.where(Indisponibilite.garde_id == garde_id)
    if personnel_id is not None:
        q = q.where(Indisponibilite.personnel_id == personnel_id)
    return db.scalars(q).all()


@router.post("", response_model=IndispoRead)
def create_indisponibilite(
    payload: IndispoCreate,
    db: Session = Depends(get_session),
    user: Personnel = Depends(get_current_user),
):
    # Agents et OPE ne peuvent déclarer que leur propre indisponibilité
    if _is_privileged(user):
        target_id = payload.personnel_id
    else:
        target_id = user.id  # force à soi-même

    if not db.get(Garde, payload.garde_id):
        raise HTTPException(404, "Garde introuvable")
    if not db.get(Personnel, target_id):
        raise HTTPException(404, "Personnel introuvable")

    indi = Indisponibilite(garde_id=payload.garde_id, personnel_id=target_id)
    db.add(indi)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Déjà marqué indisponible")
    db.refresh(indi)
    return indi


@router.delete("/{indi_id}")
def delete_indisponibilite(
    indi_id: int,
    db: Session = Depends(get_session),
    user: Personnel = Depends(get_current_user),
):
    indi = db.get(Indisponibilite, indi_id)
    if not indi:
        raise HTTPException(404, "Indisponibilité introuvable")

    # Un non-privilégié ne peut supprimer que sa propre indisponibilité
    if not _is_privileged(user) and indi.personnel_id != user.id:
        raise HTTPException(403, "Vous ne pouvez supprimer que vos propres indisponibilités")

    db.delete(indi)
    db.commit()
    return {"ok": True}
