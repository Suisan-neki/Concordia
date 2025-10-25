"""Core Pydantic domain models."""
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ActorType(str, Enum):
    DOCTOR = "doctor"
    PATIENT = "patient"
    AUDITOR = "auditor"


class UnderstandingAct(BaseModel):
    id: str
    session_id: str
    actor: ActorType
    act_type: str
    payload: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
