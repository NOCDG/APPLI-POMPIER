# Remplissage rapide des jours fériés (ex : 2025). À compléter selon vos besoins.
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.db.models import Holiday

FERIES_2025 = {
    date(2025,1,1): "Jour de l'An",
    date(2025,4,21): "Lundi de Pâques",
    date(2025,5,1): "Fête du Travail",
    date(2025,5,8): "Victoire 1945",
    date(2025,5,29): "Ascension",
    date(2025,6,9): "Lundi de Pentecôte",
    date(2025,7,14): "Fête Nationale",
    date(2025,8,15): "Assomption",
    date(2025,11,1): "Toussaint",
    date(2025,11,11): "Armistice",
    date(2025,12,25): "Noël",
}

def seed(session: Session):
    for d, label in FERIES_2025.items():
        if not session.scalar(select(Holiday).where(Holiday.date == d)):
            session.add(Holiday(date=d, label=label))
    session.commit()
