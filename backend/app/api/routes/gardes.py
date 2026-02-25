from datetime import date as date_type, datetime, timedelta
import calendar
from typing import List, Iterable

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, and_, func, exists, extract, or_
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.core.mailer import (
    send_mail, build_validation_html, MAIL_FROM_NAME,
    build_html_agent_team, build_html_agent_external,
)

from app.api.deps import get_session
from app.core.security import (
    get_current_user,
    ensure_can_validate_for_team,
    ensure_admin_off,
    ensure_can_modify_garde, require_roles
)
from app.db.models import (
    Garde, Holiday, Slot, Statut, Equipe,
    Piquet, PiquetCompetence,
    Personnel, PersonnelCompetence,
    Affectation, Personnel as PersonnelModel, PersonnelRole, RoleEnum,
    Indisponibilite,
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


def _easter(year: int) -> date_type:
    """Algorithme Meeus/Jones/Butcher — calcule le dimanche de Pâques."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = (h + l - 7 * m + 114) % 31 + 1
    return date_type(year, month, day)


_JF_LABELS = {
    (1,  1): "Jour de l'An",
    (5,  1): "Fête du Travail",
    (5,  8): "Victoire 1945",
    (7, 14): "Fête Nationale",
    (8, 15): "Assomption",
    (11, 1): "Toussaint",
    (11,11): "Armistice",
    (12,25): "Noël",
}

def _french_holidays(year: int) -> dict[date_type, str]:
    """Retourne {date: label} pour tous les jours fériés français de l'année."""
    easter = _easter(year)
    result: dict[date_type, str] = {}
    # Fêtes fixes
    for (m, d), label in _JF_LABELS.items():
        result[date_type(year, m, d)] = label
    # Fêtes mobiles (basées sur Pâques)
    result[easter]                        = "Dimanche de Pâques"
    result[easter + timedelta(days=1)]    = "Lundi de Pâques"
    result[easter + timedelta(days=39)]   = "Ascension"
    result[easter + timedelta(days=49)]   = "Dimanche de Pentecôte"
    result[easter + timedelta(days=50)]   = "Lundi de Pentecôte"
    return result


def _seed_french_holidays(db: Session, year: int) -> None:
    """Insère les jours fériés français pour l'année dans la table Holiday (idempotent)."""
    holidays = _french_holidays(year)
    for d, label in holidays.items():
        if not db.scalar(select(Holiday).where(Holiday.date == d)):
            db.add(Holiday(date=d, label=label))
    db.flush()


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
    # Semer les jours fériés français pour l'année (idempotent)
    _seed_french_holidays(db, year)

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


# ---------- POST /gardes/generate_year (TOUTE L'ANNÉE SANS ÉQUIPE) ----------
class GenerateYearRequest(BaseModel):
    year: int

@router.post("/generate_year")
@router.post("/generate_year/")
def generate_year(payload: GenerateYearRequest, db: Session = Depends(get_session)):
    """
    Crée toutes les gardes de l'année SANS équipe :
    - Semaine : NUIT
    - Week-end / JF : JOUR + NUIT
    Ignore les gardes déjà existantes (idempotent).
    """
    year = payload.year
    # Semer les jours fériés français pour l'année entière (idempotent)
    _seed_french_holidays(db, year)
    total_created = 0

    for month in range(1, 13):
        first = date_type(year, month, 1)
        last = date_type(year, month, calendar.monthrange(year, month)[1])
        d = first
        while d <= last:
            is_we = _is_weekend(d)
            is_hol = _is_holiday(db, d)
            slots = (Slot.JOUR, Slot.NUIT) if (is_we or is_hol) else (Slot.NUIT,)
            for slot in slots:
                if not db.scalar(select(Garde).where(Garde.date == d, Garde.slot == slot)):
                    db.add(Garde(date=d, slot=slot, is_weekend=is_we, is_holiday=is_hol, equipe_id=None))
                    total_created += 1
            d = date_type.fromordinal(d.toordinal() + 1)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(400, "Contrainte (date,slot) en base – doublon détecté.")
    return {"created": total_created, "year": year}


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
    search: str | None = Query(None, description="Filtre nom/prénom"),
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

    # 3) Base: personnels de la même équipe, actifs
    base = select(Personnel).where(
        Personnel.equipe_id == garde.equipe_id,
        Personnel.is_active.is_(True),
    )

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

    # 6) Filtre texte (nom ou prénom)
    if search and search.strip():
        q = f"%{search.strip().lower()}%"
        base = base.where(
            or_(
                func.lower(Personnel.nom).like(q),
                func.lower(Personnel.prenom).like(q),
            )
        )

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
    # tuple : (date, slot, piquet_label, statut_service)
    pers_map: dict[int, list[tuple[str, str, str, str]]] = {}
    for a in affs:
        g = garde_map.get(a.garde_id)
        if not g:
            continue
        pqt = piquet_map.get(a.piquet_id)
        pers_map.setdefault(a.personnel_id, []).append((
            g.date.strftime("%d/%m/%Y"),
            g.slot.name.capitalize(),
            pqt.libelle or pqt.code or "—",
            (a.statut_service or "volontaire").lower(),
        ))

    # 7️⃣ Envoyer un mail à chaque pompier
    subject_user = f"Vos gardes – {mois_nom} – {equipe_nom}"
    personnels = db.scalars(select(Personnel).where(Personnel.id.in_(pers_map.keys()))).all()

    # 7.5️⃣ Générer le PDF de la feuille de garde
    pdf_bytes: bytes | None = None
    pdf_filename: str | None = None
    try:
        from app.services.pdf_generator import generate_feuille_garde_pdf

        def _pdf_name(p) -> str:
            nom    = (p.nom    or "").strip()
            prenom = (p.prenom or "").strip()
            return f"{nom} {prenom[0]}." if prenom else nom

        # Noms des agents ayant des affectations
        pers_name_map = {p.id: _pdf_name(p) for p in personnels}

        # Tous les piquets (triés par position puis code), même ceux non utilisés
        pq_rows = db.scalars(
            select(Piquet).order_by(Piquet.position, Piquet.code)
        ).all()
        pdf_piquets: list[dict] = [
            {"id": p.id, "label": p.libelle or p.code or f"P{p.id}", "is_astreinte": bool(p.is_astreinte)}
            for p in pq_rows
        ]

        # aff_map : {garde_id: {piquet_id: agent_fullname}}
        pdf_aff_map: dict[int, dict[int, str]] = {}
        for a in affs:
            pdf_aff_map.setdefault(a.garde_id, {})[a.piquet_id] = (
                pers_name_map.get(a.personnel_id, "?")
            )

        # Membres actifs de l'équipe
        team_members = db.scalars(
            select(Personnel).where(
                Personnel.equipe_id == equipe_id,
                Personnel.is_active.is_(True),
            )
        ).all()
        team_ids = {p.id for p in team_members}
        team_names = {
            p.id: _pdf_name(p)
            for p in team_members
        }

        # Indisponibilités
        indispos = db.scalars(
            select(Indisponibilite).where(Indisponibilite.garde_id.in_(garde_ids))
        ).all()
        indispo_by_garde: dict[int, set[int]] = {}
        for i in indispos:
            indispo_by_garde.setdefault(i.garde_id, set()).add(i.personnel_id)

        # Affectés par garde
        assigned_by_garde: dict[int, set[int]] = {}
        for a in affs:
            assigned_by_garde.setdefault(a.garde_id, set()).add(a.personnel_id)

        pdf_non_aff_map: dict[int, list[str]] = {}
        pdf_indispo_map: dict[int, list[str]] = {}
        for g in gardes:
            assigned = assigned_by_garde.get(g.id, set())
            indispo_ids = indispo_by_garde.get(g.id, set())
            pdf_non_aff_map[g.id] = sorted(
                team_names[pid] for pid in team_ids
                if pid not in assigned and pid not in indispo_ids
            )
            pdf_indispo_map[g.id] = sorted(
                team_names[pid] for pid in team_ids & indispo_ids
            )

        garde_data_for_pdf = [
            {
                "id": g.id,
                "date": g.date,
                "slot": g.slot.name if hasattr(g.slot, "name") else str(g.slot),
            }
            for g in sorted(gardes, key=lambda g: (
                g.date,
                0 if (g.slot.name if hasattr(g.slot, "name") else str(g.slot)) == "JOUR" else 1,
            ))
        ]

        pdf_bytes = generate_feuille_garde_pdf(
            equipe_label=equipe_nom,
            mois_label=mois_nom,
            gardes=garde_data_for_pdf,
            piquets=pdf_piquets,
            aff_map=pdf_aff_map,
            non_aff_map=pdf_non_aff_map,
            indispo_map=pdf_indispo_map,
        )
        safe_equipe = equipe_nom.replace(" ", "_").replace("/", "-")
        safe_mois = mois_nom.replace(" ", "_")
        pdf_filename = f"feuille_garde_{safe_equipe}_{safe_mois}.pdf"

    except Exception as _pdf_err:
        import traceback
        print(f"[PDF] ❌ Erreur génération PDF: {_pdf_err}")
        traceback.print_exc()

    print(f"[PDF] pdf_bytes={'OK (' + str(len(pdf_bytes)) + ' bytes)' if pdf_bytes else 'NONE — PJ non générée'}")

    for p in personnels:
        if not p.email:
            continue

        all_rows = pers_map[p.id]  # list[tuple[date, slot, piquet, statut_service]]

        if p.statut == Statut.PRO:
            # PRO pur : jamais de mail
            print(f"[MAIL] ⏭ {p.email} ignoré (statut PRO)")
            continue
        elif p.statut == Statut.DOUBLE:
            # DOUBLE : mail uniquement si au moins une garde en mode volontaire
            vol_rows = [r for r in all_rows if r[3] == "volontaire"]
            if not vol_rows:
                print(f"[MAIL] ⏭ {p.email} ignoré (DOUBLE sans garde volontaire)")
                continue
            mail_rows = vol_rows
        else:
            # VOLONTAIRE : toutes ses gardes
            mail_rows = all_rows

        fullname = f"{p.prenom} {p.nom}".strip()
        # Tronquer le 4e élément (statut_service) — le template attend (date, slot, piquet)
        gardes_rows = sorted([(r[0], r[1], r[2]) for r in mail_rows], key=lambda r: (r[0], 0 if r[1].upper() == "JOUR" else 1))

        is_team = p.equipe_id == equipe_id
        if is_team:
            html_user = build_html_agent_team(fullname, mois_nom, equipe_nom, gardes_rows)
            attach = (
                [(pdf_filename, pdf_bytes, "application/pdf")]
                if pdf_bytes and pdf_filename else None
            )
        else:
            html_user = build_html_agent_external(fullname, mois_nom, equipe_nom, gardes_rows)
            attach = None
        print(f"[MAIL] → {p.email} | statut={p.statut.value} | gardes={len(gardes_rows)} | pj={'OUI' if attach else 'NON'}")
        try:
            send_mail(p.email, subject_user, html_user, db=db, attachments=attach)
        except Exception as e:
            print(f"[MAIL] ❌ Erreur envoi à {p.email}: {e}")

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
