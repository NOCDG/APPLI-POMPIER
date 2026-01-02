import calendar
from datetime import date as date_type
from typing import List
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_session
from app.core.security import get_current_user, ensure_can_modify_garde, require_roles
from app.db.models import Affectation, Garde, Piquet, Personnel, Personnel as PersonnelModel
from app.schemas.affectation import AffectationCreate, AffectationRead, AffectationOpeCheckPatch
from app.services.planning import has_all_required_competences, would_make_three_in_a_row

from pydantic import BaseModel

router = APIRouter(prefix="/affectations", tags=["affectations"])


@router.get("", response_model=list[AffectationRead], dependencies=[Depends(require_roles("ADMIN","OFFICIER","OPE","CHEF_EQUIPE","ADJ_CHEF_EQUIPE"))])
def list_affectations(
    garde_id: int | None = Query(None),
    db: Session = Depends(get_session)
):
    q = select(Affectation)
    if garde_id is not None:
        q = q.where(Affectation.garde_id == garde_id)
    return db.scalars(q.order_by(Affectation.garde_id)).all()


@router.post(
    "",
    response_model=AffectationRead,
    dependencies=[Depends(require_roles("ADMIN","OFFICIER","OPE","CHEF_EQUIPE","ADJ_CHEF_EQUIPE"))],
)
def create_affectation(
    payload: AffectationCreate,
    db: Session = Depends(get_session),
    user: PersonnelModel = Depends(get_current_user),
):
    g = db.get(Garde, payload.garde_id)
    if not g:
        raise HTTPException(404, "Garde introuvable")
    p = db.get(Piquet, payload.piquet_id)
    if not p:
        raise HTTPException(404, "Piquet introuvable")
    pers = db.get(Personnel, payload.personnel_id)
    if not pers:
        raise HTTPException(404, "Personnel introuvable")

    # 🔒 bloque si la garde est validée (sauf ADMIN/OFFICIER)
    ensure_can_modify_garde(user, g)

    ok, reasons = has_all_required_competences(db, pers.id, p.id, g.date)
    if not ok:
        raise HTTPException(400, f"Compétences insuffisantes: {', '.join(reasons)}")

    if would_make_three_in_a_row(db, pers.id, g, p):
        raise HTTPException(400, "Règle: pas 3 gardes consécutives (24h de coupure requise)")

    # ============================
    # 🧠 GESTION DU STATUT SERVICE
    # ============================
    # statut principal de la personne (Enum ou str)
    raw = pers.statut
    perso_statut = (
        raw.value.lower() if hasattr(raw, "value")
        else (raw or "").lower()
    )

    # normalisation de ce qui vient du front
    statut_service = payload.statut_service
    if statut_service:
        statut_service = statut_service.lower()
        if statut_service not in ("pro", "volontaire"):
            raise HTTPException(
                status_code=400,
                detail="statut_service doit être 'pro' ou 'volontaire'",
            )

    # si pas fourni, on essaie de le déduire
    if not statut_service:
        if perso_statut in ("pro", "volontaire"):
            # simple : on reprend le statut principal
            statut_service = perso_statut
        elif perso_statut == "double":
            # 🔥 cas important : double mais pas de choix → on refuse
            raise HTTPException(
                status_code=400,
                detail="Ce personnel est en double statut : préciser statut_service = 'pro' ou 'volontaire'",
            )
        else:
            statut_service = None

    # petite cohérence (évite les incohérences front)
    if perso_statut == "pro" and statut_service == "volontaire":
        raise HTTPException(
            status_code=400,
            detail="Ce personnel est PRO uniquement, impossible de l'affecter en VOLONTAIRE",
        )
    if perso_statut == "volontaire" and statut_service == "pro":
        raise HTTPException(
            status_code=400,
            detail="Ce personnel est VOLONTAIRE uniquement, impossible de l'affecter en PRO",
        )

    # ============================
    # CRÉATION
    # ============================
    aff = Affectation(
        garde_id=payload.garde_id,
        piquet_id=payload.piquet_id,
        personnel_id=payload.personnel_id,
        statut_service=statut_service,
        ope_checked=False,
        ope_checked_at=None,
    )
    db.add(aff)
    db.commit()
    db.refresh(aff)
    return aff


# --- Schémas de réponse ---
class PiquetMini(BaseModel):
    id: int
    code: str
    libelle: str | None = None
    class Config:
        from_attributes = True


class EquipeMini(BaseModel):
    id: int
    code: str
    libelle: str | None = None
    class Config:
        from_attributes = True


class MyUpcomingAff(BaseModel):
    affectation_id: int
    garde_id: int
    date: date_type
    slot: str  # 'JOUR' | 'NUIT'
    is_weekend: bool
    is_holiday: bool
    piquet: PiquetMini
    equipe: EquipeMini | None


# GET /affectations/mine_upcoming
@router.get("/mine_upcoming", response_model=List[MyUpcomingAff])
def mine_upcoming_affectations(
    limit: int = Query(10, ge=1, le=100),
    start: date_type | None = Query(None),
    db: Session = Depends(get_session),
    user: PersonnelModel = Depends(get_current_user),
):
    if start is None:
        start = date_type.today()

    rows = (
        db.execute(
            select(Affectation)
            .options(
                joinedload(Affectation.garde).joinedload(Garde.equipe),  # 🔹 charge l’équipe
                joinedload(Affectation.piquet),
            )
            .join(Garde, Garde.id == Affectation.garde_id)
            .where(
                Affectation.personnel_id == user.id,
                Garde.date >= start,
            )
            .order_by(Garde.date.asc(), Garde.slot.asc())
            .limit(limit)
        )
        .unique()
        .scalars()
        .all()
    )

    out: list[MyUpcomingAff] = []
    for a in rows:
        g = a.garde
        p = a.piquet
        if not g or not p:
            continue
        equipe_mini = None
        if getattr(g, "equipe", None):
            equipe_mini = EquipeMini.model_validate(g.equipe, from_attributes=True)
        out.append(MyUpcomingAff(
            affectation_id=a.id,
            garde_id=g.id,
            date=g.date,
            slot=g.slot.name if hasattr(g.slot, "name") else str(g.slot),
            is_weekend=bool(g.is_weekend),
            is_holiday=bool(g.is_holiday),
            piquet=PiquetMini.model_validate(p, from_attributes=True),
            equipe=equipe_mini,  # 🔹 renvoyé si présent
        ))
    return out


# --- Suggestions pour accélérer le planning ---
@router.get("/suggestions", response_model=list[dict])
def suggest_personnels(
    garde_id: int,
    piquet_id: int,
    db: Session = Depends(get_session)
):
    """Renvoie les personnels éligibles triés par:
       - équipe = équipe de la garde en premier
       - nb de gardes déjà faites dans le mois (croissant)
       - nom
    """
    g = db.get(Garde, garde_id)
    if not g:
        raise HTTPException(404, "Garde introuvable")
    pqt = db.get(Piquet, piquet_id)
    if not pqt:
        raise HTTPException(404, "Piquet introuvable")

    # Charge uniquement les personnels actifs (si tu as un flag), sinon tous
    people = db.scalars(select(Personnel)).all()

    # compter correctement le nombre de gardes du mois pour chaque personne
    month_first = g.date.replace(day=1)
    month_last_day = calendar.monthrange(g.date.year, g.date.month)[1]
    month_last = g.date.replace(day=month_last_day)

    rows = []
    for pers in people:
        ok_comp, reasons = has_all_required_competences(db, pers.id, pqt.id, g.date)
        if not ok_comp:
            continue
        if would_make_three_in_a_row(db, pers.id, g, pqt):
            continue

        # nombre de gardes dans le mois (compte réel)
        nb = db.scalar(
            select(func.count(Affectation.id))
            .join(Garde, Garde.id == Affectation.garde_id)
            .where(
                Affectation.personnel_id == pers.id,
                Garde.date >= month_first,
                Garde.date <= month_last,
            )
        ) or 0

        rows.append({
            "id": pers.id,
            "nom": pers.nom, "prenom": pers.prenom,
            "equipe_id": pers.equipe_id,
            "priorite": (0 if pers.equipe_id == g.equipe_id else 1, nb, pers.nom.upper()),
        })

    rows.sort(key=lambda r: r["priorite"])
    return rows

@router.patch(
    "/{affectation_id}",
    response_model=AffectationRead,
    dependencies=[Depends(require_roles("ADMIN", "OFFICIER", "OPE"))],
)
def patch_affectation_ope_checked(
    affectation_id: int,
    payload: AffectationOpeCheckPatch,
    db: Session = Depends(get_session),
    user: PersonnelModel = Depends(get_current_user),
):
    a = db.get(Affectation, affectation_id)
    if not a:
        raise HTTPException(404, "Affectation introuvable")

    # Option métier: autoriser OPE même si garde validée (c'est de la saisie/contrôle)
    # Si tu veux verrouiller quand validée, dé-commente:
    # g = db.get(Garde, a.garde_id)
    # if not g:
    #     raise HTTPException(404, "Garde introuvable")
    # ensure_can_modify_garde(user, g)

    a.ope_checked = bool(payload.ope_checked)
    a.ope_checked_at = datetime.now(timezone.utc) if a.ope_checked else None

    db.add(a)
    db.commit()
    db.refresh(a)
    return a

class BulkOpeCheckPayload(BaseModel):
    checked: bool


@router.post(
    "/garde/{garde_id}/ope-check",
    dependencies=[Depends(require_roles("ADMIN", "OFFICIER", "OPE"))],
)
def bulk_ope_check_for_garde(
    garde_id: int,
    payload: BulkOpeCheckPayload,
    db: Session = Depends(get_session),
    user: PersonnelModel = Depends(get_current_user),
):
    g = db.get(Garde, garde_id)
    if not g:
        raise HTTPException(404, "Garde introuvable")

    # Même remarque que plus haut :
    # si tu veux interdire quand la garde est validée, dé-commente :
    # ensure_can_modify_garde(user, g)

    affs = db.scalars(select(Affectation).where(Affectation.garde_id == garde_id)).all()

    now = datetime.now(timezone.utc) if payload.checked else None
    for a in affs:
        a.ope_checked = bool(payload.checked)
        a.ope_checked_at = now

    db.commit()
    return {"ok": True, "garde_id": garde_id, "count": len(affs), "checked": bool(payload.checked)}

@router.delete("/{affectation_id}", dependencies=[Depends(require_roles("ADMIN","OFFICIER","OPE","CHEF_EQUIPE","ADJ_CHEF_EQUIPE"))])
def delete_affectation(
    affectation_id: int,
    db: Session = Depends(get_session),
    user: PersonnelModel = Depends(get_current_user),
):
    a = db.get(Affectation, affectation_id)
    if not a:
        raise HTTPException(404, "Affectation introuvable")
    g = db.get(Garde, a.garde_id)
    if not g:
        raise HTTPException(404, "Garde introuvable")

    # 🔒 bloque la suppression si garde validée (sauf ADMIN/OFFICIER)
    ensure_can_modify_garde(user, g)

    db.delete(a); db.commit()
    return {"ok": True}
