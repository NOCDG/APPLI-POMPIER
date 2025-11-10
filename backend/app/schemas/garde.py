# app/schemas/garde.py
from datetime import date, datetime
from typing import Literal, Optional, Union
from pydantic import BaseModel, field_serializer
from app.db.models import Slot as SlotEnum  # <-- importe l'Enum Python/SQLAlchemy

SlotLiteral = Literal["JOUR", "NUIT"]

class GardeBase(BaseModel):
    date: date
    # pour les payloads d'entrée on garde le Literal (le client envoie des strings)
    slot: SlotLiteral
    is_weekend: bool = False
    is_holiday: bool = False
    equipe_id: int

class GardeRead(BaseModel):
    id: int
    date: date
    slot: Union[SlotEnum, SlotLiteral]
    equipe_id: int | None
    is_weekend: bool
    is_holiday: bool
    model_config = {"from_attributes": True}
    @field_serializer("slot")
    def serialize_slot(self, v): return getattr(v, "value", v)
    validated: bool
    validated_at: Optional[datetime] = None


class GenerateMonthRequest(BaseModel):
    year: int
    month: int

class GardeCreate(BaseModel):
    date: date
    slot: SlotLiteral

class AssignTeamRequest(BaseModel):
    date: date
    slot: SlotLiteral
    equipe_id: int

class GenerateMonthAllRequest(BaseModel):
    year: int
    month: int
