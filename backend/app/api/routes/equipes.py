from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.core.security import require_roles
from app.api.deps import get_session
from app.db.models import Equipe
from app.schemas.equipe import EquipeCreate, EquipeRead, EquipeUpdate

router = APIRouter(prefix="/equipes", tags=["equipes"])

@router.post("", response_model=EquipeRead)
@router.post("/", response_model=EquipeRead)
def create_equipe(payload: EquipeCreate, db: Session = Depends(get_session)):
    e = Equipe(**payload.model_dump())
    db.add(e)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Code d'équipe déjà utilisé")
    db.refresh(e)
    return e

@router.get("/", response_model=list[EquipeRead], dependencies=[Depends(require_roles("ADMIN","OFFICIER","OPE","CHEF_EQUIPE","ADJ_CHEF_EQUIPE","AGENT"))])
@router.get("", response_model=list[EquipeRead], dependencies=[Depends(require_roles("ADMIN","OFFICIER","OPE","CHEF_EQUIPE","ADJ_CHEF_EQUIPE","AGENT"))])
def list_equipes(db: Session = Depends(get_session)):
    return db.scalars(select(Equipe).order_by(Equipe.code)).all()

@router.put("/{equipe_id}", response_model=EquipeRead)
@router.put("{equipe_id}", response_model=EquipeRead)
def update_equipe(equipe_id: int, payload: EquipeUpdate, db: Session = Depends(get_session)):
    e = db.get(Equipe, equipe_id)
    if not e:
        raise HTTPException(status_code=404, detail="Équipe introuvable")
    e.code = payload.code
    e.libelle = payload.libelle
    e.couleur = payload.couleur or "#888888"
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Code d'équipe déjà utilisé")
    db.refresh(e)
    return e

@router.delete("/{equipe_id}", status_code=204)
@router.delete("{equipe_id}", status_code=204)
def delete_equipe(equipe_id: int, db: Session = Depends(get_session)):
    e = db.get(Equipe, equipe_id)
    if not e:
        raise HTTPException(status_code=404, detail="Équipe introuvable")
    # On ne cascade pas sur personnels (ton modèle ne le fait pas) → si des FK existent, il faudra les passer à NULL avant.
    db.delete(e)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # Si erreur FK, renvoyer 409 explicite
        raise HTTPException(status_code=409, detail="Impossible de supprimer: personnels associés")
    return None
