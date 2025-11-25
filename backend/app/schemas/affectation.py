from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel

# statut utilisé pour CETTE garde
StatutServiceLiteral = Literal["pro", "volontaire"]


class AffectationCreate(BaseModel):
    garde_id: int
    piquet_id: int
    personnel_id: int
    # 🆕 pour les doubles statuts : pro ou volontaire
    statut_service: Optional[StatutServiceLiteral] = None


class AffectationRead(BaseModel):
    id: int
    garde_id: int
    piquet_id: int
    personnel_id: int
    created_at: datetime
    # sortie JSON : on accepte une simple string
    statut_service: Optional[str] = None

    class Config:
        from_attributes = True
