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
    roles,
)
from app.db.seed_holidays_fr import seed as seed_holidays


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


# --- Routes ---
app.include_router(health.router)
app.include_router(personnel.router)
app.include_router(competences.router)
app.include_router(equipes.router)
app.include_router(piquets.router)
app.include_router(gardes.router)
app.include_router(affectations.router)
app.include_router(auth.router)
app.include_router(users_me.router)
app.include_router(roles.router)
