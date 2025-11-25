from datetime import date, datetime
from enum import Enum as PyEnum
from typing import Optional
import enum

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    JSON,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Statut(PyEnum):
    PRO = "pro"
    VOLONTAIRE = "volontaire"
    DOUBLE = "double"


class Slot(PyEnum):
    JOUR = "JOUR"
    NUIT = "NUIT"


class Equipe(Base):
    __tablename__ = "equipes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    libelle: Mapped[str] = mapped_column(String(50))
    couleur: Mapped[str] = mapped_column(String(10), default="#888888")

    # Pas de cascade ici: supprimer une équipe ne doit pas supprimer les personnels
    personnels: Mapped[list["Personnel"]] = relationship(
        "Personnel", back_populates="equipe"
    )


class Personnel(Base):
    __tablename__ = "personnels"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    nom: Mapped[str]
    prenom: Mapped[str]
    grade: Mapped[str]
    email: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    statut: Mapped[Statut] = mapped_column(
        SAEnum(Statut, values_callable=lambda e: [i.value for i in e])
    )
    hashed_password: Mapped[str | None] = mapped_column(String(255), default=None)
    is_active: Mapped[bool] = mapped_column(default=True)

    roles = relationship("PersonnelRole", back_populates="personnel", cascade="all, delete-orphan")
    # ⚠️ un seul champ equipe_id, avec SET NULL si l'équipe est supprimée
    equipe_id: Mapped[int | None] = mapped_column(
        ForeignKey("equipes.id", ondelete="SET NULL"), nullable=True, index=True
    )
    equipe: Mapped["Equipe"] = relationship("Equipe", back_populates="personnels")

    # ✅ cascade pour supprimer automatiquement les liaisons lors d'une suppression de personnel
    competences: Mapped[list["PersonnelCompetence"]] = relationship(
        "PersonnelCompetence",
        back_populates="personnel",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # Si tu utilises des affectations liées à un personnel, garde la relation et la cascade côté ORM
    affectations: Mapped[list["Affectation"]] = relationship(
        "Affectation",
        back_populates="personnel",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    


class Competence(Base):
    __tablename__ = "competences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    libelle: Mapped[str] = mapped_column(String(120))


class PersonnelCompetence(Base):
    __tablename__ = "personnel_competences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # ✅ CASCADE quand on supprime le personnel
    personnel_id: Mapped[int] = mapped_column(
        ForeignKey("personnels.id", ondelete="CASCADE"), index=True
    )
    competence_id: Mapped[int] = mapped_column(
        ForeignKey("competences.id"), index=True
    )
    # ✅ types "date" (et pas datetime) puisque la colonne est Date
    date_obtention: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_expiration: Mapped[date | None] = mapped_column(Date, nullable=True)

    personnel: Mapped["Personnel"] = relationship("Personnel", back_populates="competences")
    competence: Mapped["Competence"] = relationship("Competence")

    __table_args__ = (
        UniqueConstraint("personnel_id", "competence_id", name="uq_person_comp"),
    )


class PiquetCompetence(Base):
    __tablename__ = "piquet_competences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    piquet_id: Mapped[int] = mapped_column(
        ForeignKey("piquets.id", ondelete="CASCADE"), index=True
    )
    competence_id: Mapped[int] = mapped_column(
        ForeignKey("competences.id"), index=True
    )

    piquet: Mapped["Piquet"] = relationship("Piquet", back_populates="exigences")
    competence: Mapped["Competence"] = relationship("Competence")

    __table_args__ = (
        UniqueConstraint("piquet_id", "competence_id", name="uq_piquet_comp"),
    )


class Holiday(Base):
    __tablename__ = "holidays"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[Date] = mapped_column(Date, unique=True, index=True)
    label: Mapped[str] = mapped_column(String(120))

class Affectation(Base):
    __tablename__ = "affectations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    garde_id: Mapped[int] = mapped_column(
        ForeignKey("gardes.id", ondelete="CASCADE"), index=True
    )
    piquet_id: Mapped[int] = mapped_column(
        ForeignKey("piquets.id", ondelete="CASCADE"), index=True
    )
    # ✅ si on supprime un personnel, on supprime ses affectations
    personnel_id: Mapped[int] = mapped_column(
        ForeignKey("personnels.id", ondelete="CASCADE"), index=True
    )

    # 🆕 statut utilisé pour cette affectation : "pro" ou "volontaire"
    statut_service: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    garde: Mapped["Garde"] = relationship("Garde")
    piquet: Mapped["Piquet"] = relationship("Piquet")
    personnel: Mapped["Personnel"] = relationship("Personnel", back_populates="affectations")

    __table_args__ = (
        UniqueConstraint("garde_id", "piquet_id", name="uq_garde_piquet"),
        UniqueConstraint("garde_id", "personnel_id", name="uq_garde_personnel"),
    )

class Piquet(Base):
    __tablename__ = "piquets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    libelle: Mapped[str] = mapped_column(String(120))
    is_astreinte: Mapped[bool] = mapped_column(Boolean, default=False)

    # NEW: ordre d'affichage
    position: Mapped[int] = mapped_column(Integer, default=0, index=True)

    exigences = relationship(
        "PiquetCompetence", back_populates="piquet", cascade="all, delete-orphan"
    )

class Garde(Base):
    __tablename__ = "gardes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[Date] = mapped_column(Date, index=True)
    slot: Mapped[Slot] = mapped_column(SAEnum(Slot))
    is_weekend: Mapped[bool] = mapped_column(Boolean, default=False)
    is_holiday: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (
        UniqueConstraint("date", "slot", name="uq_date_slot_team"),
    )
    equipe_id: Mapped[int | None] = mapped_column(ForeignKey("equipes.id"), nullable=True)
    equipe: Mapped["Equipe"] = relationship("Equipe")

    validated: Mapped[bool] = mapped_column(Boolean, default=False)
    validated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

class RoleEnum(str, enum.Enum):
    ADMIN = "ADMIN"
    OFFICIER = "OFFICIER"
    OPE = "OPE"
    CHEF_EQUIPE = "CHEF_EQUIPE"
    ADJ_CHEF_EQUIPE = "ADJ_CHEF_EQUIPE"
    AGENT = "AGENT"

class PersonnelRole(Base):
    __tablename__ = "personnel_roles"
    id: Mapped[int] = mapped_column(primary_key=True)
    personnel_id: Mapped[int] = mapped_column(ForeignKey("personnels.id", ondelete="CASCADE"))
    role: Mapped[RoleEnum] = mapped_column(SAEnum(RoleEnum, name="roleenum"))
    personnel = relationship("Personnel", back_populates="roles")
    __table_args__ = (UniqueConstraint("personnel_id", "role", name="uq_personnel_role"),)

try:
    # si Postgres
    from sqlalchemy.dialects.postgresql import JSONB as SAJSON
except Exception:
    from sqlalchemy import JSON as SAJSON

class AppConfig(Base):
    __tablename__ = "app_config"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    data: Mapped[dict] = mapped_column(SAJSON, default=dict)

class AppSetting(Base):
    __tablename__ = "app_settings"
    key: Mapped[str]   = mapped_column(String(100), primary_key=True)
    value: Mapped[dict | str | int | bool | None] = mapped_column(JSON, nullable=True)