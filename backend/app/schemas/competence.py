from pydantic import BaseModel

class CompetenceBase(BaseModel):
    code: str
    libelle: str

class CompetenceCreate(CompetenceBase):
    pass

class CompetenceRead(CompetenceBase):
    id: int
    class Config:
        from_attributes = True
