from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import date
from app.db.models import RoleEnum

class PersonnelBase(BaseModel):
    nom: str
    prenom: str
    grade: str
    email: EmailStr
    statut: str  # "pro" | "volontaire"
    equipe_id: Optional[int] = None

class SetEquipePayload(BaseModel):
    equipe_id: Optional[int | None] = None

class PersonnelUpdate(BaseModel):
    nom: Optional[str] = None
    prenom: Optional[str] = None
    grade: Optional[str] = None
    email: Optional[EmailStr] = None
    statut: Optional[str] = None  # "pro" | "volontaire"
    equipe_id: Optional[int | None] = None

class PersonnelCreate(PersonnelBase):
    roles: List[RoleEnum] = [RoleEnum.AGENT]
    pass

class PersonnelRead(PersonnelBase):
    id: int
    class Config:
        from_attributes = True

class PersonnelCompetenceCreate(BaseModel):
    competence_id: int
    date_obtention: Optional[date] = None
    date_expiration: Optional[date] = None

class PersonnelCompetenceRead(PersonnelCompetenceCreate):
    id: int
    class Config:
        from_attributes = True

from app.schemas.competence import CompetenceRead

class PersonnelCompetenceDetail(PersonnelCompetenceRead):
    competence: CompetenceRead | None = None  # pour renvoyer code/libellé

class PersonnelCreateResponse(BaseModel):
    personnel: PersonnelRead
    temp_password: str
