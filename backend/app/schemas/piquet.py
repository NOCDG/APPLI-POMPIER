# app/schemas/piquet.py
from pydantic import BaseModel
from typing import List, Optional

class CompetenceMini(BaseModel):
    id: int
    code: str
    libelle: str

    class Config:
        from_attributes = True

class PiquetBase(BaseModel):
    code: str
    libelle: str

class PiquetCreate(PiquetBase):
    exigences: List[int] = []  # liste de competence_id

class PiquetRead(PiquetBase):
    id: int
    # On renvoie les exigences "riches" pour simplifier le front
    exigences: List[CompetenceMini] = []
    is_astreinte: bool = False

    class Config:
        from_attributes = True
