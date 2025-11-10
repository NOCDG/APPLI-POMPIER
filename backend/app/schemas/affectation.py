from datetime import datetime
from pydantic import BaseModel

class AffectationCreate(BaseModel):
  garde_id: int
  piquet_id: int
  personnel_id: int

class AffectationRead(AffectationCreate):
  id: int
  created_at: datetime
  class Config: from_attributes = True
