from pydantic import BaseModel

class EquipeBase(BaseModel):
    code: str
    libelle: str
    couleur: str | None = "#888888"

class EquipeCreate(EquipeBase):
    pass

class EquipeUpdate(EquipeBase):
    pass  # on envoie les 3 champs pour un PUT complet

class EquipeRead(EquipeBase):
    id: int
    class Config:
        from_attributes = True
