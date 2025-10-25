"""API I/O schemas."""
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from .models import ActType, ActorType, MetricsSnapshotRead


class ChallengeRequest(BaseModel):
    user_id: str


class ChallengeResponse(BaseModel):
    challenge: str


class UnderstandingEventIn(BaseModel):
    session_id: str
    actor_id: str
    actor_type: ActorType
    act_type: ActType
    payload: Dict[str, Any] = Field(default_factory=dict)
    artifact_hash: Optional[str] = None
    signature: Optional[str] = None


class UnderstandingEventOut(BaseModel):
    id: str
    session_id: str
    actor_id: str
    actor_type: ActorType
    act_type: ActType
    payload: Dict[str, Any]
    artifact_hash: Optional[str]
    prev_hash: Optional[str]
    curr_hash: Optional[str]
    signature: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class MetricsSnapshotOut(MetricsSnapshotRead):
    pass
