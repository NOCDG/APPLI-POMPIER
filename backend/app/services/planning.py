# app/services/planning.py
from datetime import date, timedelta
from typing import Iterable
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, or_
from app.db.models import (
    Garde, Slot, Piquet, PiquetCompetence, PersonnelCompetence, Affectation
)

def day_slots(d: date) -> list[tuple[date, Slot]]:
    # ordre chronologique: JOUR (si existe), puis NUIT
    return [(d, Slot.JOUR), (d, Slot.NUIT)]

def prev_next_slots(target_date: date, target_slot: Slot) -> list[tuple[date, Slot]]:
    # renvoie les 4 slots entourant (2 avant, 2 après) pour tester les séries
    # calendrier: en semaine → uniquement NUIT ; we/jour férié → JOUR+NUIT
    # on va juste regarder J/N du jour -1, jour, jour +1
    seq: list[tuple[date, Slot]] = []
    for delta in [-1, 0, 1]:
        d = target_date + timedelta(days=delta)
        seq.extend(day_slots(d))
    # garde l’ordre et enlève les doublons
    seen = set(); out=[]
    for x in seq:
        if x not in seen:
            seen.add(x); out.append(x)
    return out

def has_all_required_competences(
    db: Session, personnel_id: int, piquet_id: int, on_date: date
) -> tuple[bool, list[str]]:
    """Vérifie que le personnel possède toutes les compétences exigées (non expirées)."""
    reqs = db.scalars(select(PiquetCompetence).where(PiquetCompetence.piquet_id==piquet_id)).all()
    if not reqs:
        return True, []
    required_ids = {r.competence_id for r in reqs}
    pcs = db.scalars(
        select(PersonnelCompetence)
        .where(PersonnelCompetence.personnel_id==personnel_id)
        .where(PersonnelCompetence.competence_id.in_(required_ids))
    ).all()
    have = set()
    reasons: list[str] = []
    for pc in pcs:
        # expiration: si définie et < on_date → invalide
        if pc.date_expiration and pc.date_expiration < on_date:
            reasons.append(f"compétence {pc.competence.code} expirée le {pc.date_expiration}")
            continue
        have.add(pc.competence_id)
    missing = required_ids - have
    if missing:
        # libellés manquants
        miss_labels = [db.get(PiquetCompetence, next(iter([c for c in reqs if c.competence_id==m])))
                       for m in missing]
        return False, [f"compétence manquante id={m}" for m in missing]
    return True, reasons

def would_make_three_in_a_row(
    db: Session, personnel_id: int, garde: Garde, piquet: Piquet
) -> bool:
    """Retourne True si affecter cette garde ferait une série de 3 gardes consécutives
    sans 24h off ; les astreintes ne sont pas comptées."""
    if piquet.is_astreinte:
        return False  # astreinte ignorée

    # récupère toutes les affectations du personnel sur les slots alentours (J-1, J, J+1)
    slots = prev_next_slots(garde.date, garde.slot)
    # map (date, slot) -> garde_id
    garde_map: dict[tuple[date, Slot], int] = {}
    existing_gardes = db.scalars(
        select(Garde).where(
            or_(*[
                and_(Garde.date==d, Garde.slot==s) for (d,s) in slots
            ])
        )
    ).all()
    for g in existing_gardes:
        garde_map[(g.date, g.slot)] = g.id

    # affectations existantes du personnel (hors astreinte)
    affs = db.scalars(
        select(Affectation)
        .where(Affectation.personnel_id==personnel_id)
        .where(Affectation.garde_id.in_(list(garde_map.values())))
    ).all()
    occupied: set[tuple[date, Slot]] = set()
    for a in affs:
        pq: Piquet = db.get(Piquet, a.piquet_id)
        if pq and pq.is_astreinte:
            continue
        g = db.get(Garde, a.garde_id)
        occupied.add((g.date, g.slot))

    # ajoute la garde candidate
    occupied.add((garde.date, garde.slot))

    # détecte une série de 3 sans trou 24h (i.e., sans journée complète vide entre)
    # on regarde des motifs: (J,N,J) ou (N,J,N) sur 2 jours glissants.
    def has(b: tuple[date, Slot]) -> bool: return b in occupied
    for delta in [-1, 0]:
        d = garde.date + timedelta(days=delta)
        if has((d, Slot.JOUR)) and has((d, Slot.NUIT)) and has((d+timedelta(days=1), Slot.JOUR)):
            return True  # J N J
        if has((d, Slot.NUIT)) and has((d+timedelta(days=1), Slot.JOUR)) and has((d+timedelta(days=1), Slot.NUIT)):
            return True  # N J N
    return False
