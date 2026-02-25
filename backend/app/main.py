from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db.base import Base
from app.db.session import engine, SessionLocal
from app.api.routes import (
    auth,
    users_me,
    health,
    personnel,
    competences,
    equipes,
    piquets,
    gardes,
    affectations,
    indisponibilites,
    roles,
    password_reset,
)
from app.db.seed_holidays_fr import seed as seed_holidays

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from app.services.scheduler import send_monthly_reminder
    _scheduler = BackgroundScheduler(timezone="Europe/Paris")
    _scheduler.add_job(
        send_monthly_reminder,
        "cron",
        day=25,
        hour=8,
        minute=0,
        id="monthly_reminder",
        replace_existing=True,
    )
    _HAS_SCHEDULER = True
except ImportError:
    _HAS_SCHEDULER = False
    print("[WARN] apscheduler non installé — rappel mensuel désactivé. Lancez : pip install apscheduler")


app = FastAPI(title="FEUILLE_GARDE API")

# --- CORS ---
# On utilise directement la liste déjà parsée depuis settings.cors_list
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as s:
        seed_holidays(s)
    if _HAS_SCHEDULER:
        _scheduler.start()
        print("[INFO] Scheduler démarré — rappel mensuel programmé le 25 à 08h00.")


@app.on_event("shutdown")
def on_shutdown():
    if _HAS_SCHEDULER:
        _scheduler.shutdown(wait=False)


# --- Routes ---
app.include_router(health.router)
app.include_router(personnel.router)
app.include_router(competences.router)
app.include_router(equipes.router)
app.include_router(piquets.router)
app.include_router(gardes.router)
app.include_router(affectations.router)
app.include_router(indisponibilites.router)
app.include_router(auth.router)
app.include_router(users_me.router)
app.include_router(roles.router)
app.include_router(password_reset.router)
