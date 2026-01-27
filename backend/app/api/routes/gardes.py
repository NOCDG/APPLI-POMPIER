from datetime import date as date_type, datetime
import calendar
from typing import List, Iterable

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, and_, func, exists, extract, or_
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.core.mailer import send_mail, build_validation_html, MAIL_FROM_NAME

from app.api.deps import get_session
from app.core.security import (
    get_current_user,
    ensure_can_validate_for_team,
    ensure_admin_off,
    ensure_can_modify_garde, require_roles
)
from app.db.models import (
    Garde, Holiday, Slot, Equipe,
    Piquet, PiquetCompetence,
    Personnel, PersonnelCompetence,
    Affectation, Personnel as PersonnelModel, PersonnelRole, RoleEnum,
)
from app.schemas.garde import (
    GardeRead, GenerateMonthRequest, GardeCreate,
    AssignTeamRequest, GenerateMonthAllRequest,
)

router = APIRouter(prefix="/gardes", tags=["gardes"])


def _is_weekend(d: date_type) -> bool:
    return d.weekday() >= 5


def _is_holiday(db: Session, d: date_type) -> bool:
    return db.scalar(select(Holiday).where(Holiday.date == d)) is not None


# ---------- GET /gardes (liste par année/mois (+ filtre équipe optionnel)) ----------
@router.get("", response_model=list[GardeRead], dependencies=[Depends(require_roles("ADMIN","OFFICIER","OPE","AGENT","CHEF_EQUIPE","ADJ_CHEF_EQUIPE"))])
@router.get("/", response_model=list[GardeRead], dependencies=[Depends(require_roles("ADMIN","OFFICIER","OPE","AGENT","CHEF_EQUIPE","ADJ_CHEF_EQUIPE"))])
def list_gardes(
    year: int = Query(..., ge=1970, le=2100),
    month: int = Query(..., ge=1, le=12),
    equipe_id: int | None = Query(None),
    include_unassigned: bool = Query(False),
    db: Session = Depends(get_session),
):
    q = select(Garde).where(
        and_(
            extract("year", Garde.date) == year,
            extract("month", Garde.date) == month,
        )
    )

    if equipe_id is not None:
        if include_unassigned:
            q = q.where(or_(Garde.equipe_id == equipe_id, Garde.equipe_id.is_(None)))
        else:
            q = q.where(Garde.equipe_id == equipe_id)

    q = q.order_by(Garde.date.asc(), Garde.slot.asc())
    rows = db.scalars(q).all()
    return rows


@router.get("/all", response_model=list[GardeRead], dependencies=[Depends(require_roles("ADMIN","OFFICIER","OPE","CHEF_EQUIPE","ADJ_CHEF_EQUIPE"))])
def list_gardes_all_month(
    year: int = Query(..., ge=1970, le=2100),
    month: int = Query(..., ge=1, le=12),
    db: Session = Depends(get_session),
):
    """
    Renvoie TOUTES les gardes du mois (JOUR/NUIT), qu'elles soient assignées
    à une équipe ou non (equipe_id peut être NULL).
    """
    q = (
        select(Garde)
        .where(
            and_(
                extract("year", Garde.date) == year,
                extract("month", Garde.date) == month,
            )
        )
        .order_by(Garde.date.asc(), Garde.slot.asc())
    )
    return db.scalars(q).all()


# ---------- POST /gardes/generate_month (crée les gardes du mois SANS équipe) ----------
@router.post("/generate_month", response_model=list[GardeRead], dependencies=[Depends(require_roles("ADMIN","OFFICIER","OPE"))])
def generate_month(payload: GenerateMonthRequest, db: Session = Depends(get_session)):
    first = date_type(payload.year, payload.month, 1)
    last = date_type(payload.year, payload.month, calendar.monthrange(payload.year, payload.month)[1])

    created: list[Garde] = []
    d = first
    while d <= last:
        is_we = _is_weekend(d)
        is_hol = _is_holiday(db, d)
        if is_we or is_hol:
            for slot in (Slot.JOUR, Slot.NUIT):
                exists_g = db.scalar(select(Garde).where(Garde.date == d, Garde.slot == slot))
                if not exists_g:
                    g = Garde(date=d, slot=slot, is_weekend=is_we, is_holiday=is_hol, equipe_id=None)
                    db.add(g); created.append(g)
        else:
            exists_g = db.scalar(select(Garde).where(Garde.date == d, Garde.slot == Slot.NUIT))
            if not exists_g:
                g = Garde(date=d, slot=Slot.NUIT, is_weekend=False, is_holiday=False, equipe_id=None)
                db.add(g); created.append(g)
        d = date_type.fromordinal(d.toordinal()+1)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(400, "Contrainte (date,slot) en base – doublon détecté.")
    for g in created:
        db.refresh(g)
    return created


# ---------- POST /gardes (ajout manuel d’une garde SANS équipe) ----------
@router.post("", response_model=GardeRead)
def create_garde(
    payload: GardeCreate,
    db: Session = Depends(get_session),
    user: PersonnelModel = Depends(get_current_user),
):
    d = payload.date
    slot = Slot[payload.slot] if isinstance(payload.slot, str) else payload.slot
    g = Garde(
        date=d, slot=slot,
        equipe_id=None,
        is_weekend=_is_weekend(d), is_holiday=_is_holiday(db, d)
    )
    db.add(g)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(400, "Garde déjà existante pour cette date/slot.")
    db.refresh(g)
    return g


# ---------- DELETE /gardes/{id} ----------
@router.delete("/{garde_id}")
def delete_garde(
    garde_id: int,
    db: Session = Depends(get_session),
    user: PersonnelModel = Depends(get_current_user),
):
    g = db.get(Garde, garde_id)
    if not g:
        raise HTTPException(404, "Garde introuvable")

    # 🔒 bloque la suppression si la garde est validée (sauf ADMIN/OFFICIER)
    ensure_can_modify_garde(user, g)

    db.delete(g)
    db.commit()
    return {"ok": True}


# ---------- PUT /gardes/assign_team (affecter l’équipe d’un jour/slot) ----------
@router.put("/assign_team", response_model=GardeRead, dependencies=[Depends(require_roles("ADMIN","OFFICIER","OPE"))])
def assign_team(
    payload: AssignTeamRequest,
    db: Session = Depends(get_session),
    user: PersonnelModel = Depends(get_current_user),
):
    if not db.get(Equipe, payload.equipe_id):
        raise HTTPException(404, "Équipe inconnue")
    slot = Slot[payload.slot] if isinstance(payload.slot, str) else payload.slot

    existing = db.scalar(select(Garde).where(Garde.date == payload.date, Garde.slot == slot))
    if existing:
        # 🔒 bloque si déjà validée (sauf ADMIN/OFFICIER)
        ensure_can_modify_garde(user, existing)
        existing.equipe_id = payload.equipe_id
        db.commit(); db.refresh(existing); return existing

    g = Garde(
        date=payload.date, slot=slot, equipe_id=payload.equipe_id,
        is_weekend=_is_weekend(payload.date), is_holiday=_is_holiday(db, payload.date)
    )
    db.add(g); db.commit(); db.refresh(g)
    return g


# ---------- PUT /gardes/clear_team (retirer l’équipe d’un jour/slot) ----------
@router.put("/clear_team", response_model=GardeRead, dependencies=[Depends(require_roles("ADMIN","OFFICIER","OPE"))])
def clear_team(
    payload: AssignTeamRequest,
    db: Session = Depends(get_session),
    user: PersonnelModel = Depends(get_current_user),
):
    slot = Slot[payload.slot] if isinstance(payload.slot, str) else payload.slot
    existing = db.scalar(select(Garde).where(Garde.date == payload.date, Garde.slot == slot))
    if not existing:
        raise HTTPException(404, "Garde inexistante pour cette date/slot")

    # 🔒 bloque si validée (sauf ADMIN/OFFICIER)
    ensure_can_modify_garde(user, existing)

    existing.equipe_id = None
    db.commit(); db.refresh(existing)
    return existing


# ---------- POST /gardes/generate_month_all (TOUTES LES DATES SANS ÉQUIPE) ----------
@router.post("/generate_month_all")
@router.post("/generate_month_all/")
def generate_month_all(payload: GenerateMonthAllRequest, db: Session = Depends(get_session)):
    """
    Crée toutes les gardes du mois SANS équipe :
    - Semaine : NUIT
    - Week-end / JF : JOUR + NUIT
    """
    year, month = payload.year, payload.month
    first = date_type(year, month, 1)
    last = date_type(year, month, calendar.monthrange(year, month)[1])

    total_created = 0
    d = first
    while d <= last:
        is_we = _is_weekend(d)
        is_hol = _is_holiday(db, d)
        slots = (Slot.JOUR, Slot.NUIT) if (is_we or is_hol) else (Slot.NUIT,)
        for slot in slots:
            exists_g = db.scalar(select(Garde).where(Garde.date == d, Garde.slot == slot))
            if not exists_g:
                g = Garde(date=d, slot=slot, is_weekend=is_we, is_holiday=is_hol, equipe_id=None)
                db.add(g); total_created += 1
        d = date_type.fromordinal(d.toordinal()+1)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(400, "Contrainte (date,slot) en base – doublon détecté.")
    return {"created": total_created, "year": year, "month": month}


# ---------- GET /gardes/{id}/suggest-personnels (équipe de la garde + compétences du piquet) ----------
class PersonnelMini(BaseModel):
    id: int
    nom: str
    prenom: str
    equipe_id: int | None = None
    class Config:
        from_attributes = True


@router.get("/{garde_id}/suggest-personnels", response_model=List[PersonnelMini])
@router.get("{garde_id}/suggest-personnels", response_model=List[PersonnelMini])  # compat
def suggest_personnels(
    garde_id: int,
    piquet_id: int = Query(..., description="ID du piquet"),
    db: Session = Depends(get_session),
):
    # 1) Garde (équipe + date)
    garde = db.get(Garde, garde_id)
    if not garde:
        raise HTTPException(status_code=404, detail="Garde introuvable")
    if garde.equipe_id is None:
        raise HTTPException(status_code=400, detail="Cette garde n'est pas rattachée à une équipe")

    # 2) Exigences du piquet
    req_ids = db.scalars(
        select(PiquetCompetence.competence_id).where(PiquetCompetence.piquet_id == piquet_id)
    ).all()

    # 3) Base: personnels de la même équipe
    base = select(Personnel).where(Personnel.equipe_id == garde.equipe_id)

    # 4) Exclure ceux déjà affectés sur cette garde
    base = base.where(
        ~exists().where(
            and_(
                Affectation.garde_id == garde_id,
                Affectation.personnel_id == Personnel.id,
            )
        )
    )

    # 5) Si exigences: ne garder que ceux qui possèdent TOUTES les compétences requises,
    #    valides à la date (expiration NULL ou >= date de garde)
    if req_ids:
        pc = PersonnelCompetence
        sub = (
            select(pc.personnel_id, func.count(func.distinct(pc.competence_id)).label("cnt"))
            .where(
                and_(
                    pc.competence_id.in_(req_ids),
                    (pc.date_expiration.is_(None)) | (pc.date_expiration >= garde.date),
                )
            )
            .group_by(pc.personnel_id)
            .subquery()
        )
        base = base.join(sub, sub.c.personnel_id == Personnel.id).where(sub.c.cnt == len(req_ids))

    base = base.order_by(Personnel.nom, Personnel.prenom)
    rows = db.scalars(base).all()
    return [PersonnelMini.model_validate(r, from_attributes=True) for r in rows]


# ---------- VALIDATION / DEVALIDATION DU MOIS ----------
def _month_filter(annee: int, mois: int):
    return and_(
        func.extract("year", Garde.date) == annee,
        func.extract("month", Garde.date) == mois,
    )


VALIDATION_FIXED_RECIPIENT = "operation-st-lo@sdis50.fr"

def _get_officier_emails(db: Session) -> list[str]:
    rows = db.execute(
        select(Personnel.email)
        .join(PersonnelRole, PersonnelRole.personnel_id == Personnel.id)
        .where(
            PersonnelRole.role == RoleEnum.OFFICIER,
            Personnel.is_active.is_(True),
            Personnel.email.is_not(None),
            Personnel.email != "",
        )
        .distinct()
    ).all()
    return [r[0] for r in rows if r and r[0]]


@router.post("/valider-mois")
def valider_mois(
    annee: int = Query(..., ge=1970, le=2100),
    mois: int = Query(..., ge=1, le=12),
    equipe_id: int = Query(...),
    db: Session = Depends(get_session),
    user = Depends(get_current_user),
):
    # 1️⃣ Récupérer les gardes du mois pour l’équipe
    gardes = db.scalars(
        select(Garde)
        .where(
            extract("year", Garde.date) == annee,
            extract("month", Garde.date) == mois,
            Garde.equipe_id == equipe_id,
        )
    ).all()
    if not gardes:
        raise HTTPException(404, "Aucune garde trouvée pour ce mois/équipe")

    # 2️⃣ Valider les gardes
    now = datetime.utcnow()
    for g in gardes:
        g.validated = True
        g.validated_at = now
    db.commit()

    # 3️⃣ Préparer infos générales
    equipe = db.get(Equipe, equipe_id)
    equipe_nom = equipe.libelle or equipe.code or f"Équipe {equipe_id}"
    mois_nom = datetime(annee, mois, 1).strftime("%B %Y").capitalize()
    validator_fullname = f"{getattr(user, 'prenom', '')} {getattr(user, 'nom', '')}".strip() or user.email

    # 4️⃣ Mail validation -> operation-st-lo + OFFICIER
    subject_admin = f"Validation feuille de garde – {mois_nom} – {equipe_nom}"

    # ✅ Ton template (core/mailer.py) attend exactement: (mois_label, equipe_label, validateur)
    html_admin = build_validation_html(mois_nom, equipe_nom, validator_fullname)

    recipients = {VALIDATION_FIXED_RECIPIENT}
    recipients.update(_get_officier_emails(db))

    # ✅ Passe db=db pour que send_mail lise la config mail via AppSetting/env
    send_mail(sorted(recipients), subject_admin, html_admin, db=db)

    # send_mail accepte un str OU un Iterable[str] ; on passe la liste
    send_mail(sorted(recipients), subject_admin, html_admin, db=db)

    # 5️⃣ Récupérer toutes les affectations concernées
    garde_ids = [g.id for g in gardes]
    affs = db.scalars(
        select(Affectation)
        .join(Garde, Garde.id == Affectation.garde_id)
        .join(Piquet, Piquet.id == Affectation.piquet_id)
        .where(Affectation.garde_id.in_(garde_ids))
    ).unique().all()

    # Indexer les gardes
    garde_map = {g.id: g for g in gardes}
    piquet_map = {a.piquet_id: db.get(Piquet, a.piquet_id) for a in affs}

    # 6️⃣ Grouper par personnel
    pers_map: dict[int, list[tuple[str, str, str]]] = {}
    for a in affs:
        g = garde_map.get(a.garde_id)
        if not g:
            continue
        pqt = piquet_map.get(a.piquet_id)
        pers_map.setdefault(a.personnel_id, []).append((
            g.date.strftime("%d/%m/%Y"),
            g.slot.name.capitalize(),
            pqt.libelle or pqt.code or "—"
        ))

    # 7️⃣ Envoyer un mail à chaque pompier
    subject_user = f"Vos gardes – {mois_nom} – {equipe_nom}"
    personnels = db.scalars(select(Personnel).where(Personnel.id.in_(pers_map.keys()))).all()

    for p in personnels:
        if not p.email:
            continue
        fullname = f"{p.prenom} {p.nom}".strip()
        gardes_rows = sorted(pers_map[p.id], key=lambda r: r[0])
        html_user = build_validation_html(
            fullname, mois_nom, equipe_nom, validator_fullname, MAIL_FROM_NAME, gardes_rows
        )
        try:
            send_mail(p.email, subject_user, html_user)
        except Exception as e:
            print(f"[MAIL] ⚠️ Erreur envoi à {p.email}: {e}")

    return {
        "status": "ok",
        "validated_count": len(gardes),
        "notified_count": len(personnels) + 1,
        "equipe": equipe_nom,
        "mois": mois_nom,
    }


@router.post("/devalider-mois")
def devalider_mois(
    annee: int = Query(..., ge=1970, le=2100),
    mois: int = Query(..., ge=1, le=12),
    equipe_id: int | None = Query(None, description="Limiter la dévalidation à une équipe"),
    db: Session = Depends(get_session),
    user: PersonnelModel = Depends(get_current_user),
):
    """
    Dévalidation réservée à ADMIN/OFFICIER.
    """
    ensure_admin_off(user)

    q = select(Garde).where(_month_filter(annee, mois))
    if equipe_id is not None:
        q = q.where(Garde.equipe_id == equipe_id)

    gardes = db.execute(q).scalars().all()
    if not gardes:
        raise HTTPException(404, "Aucune garde trouvée pour ce périmètre")

    updated = 0
    for g in gardes:
        if g.validated:
            g.validated = False
            g.validated_at = None
            db.add(g)
            updated += 1
    db.commit()
    return {"status": "ok", "gardes_mises_a_jour": updated, "scope": {"annee": annee, "mois": mois, "equipe_id": equipe_id}}
