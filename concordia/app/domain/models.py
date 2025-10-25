"""Domain models shared between API and persistence layers."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from uuid import uuid4

from pydantic import BaseModel, Field
from sqlalchemy import JSON
from sqlmodel import Column, Field as SQLField, SQLModel


class ActorType(str, Enum):
    DOCTOR = "doctor"
    PATIENT = "patient"
    AUDITOR = "auditor"


class ActType(str, Enum):
    PRESENT = "present"
    ACK_SUMMARY = "ack_summary"
    CLARIFY_REQUEST = "clarify_request"
    ASK_LATER = "ask_later"
    RE_EXPLAIN = "re_explain"
    AGREE = "agree"
    PENDING = "pending"
    REAGREE = "reagree"
    REVOKE = "revoke"
    RE_VIEW = "re_view"


class ComfortZone(str, Enum):
    CALM = "calm"
    OBSERVE = "observe"
    FOCUS = "focus"


class UnderstandingEvent(SQLModel, table=True):
    """Immutable understanding-event row stored in PostgreSQL."""

    __tablename__ = "understanding_events"

    id: str = SQLField(default_factory=lambda: str(uuid4()), primary_key=True, index=True)
    session_id: str = SQLField(index=True)
    actor_id: str = SQLField(index=True)
    actor_type: ActorType
    act_type: ActType
    payload: Dict[str, Any] = SQLField(
        sa_column=Column(JSON, nullable=False, server_default="{}")
    )
    artifact_hash: Optional[str] = SQLField(default=None, index=True)
    prev_hash: Optional[str] = SQLField(default=None)
    curr_hash: Optional[str] = SQLField(default=None, index=True)
    signature: Optional[str] = SQLField(default=None)
    created_at: datetime = SQLField(default_factory=datetime.utcnow, nullable=False, index=True)


class UnderstandingEventCreate(BaseModel):
    session_id: str
    actor_id: str
    actor_type: ActorType
    act_type: ActType
    payload: Dict[str, Any] = Field(default_factory=dict)
    artifact_hash: Optional[str] = None
    signature: Optional[str] = None


class UnderstandingEventRead(BaseModel):
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


class MetricsSnapshot(SQLModel, table=True):
    """Aggregated zero-pressure metrics per session."""

    __tablename__ = "metrics_snapshots"

    id: str = SQLField(default_factory=lambda: str(uuid4()), primary_key=True, index=True)
    session_id: str = SQLField(index=True)
    clarify_request_rate: float = SQLField(default=0.0)
    re_explain_rate: float = SQLField(default=0.0)
    post_view_rate: float = SQLField(default=0.0)
    pending_rate: float = SQLField(default=0.0)
    revoke_rate: float = SQLField(default=0.0)
    comfort_zone: ComfortZone = SQLField(default=ComfortZone.CALM)
    calculated_at: datetime = SQLField(default_factory=datetime.utcnow, nullable=False)


class MetricsSnapshotRead(BaseModel):
    id: str
    session_id: str
    clarify_request_rate: float
    re_explain_rate: float
    post_view_rate: float
    pending_rate: float
    revoke_rate: float
    comfort_zone: ComfortZone
    calculated_at: datetime

    class Config:
        from_attributes = True
