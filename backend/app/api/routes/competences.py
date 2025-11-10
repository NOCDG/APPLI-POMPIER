from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.api.deps import get_session
from app.db.models import Competence
from app.schemas.competence import CompetenceCreate, CompetenceRead

router = APIRouter(prefix="/competences", tags=["competences"])

@router.post("", response_model=CompetenceRead)
@router.post("/", response_model=CompetenceRead)
def create_competence(payload: CompetenceCreate, db: Session = Depends(get_session)):
    # unicité code déjà garantie par la BDD; on peut lever un 409 si doublon
    if db.scalar(select(Competence).where(Competence.code == payload.code)):
        raise HTTPException(status_code=409, detail="Code déjà existant")
    c = Competence(**payload.model_dump())
    db.add(c); db.commit(); db.refresh(c)
    return c

@router.get("/", response_model=list[CompetenceRead])
@router.get("", response_model=list[CompetenceRead])
def list_competences(db: Session = Depends(get_session)):
    return db.scalars(select(Competence).order_by(Competence.code)).all()

@router.put("/{cid}", response_model=CompetenceRead)
@router.put("{cid}", response_model=CompetenceRead)
def update_competence(cid: int, payload: CompetenceCreate, db: Session = Depends(get_session)):
    c = db.get(Competence, cid)
    if not c:
        raise HTTPException(status_code=404, detail="Compétence introuvable")
    # vérifier unicité code si changement
    if payload.code != c.code and db.scalar(select(Competence).where(Competence.code == payload.code)):
        raise HTTPException(status_code=409, detail="Code déjà existant")
    c.code = payload.code
    c.libelle = payload.libelle
    db.commit(); db.refresh(c)
    return c

@router.delete("/{cid}")
@router.delete("{cid}")
def delete_competence(cid: int, db: Session = Depends(get_session)):
    c = db.get(Competence, cid)
    if not c:
        raise HTTPException(status_code=404, detail="Compétence introuvable")
    db.delete(c); db.commit()
    return {"ok": True}
