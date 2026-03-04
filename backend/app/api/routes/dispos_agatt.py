import unicodedata
from datetime import date as DateType
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_session
from app.core.roles import require_roles
from app.db.models import (
    DispoAgatt, Personnel, PiquetCompetence, PersonnelCompetence, RoleEnum,
)
from app.services.gmail_fetcher import fetch_csv_from_gmail

router = APIRouter(prefix="/dispos-agatt", tags=["dispos-agatt"])


def _normalize(s: str) -> str:
    return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().upper().strip()


@router.get("")
@router.get("/")
def get_dispos_agatt(
    date: str = Query(..., description="Date ISO YYYY-MM-DD"),
    slot: str = Query(..., description="JOUR ou NUIT"),
    is_astreinte: bool = Query(False),
    piquet_id: Optional[int] = Query(None),
    db: Session = Depends(get_session),
):
    """
    Retourne les personnels disponibles pour une garde donnée,
    issus de la table dispos_agatt (synchronisée depuis le CSV Agatt).

    Mapping types :
      Garde NUIT       → DN
      Garde JOUR       → DJ
      Astreinte NUIT   → DN + DAN
      Astreinte JOUR   → DJ + DAJ
    """
    slot_up = slot.upper()
    if is_astreinte:
        types = ["DN", "DAN"] if slot_up == "NUIT" else ["DJ", "DAJ"]
    else:
        types = ["DN"] if slot_up == "NUIT" else ["DJ"]

    try:
        target_date = DateType.fromisoformat(date)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Date invalide : {date}")

    # Noms (normalisés) des dispos pour cette date + ces types
    rows: list[DispoAgatt] = db.scalars(
        select(DispoAgatt).where(
            DispoAgatt.date == target_date,
            DispoAgatt.type_occ.in_(types),
        )
    ).all()

    if not rows:
        return []

    dispo_keys = {(r.nom, r.prenom) for r in rows}

    # Compétences requises par le piquet (si fourni)
    required_competence_ids: set[int] | None = None
    if piquet_id is not None:
        reqs = db.scalars(
            select(PiquetCompetence).where(PiquetCompetence.piquet_id == piquet_id)
        ).all()
        required_competence_ids = {r.competence_id for r in reqs} if reqs else set()

    # Matching contre les personnels actifs
    all_persons: list[Personnel] = db.scalars(
        select(Personnel).where(Personnel.is_active == True)
    ).all()

    matched = []
    seen_ids: set[int] = set()

    for person in all_persons:
        key = (_normalize(person.nom), _normalize(person.prenom))
        if key not in dispo_keys:
            continue
        if person.id in seen_ids:
            continue

        # Filtre compétences (présence uniquement, pas d'expiration)
        if required_competence_ids:
            pcs = db.scalars(
                select(PersonnelCompetence).where(
                    PersonnelCompetence.personnel_id == person.id,
                    PersonnelCompetence.competence_id.in_(required_competence_ids),
                )
            ).all()
            if not required_competence_ids.issubset({pc.competence_id for pc in pcs}):
                continue

        seen_ids.add(person.id)
        matched.append({
            "id": person.id,
            "nom": person.nom,
            "prenom": person.prenom,
            "grade": person.grade,
            "equipe_id": person.equipe_id,
            "statut": person.statut.value if hasattr(person.statut, "value") else str(person.statut),
        })

    return matched


@router.get("/pro-garde")
def get_pro_garde(
    date: str = Query(..., description="Date ISO YYYY-MM-DD"),
    db: Session = Depends(get_session),
):
    """Retourne les professionnels de garde (G24) pour une date donnée."""
    try:
        target_date = DateType.fromisoformat(date)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Date invalide : {date}")

    rows: list[DispoAgatt] = db.scalars(
        select(DispoAgatt).where(
            DispoAgatt.date == target_date,
            DispoAgatt.type_occ == "G24",
        )
    ).all()

    if not rows:
        return []

    dispo_keys = {(r.nom, r.prenom) for r in rows}

    all_persons: list[Personnel] = db.scalars(
        select(Personnel).where(Personnel.is_active == True)
    ).all()

    matched = []
    seen_ids: set[int] = set()
    for person in all_persons:
        key = (_normalize(person.nom), _normalize(person.prenom))
        if key not in dispo_keys or person.id in seen_ids:
            continue
        seen_ids.add(person.id)
        matched.append({
            "id": person.id,
            "nom": person.nom,
            "prenom": person.prenom,
            "grade": person.grade,
            "equipe_id": person.equipe_id,
            "statut": person.statut.value if hasattr(person.statut, "value") else str(person.statut),
        })

    return matched


@router.post("/fetch-gmail")
def trigger_gmail_fetch(
    _=Depends(require_roles(RoleEnum.ADMIN, RoleEnum.OFFICIER)),
):
    """Déclenche manuellement la récupération et la sync BDD du CSV (ADMIN/OFFICIER)."""
    try:
        msg = fetch_csv_from_gmail()
        return {"status": "ok", "detail": msg}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
