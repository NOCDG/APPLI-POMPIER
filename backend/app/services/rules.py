from datetime import timedelta
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.db.models import (
    Affectation, Garde, Slot, PiquetCompetence, PersonnelCompetence
)

# Règles :
# - Le personnel doit posséder toutes les compétences exigées par le piquet (non expirées à la date de garde).
# - Interdit les séquences : jour+nuit+jour et nuit+jour+nuit (sur 3 jours autour de la date visée).
# - Un agent ne peut pas être affecté deux fois sur la même garde.

def has_required_competences(session: Session, personnel_id: int, piquet_id: int, at_date) -> bool:
    # exigences du piquet
    req_comp_ids = [pc.competence_id for pc in session.scalars(select(PiquetCompetence).where(PiquetCompetence.piquet_id == piquet_id)).all()]
    if not req_comp_ids:
        return True
    pcs = session.scalars(
        select(PersonnelCompetence)
        .where(PersonnelCompetence.personnel_id == personnel_id)
        .where(PersonnelCompetence.competence_id.in_(req_comp_ids))
    ).all()
    ok_ids = set()
    for pc in pcs:
        # valide si pas d'expiration ou expiration >= date
        if pc.date_expiration is None or pc.date_expiration >= at_date:
            ok_ids.add(pc.competence_id)
    return set(req_comp_ids).issubset(ok_ids)

def violates_three_day_pattern(session: Session, personnel_id: int, target_garde: Garde) -> bool:
    d = target_garde.date
    # récupérer affectations sur J-1 et J+1
    prev = session.scalars(
        select(Affectation)
        .join(Garde, Affectation.garde_id == Garde.id)
        .where(Affectation.personnel_id == personnel_id)
        .where(Garde.date == (d - timedelta(days=1)))
    ).all()
    next_ = session.scalars(
        select(Affectation)
        .join(Garde, Affectation.garde_id == Garde.id)
        .where(Affectation.personnel_id == personnel_id)
        .where(Garde.date == (d + timedelta(days=1)))
    ).all()

    prev_slot = prev[0].garde.slot if prev else None
    next_slot = next_[0].garde.slot if next_ else None

    if prev_slot == Slot.JOUR and target_garde.slot == Slot.NUIT and next_slot == Slot.JOUR:
        return True
    if prev_slot == Slot.NUIT and target_garde.slot == Slot.JOUR and next_slot == Slot.NUIT:
        return True
    return False
