from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List
from sqlalchemy import select, and_
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError
from app.core.security import require_roles
from app.api.deps import get_session
from app.db.models import Piquet, PiquetCompetence, Competence
from app.schemas.piquet import PiquetCreate, PiquetRead, CompetenceMini

router = APIRouter(prefix="/piquets", tags=["piquets"])

# -------- helpers --------
def _query_piquet_with_exigences(db: Session):
    return (
        select(Piquet)
        .options(joinedload(Piquet.exigences).joinedload(PiquetCompetence.competence))
        .order_by(Piquet.position, Piquet.code)  # <= tri par position puis code
    )

def _to_read_schema(p: Piquet) -> PiquetRead:
    exigences = []
    for pc in (p.exigences or []):
        if pc.competence:
            exigences.append(
                CompetenceMini(
                    id=pc.competence.id,
                    code=pc.competence.code,
                    libelle=pc.competence.libelle,
                )
            )
    return PiquetRead(
        id=p.id, 
        code=p.code, 
        libelle=p.libelle, 
        exigences=exigences,
        is_astreinte=bool(getattr(p, "is_astreinte", False))
        )

# -------- CRUD --------
@router.post("/", response_model=PiquetRead)
@router.post("", response_model=PiquetRead)
def create_piquet(payload: PiquetCreate, db: Session = Depends(get_session)):
    # place en fin
    last_pos = db.scalar(select(Piquet.position).order_by(Piquet.position.desc()).limit(1)) or 0
    p = Piquet(code=payload.code, libelle=payload.libelle, position=last_pos + 1)
    db.add(p)
    db.flush()
    for cid in payload.exigences or []:
        db.add(PiquetCompetence(piquet_id=p.id, competence_id=cid))
    db.commit()
    p = db.scalar(_query_piquet_with_exigences(db).where(Piquet.id == p.id))
    return _to_read_schema(p)

@router.get("/", response_model=list[PiquetRead], dependencies=[Depends(require_roles("ADMIN","OFFICIER","OPE","CHEF_EQUIPE","ADJ_CHEF_EQUIPE"))])
@router.get("", response_model=list[PiquetRead], dependencies=[Depends(require_roles("ADMIN","OFFICIER","OPE","CHEF_EQUIPE","ADJ_CHEF_EQUIPE"))])
def list_piquets(db: Session = Depends(get_session)):
    rows = db.execute(_query_piquet_with_exigences(db)).unique().scalars().all()
    return [_to_read_schema(p) for p in rows]

@router.delete("/{piquet_id}", status_code=204)
@router.delete("{piquet_id}", status_code=204)
def delete_piquet(piquet_id: int, db: Session = Depends(get_session)):
    p = db.get(Piquet, piquet_id)
    if not p:
        raise HTTPException(status_code=404, detail="Piquet introuvable")
    db.delete(p)  # cascade sur PiquetCompetence/Affectations selon tes modèles
    db.commit()
    return None

# -------- exigences (ajout/suppression) --------
class AddExigencePayload(BaseModel):
    competence_id: int

@router.post("/{piquet_id}/exigences", response_model=PiquetRead)
@router.post("{piquet_id}/exigences", response_model=PiquetRead)
def add_exigence(piquet_id: int, payload: AddExigencePayload, db: Session = Depends(get_session)):
    p = db.get(Piquet, piquet_id)
    if not p:
        raise HTTPException(status_code=404, detail="Piquet introuvable")

    c = db.get(Competence, payload.competence_id)
    if not c:
        raise HTTPException(status_code=404, detail="Compétence introuvable")

    exists = db.scalar(
        select(PiquetCompetence).where(
            and_(
                PiquetCompetence.piquet_id == piquet_id,
                PiquetCompetence.competence_id == payload.competence_id,
            )
        )
    )
    if not exists:
        db.add(PiquetCompetence(piquet_id=piquet_id, competence_id=payload.competence_id))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()

    p = db.scalar(_query_piquet_with_exigences(db).where(Piquet.id == piquet_id))
    return _to_read_schema(p)

@router.delete("/{piquet_id}/exigences/{competence_id}", response_model=PiquetRead)
@router.delete("{piquet_id}/exigences/{competence_id}", response_model=PiquetRead)
def remove_exigence(piquet_id: int, competence_id: int, db: Session = Depends(get_session)):
    p = db.get(Piquet, piquet_id)
    if not p:
        raise HTTPException(status_code=404, detail="Piquet introuvable")

    link = db.scalar(
        select(PiquetCompetence).where(
            and_(
                PiquetCompetence.piquet_id == piquet_id,
                PiquetCompetence.competence_id == competence_id,
            )
        )
    )
    if link:
        db.delete(link)
        db.commit()

    p = db.scalar(_query_piquet_with_exigences(db).where(Piquet.id == piquet_id))
    return _to_read_schema(p)

# -------- réordonnancement des piquets --------
class ReorderPiquetsPayload(BaseModel):
    piquet_ids: List[int]  # ordre final des IDs

@router.put("/reorder", response_model=list[PiquetRead])
@router.put("reorder", response_model=list[PiquetRead])
def reorder_piquets(payload: ReorderPiquetsPayload, db: Session = Depends(get_session)):
    # Met à jour position = index dans la liste (si tu veux commencer à 1, fais enumerate(..., start=1))
    for idx, pid in enumerate(payload.piquet_ids, start=0):
        p = db.get(Piquet, pid)
        if p:
            p.position = idx
    db.commit()

    # ⚠️ joinedload sur une collection => utiliser execute(...).unique().scalars().all()
    rows = db.execute(_query_piquet_with_exigences(db)).unique().scalars().all()
    return [_to_read_schema(p) for p in rows]
