import secrets
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.api.deps import get_session
from app.db.models import Personnel, PersonnelCompetence, Statut, PersonnelRole, RoleEnum
from app.schemas.personnel import (
    PersonnelCreate, PersonnelRead, PersonnelCompetenceCreate, PersonnelCompetenceRead, PersonnelCompetenceDetail, PersonnelCreateResponse, PersonnelUpdate, SetEquipePayload
)
from app.core.security import hash_password
from app.core.security import get_current_user
from app.db.models import RoleEnum

router = APIRouter(prefix="/personnels", tags=["personnels"])

# --- CREATE ---
@router.post("", response_model=PersonnelCreateResponse)
@router.post("/", response_model=PersonnelCreateResponse)
def create_personnel(payload: PersonnelCreate, db: Session = Depends(get_session)):
    if db.scalar(select(Personnel).where(Personnel.email == payload.email)):
        raise HTTPException(status_code=400, detail="Email déjà utilisé")

    statut_in = (payload.statut or "").strip().lower()
    if statut_in not in ("pro", "volontaire"):
        raise HTTPException(status_code=400, detail="Statut doit être 'pro' ou 'volontaire'")
    statut_enum = Statut.PRO if statut_in == "pro" else Statut.VOLONTAIRE

        # 1) générer un mdp temporaire
    temp_pwd = secrets.token_urlsafe(12)  # ~16 caractères

    p = Personnel(
        nom=payload.nom, prenom=payload.prenom, grade=payload.grade,
        email=payload.email, statut=statut_enum, equipe_id=payload.equipe_id,
        hashed_password=hash_password(temp_pwd),  # 2) hasher et stocker
    )
    db.add(p); db.commit(); db.refresh(p)

    # 3) affecter les rôles (si envoyés ; défaut = AGENT)
    roles_in = payload.roles or [RoleEnum.AGENT]
    for r in roles_in:
        db.add(PersonnelRole(personnel_id=p.id, role=r))
    db.commit(); db.refresh(p)

    # 4) renvoyer le mdp UNE SEULE FOIS
    
    return {"personnel": p, "temp_password": temp_pwd}

# --- LIST ---
@router.get("", response_model=list[PersonnelRead])   # sans slash
@router.get("/", response_model=list[PersonnelRead])  # avec slash
def list_personnels(db: Session = Depends(get_session)):
    return db.scalars(select(Personnel).order_by(Personnel.nom, Personnel.prenom)).all()

@router.post("/{personnel_id}/competences", response_model=PersonnelCompetenceRead)
@router.post("/{personnel_id}/competences/", response_model=PersonnelCompetenceRead)
def add_competence_to_personnel(
    personnel_id: int,
    payload: PersonnelCompetenceCreate,
    db: Session = Depends(get_session)
):
    """Ajoute une compétence à un personnel."""
    personnel = db.get(Personnel, personnel_id)
    if not personnel:
        raise HTTPException(status_code=404, detail="Personnel introuvable")

    # Création de la relation
    competence = PersonnelCompetence(
        personnel_id=personnel_id,
        competence_id=payload.competence_id,
        date_obtention=payload.date_obtention,
        date_expiration=payload.date_expiration
    )
    db.add(competence)
    db.commit()
    db.refresh(competence)
    return competence

@router.get("/{personnel_id}/competences", response_model=list[PersonnelCompetenceDetail])
@router.get("/{personnel_id}/competences/", response_model=list[PersonnelCompetenceDetail])
def list_competences_of_personnel(personnel_id: int, db: Session = Depends(get_session)):
    p = db.get(Personnel, personnel_id)
    if not p:
        raise HTTPException(404, "Personnel introuvable")
    # récupère les liaisons (avec relationship .competence déjà chargée à l’accès)
    pcs = db.scalars(
        select(PersonnelCompetence).where(PersonnelCompetence.personnel_id == personnel_id)
    ).all()
    return pcs

@router.delete("/competences/{pc_id}")
@router.delete("/competences/{pc_id}/")
def delete_personnel_competence(pc_id: int, db: Session = Depends(get_session)):
    pc = db.get(PersonnelCompetence, pc_id)
    if not pc:
        raise HTTPException(status_code=404, detail="Lien compétence introuvable")
    db.delete(pc)
    db.commit()
    return {"ok": True}

@router.delete("/{personnel_id}")
@router.delete("/{personnel_id}/")
def delete_personnel(personnel_id: int, db: Session = Depends(get_session)):
    p = db.get(Personnel, personnel_id)
    if not p:
        raise HTTPException(404, "Personnel introuvable")
    db.delete(p)
    db.commit()
    return {"ok": True}

@router.put("/{personnel_id}", response_model=PersonnelRead)
@router.put("/{personnel_id}/", response_model=PersonnelRead)
def update_personnel(
    personnel_id: int,
    payload: PersonnelUpdate,
    db: Session = Depends(get_session),
    user=Depends(get_current_user)          # 🔒 protège si tu veux (ADMIN/OFF/OPE)
):
    # 🔒 autorisations simples: ADMIN/OFFICIER/OPE
    if not any(r.role in (RoleEnum.ADMIN, RoleEnum.OFFICIER, RoleEnum.OPE) for r in getattr(user, "roles", [])):
        raise HTTPException(403, "Accès réservé")

    p = db.get(Personnel, personnel_id)
    if not p:
        raise HTTPException(404, "Personnel introuvable")

    # email: contrôle d’unicité si modifié
    if payload.email and payload.email != p.email:
        if db.scalar(select(Personnel).where(Personnel.email == payload.email)):
            raise HTTPException(400, "Email déjà utilisé")
        p.email = payload.email

    if payload.nom is not None:
        p.nom = payload.nom
    if payload.prenom is not None:
        p.prenom = payload.prenom
    if payload.grade is not None:
        p.grade = payload.grade
    if payload.equipe_id is not None:
        p.equipe_id = payload.equipe_id

    if payload.statut is not None:
        st = payload.statut.strip().lower()
        if st not in ("pro", "volontaire"):
            raise HTTPException(400, "Statut doit être 'pro' ou 'volontaire'")
        p.statut = Statut.PRO if st == "pro" else Statut.VOLONTAIRE

    db.commit()
    db.refresh(p)
    return p


# ---------- PATCH équipe (PATCH /personnels/{id}/equipe) ----------
@router.patch("/{personnel_id}/equipe")
@router.patch("/{personnel_id}/equipe/")
def set_personnel_equipe(
    personnel_id: int,
    payload: SetEquipePayload,
    db: Session = Depends(get_session),
    user=Depends(get_current_user)          # 🔒 protège si tu veux (ADMIN/OFF/OPE)
):
    # 🔒 autorisations simples: ADMIN/OFFICIER/OPE
    if not any(r.role in (RoleEnum.ADMIN, RoleEnum.OFFICIER, RoleEnum.OPE) for r in getattr(user, "roles", [])):
        raise HTTPException(403, "Accès réservé")

    p = db.get(Personnel, personnel_id)
    if not p:
        raise HTTPException(404, "Personnel introuvable")

    p.equipe_id = payload.equipe_id if payload.equipe_id is not None else None
    db.commit()
    return {"ok": True, "personnel_id": p.id, "equipe_id": p.equipe_id}

@router.post("", response_model=PersonnelCreateResponse)    # sans slash
@router.post("/", response_model=PersonnelCreateResponse)   # avec slash
def create_personnel(payload: PersonnelCreate, db: Session = Depends(get_session)):
    if db.scalar(select(Personnel).where(Personnel.email == payload.email)):
        raise HTTPException(status_code=400, detail="Email déjà utilisé")

    statut_in = (payload.statut or "").strip().lower()
    if statut_in not in ("pro", "volontaire"):
        raise HTTPException(status_code=400, detail="Statut doit être 'pro' ou 'volontaire'")
    statut_enum = Statut.PRO if statut_in == "pro" else Statut.VOLONTAIRE

    # 🔐 génère un mot de passe temporaire (lisible et suffisamment entropique)
    temp_pwd = secrets.token_urlsafe(12)  # ~16 caractères

    p = Personnel(
        nom=payload.nom,
        prenom=payload.prenom,
        grade=payload.grade,
        email=payload.email,
        statut=statut_enum,
        equipe_id=payload.equipe_id,
        hashed_password=hash_password(temp_pwd),
    )
    db.add(p)
    db.commit()
    db.refresh(p)

    # 🎭 rôles (liste). Si vide → AGENT
    roles_in = payload.roles or [RoleEnum.AGENT]
    for r in roles_in:
        db.add(PersonnelRole(personnel_id=p.id, role=r))
    db.commit()
    db.refresh(p)

    # ✅ on renvoie le mdp temporaire UNE SEULE FOIS
    return PersonnelCreateResponse(personnel=p, temp_password=temp_pwd)