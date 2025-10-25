"""API I/O schemas."""
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from .models import ActType, ActorType, ComfortZone, MetricsSnapshotRead


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
    zone_label: str | None = None
    zone_message: str | None = None


def zone_label(zone: ComfortZone) -> str:
    return {
        ComfortZone.CALM: "Calm",
        ComfortZone.OBSERVE: "Observe",
        ComfortZone.FOCUS: "Focus",
    }[zone]


def zone_message(zone: ComfortZone) -> str:
    return {
        ComfortZone.CALM: "選択肢が十分あり、落ち着いた空気です",
        ComfortZone.OBSERVE: "少し様子を見て改善点を探りましょう",
        ComfortZone.FOCUS: "再説明やUIの調整を検討するタイミングです",
    }[zone]
