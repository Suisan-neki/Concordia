"""API I/O schemas."""
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field

from .models import (
    ActType,
    ActorType,
    ActorKeyRead,
    ComfortZone,
    MetricsSnapshotRead,
    SignatureRecordRead,
)


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

    model_config = ConfigDict(from_attributes=True)


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


class ClarifyRequestBody(BaseModel):
    actor_id: str
    actor_type: ActorType = ActorType.PATIENT
    preset: Optional[str] = None
    note: Optional[str] = None
    ask_later: bool = False


class RevisitRequestBody(BaseModel):
    actor_id: str
    actor_type: ActorType = ActorType.PATIENT
    note: Optional[str] = None


class ActorKeyIn(BaseModel):
    actor_id: str
    public_key_hex: str


class ActorKeyOut(ActorKeyRead):
    pass


class SignatureRecordOut(SignatureRecordRead):
    pass


class SignalEventIn(BaseModel):
    actor_id: str
    actor_type: ActorType = ActorType.PATIENT
    signal_type: str = Field(
        ...,
        description="one of: ack, question, praise",
        pattern="^(ack|question|praise)$",
    )
