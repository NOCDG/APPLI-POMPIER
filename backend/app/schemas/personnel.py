from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Literal
from datetime import date
from app.db.models import RoleEnum
from app.schemas.competence import CompetenceRead

# On garde le Literal pour la création / update (validation côté entrée)
StatutLiteral = Literal["pro", "volontaire", "double"]


class PersonnelBase(BaseModel):
    nom: str
    prenom: str
    grade: str
    email: EmailStr
    statut: StatutLiteral
    equipe_id: Optional[int] = None


class SetEquipePayload(BaseModel):
    equipe_id: Optional[int | None] = None


class PersonnelUpdate(BaseModel):
    nom: Optional[str] = None
    prenom: Optional[str] = None
    grade: Optional[str] = None
    email: Optional[EmailStr] = None
    statut: Optional[StatutLiteral] = None
    equipe_id: Optional[int | None] = None


class PersonnelCreate(PersonnelBase):
    roles: List[RoleEnum] = Field(default_factory=lambda: [RoleEnum.AGENT])


class PersonnelRead(BaseModel):
    """
    ⚠️ Ici on n'utilise PAS Literal ni l'Enum Python,
    on accepte juste une string, pour que Pydantic puisse
    sérialiser proprement l'Enum SQLAlchemy.
    """
    id: int
    nom: str
    prenom: str
    grade: str
    email: EmailStr
    statut: Optional[str] = None   # <= 🔥 clé : str, pas Literal
    equipe_id: Optional[int] = None

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


class PersonnelCompetenceDetail(PersonnelCompetenceRead):
    competence: CompetenceRead | None = None


class PersonnelCreateResponse(BaseModel):
    personnel: PersonnelRead
    temp_password: str
