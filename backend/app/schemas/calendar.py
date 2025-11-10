from datetime import date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.db.models import Garde, Slot, Holiday


# Génère les gardes d'un mois (nuit en semaine, jour+nuit le week-end/ferié)


def ensure_month(session: Session, year: int, month: int) -> int:
    first = date(year, month, 1)
    # dernier jour du mois
    if month == 12:
        last = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last = date(year, month + 1, 1) - timedelta(days=1)


    # indexe les fériés
    holis = {h.date for h in session.scalars(select(Holiday).where(Holiday.date >= first, Holiday.date <= last)).all()}


    d = first
    created = 0
    while d <= last:
        is_weekend = d.weekday() >= 5 # 5=Samedi, 6=Dimanche
        is_holiday = d in holis
        # Nuit tous les jours
        created += _get_or_create_garde(session, d, Slot.NUIT, is_weekend, is_holiday)
        # Jour seulement si week-end ou férié
        if is_weekend or is_holiday:
            created += _get_or_create_garde(session, d, Slot.JOUR, is_weekend, is_holiday)
        d += timedelta(days=1)
    session.commit()
    return created




def _get_or_create_garde(session: Session, d: date, slot: Slot, is_weekend: bool, is_holiday: bool) -> int:
    existing = session.scalar(select(Garde).where(Garde.date == d, Garde.slot == slot))
    if existing:
        return 0
    g = Garde(date=d, slot=slot, is_weekend=is_weekend, is_holiday=is_holiday)
    session.add(g)
    return 1