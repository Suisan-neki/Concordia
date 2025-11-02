"""Domain models shared between API and persistence layers."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import JSON, Enum as SQLAlchemyEnum
from sqlalchemy.types import TypeDecorator, String
from sqlmodel import Column, Field as SQLField, SQLModel


class EnumValueType(TypeDecorator):
    """Ensures enum values are stored as lowercase strings in the database."""
    impl = SQLAlchemyEnum
    cache_ok = True

    def __init__(self, enum_class, name, **kwargs):
        self.enum_class = enum_class
        self.enum_name = name
        super().__init__(enum_class, name=name, **kwargs)

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        # Handle Enum instances
        if hasattr(value, 'value'):
            return str(value.value).lower()
        # Handle string values
        if isinstance(value, str):
            return value.lower()
        # Handle other types
        return str(value).lower() if value else None

    def process_result_value(self, value, dialect):
        if not value:
            return None
        # If already an enum, return as is
        if isinstance(value, self.enum_class):
            return value
        # Try to find enum member by value
        value_str = str(value).lower()
        for member in self.enum_class:
            if member.value.lower() == value_str:
                return member
        # Fallback: return the value as-is if no match
        return value


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
    SIGNAL_ACK = "signal_ack"  # 「伝わっています」
    SIGNAL_QUESTION = "signal_question"  # 「質問したい！」
    SIGNAL_PRAISE = "signal_praise"  # 「今の説明はいいね！」
    MITIGATE = "mitigate"  # セキュリティ技術を当てて脅威を和らげる
    MITIGATE_REMOVE = "mitigate_remove"  # 適用を外す（UI整合用）


class ComfortZone(str, Enum):
    CALM = "calm"
    OBSERVE = "observe"
    FOCUS = "focus"


class ComprehensionQuality(str, Enum):
    """Understanding quality assessment by LLM."""
    HIGH = "high"  # 十分に理解している
    MODERATE = "moderate"  # 一部不明点あり、再説明が有効
    LOW = "low"  # 理解不足、構造的な再説明が必要


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

    model_config = ConfigDict(from_attributes=True)


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

    model_config = ConfigDict(from_attributes=True)


class AccessLog(SQLModel, table=True):
    __tablename__ = "access_logs"

    id: str = SQLField(default_factory=lambda: str(uuid4()), primary_key=True, index=True)
    actor_id: str = SQLField(index=True)
    role: str
    action: str
    resource: str
    allowed: bool = SQLField(default=True)
    created_at: datetime = SQLField(default_factory=datetime.utcnow, nullable=False, index=True)


class AccessLogRead(BaseModel):
    id: str
    actor_id: str
    role: str
    action: str
    resource: str
    allowed: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ActorKey(SQLModel, table=True):
    """Registered public keys for Ed25519 signatures."""

    __tablename__ = "actor_keys"

    actor_id: str = SQLField(primary_key=True)
    public_key_hex: str
    created_at: datetime = SQLField(default_factory=datetime.utcnow, nullable=False)


class ActorKeyRead(BaseModel):
    actor_id: str
    public_key_hex: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SignatureRecord(SQLModel, table=True):
    """Signature verification + TSA token recorded per event."""

    __tablename__ = "signature_records"

    id: str = SQLField(default_factory=lambda: str(uuid4()), primary_key=True, index=True)
    event_id: str = SQLField(index=True)
    actor_id: str = SQLField(index=True)
    signature_hex: str
    tsa_token: Dict[str, Any] = SQLField(sa_column=Column(JSON, nullable=False, server_default="{}"))
    created_at: datetime = SQLField(default_factory=datetime.utcnow, nullable=False)


class SignatureRecordRead(BaseModel):
    id: str
    event_id: str
    actor_id: str
    signature_hex: str
    tsa_token: Dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SessionRecord(SQLModel, table=True):
    __tablename__ = "sessions"

    id: str = SQLField(primary_key=True, index=True)
    doctor_id: str = SQLField(index=True)
    title: str
    artifact_hash: str
    created_at: datetime = SQLField(default_factory=datetime.utcnow, nullable=False)
    status: str = SQLField(default="active", index=True)


class SessionRecordRead(BaseModel):
    id: str
    doctor_id: str
    title: str
    artifact_hash: str
    created_at: datetime
    status: str

    model_config = ConfigDict(from_attributes=True)


class ComprehensionAssessment(SQLModel, table=True):
    """LLM-based comprehension quality assessment per session."""

    __tablename__ = "comprehension_assessments"

    id: str = SQLField(default_factory=lambda: str(uuid4()), primary_key=True, index=True)
    session_id: str = SQLField(index=True)
    overall_quality: ComprehensionQuality = SQLField(default=ComprehensionQuality.MODERATE)
    agreement_readiness: str = SQLField(default="")  # 「合意への準備度」を言葉で表現（数値化しない）
    reasoning: str = SQLField(default="")  # LLM の判定理由（肯定的な表現で）
    suggestions: str = SQLField(default="")  # より良い対話のための肯定的な提案
    assessment_metadata: Dict[str, Any] = SQLField(
        sa_column=Column(JSON, nullable=False, server_default="{}")
    )  # プロンプト・モデル・バージョン等
    calculated_at: datetime = SQLField(default_factory=datetime.utcnow, nullable=False, index=True)


class ComprehensionAssessmentRead(BaseModel):
    id: str
    session_id: str
    overall_quality: ComprehensionQuality
    agreement_readiness: str
    reasoning: str
    suggestions: str
    assessment_metadata: Dict[str, Any]
    calculated_at: datetime

    model_config = ConfigDict(from_attributes=True)
