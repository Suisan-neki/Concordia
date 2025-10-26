"""Session management endpoints."""
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..deps import db_session
from ..domain.models import (
    ActType,
    ActorType,
    SessionRecord,
    SessionRecordRead,
    UnderstandingEventCreate,
)
from ..services.ledger import LedgerService

router = APIRouter()


class SessionCreate(BaseModel):
    id: str = Field(..., description="session identifier")
    doctor_id: str
    title: str
    artifact_hash: str


class SessionStatusUpdate(BaseModel):
    status: str


@router.post("/", response_model=SessionRecordRead, status_code=status.HTTP_201_CREATED)
def create_session(payload: SessionCreate, session: Session = Depends(db_session)):
    if session.get(SessionRecord, payload.id):
        raise HTTPException(status_code=400, detail="Session already exists")
    record = SessionRecord(
        id=payload.id,
        doctor_id=payload.doctor_id,
        title=payload.title,
        artifact_hash=payload.artifact_hash,
        created_at=datetime.utcnow(),
    )
    session.add(record)
    session.flush()
    session.refresh(record)
    LedgerService(session).append(
        UnderstandingEventCreate(
            session_id=record.id,
            actor_id=record.doctor_id,
            actor_type=ActorType.DOCTOR,
            act_type=ActType.PRESENT,
            artifact_hash=record.artifact_hash,
            payload={"title": record.title},
        )
    )
    return record


@router.get("/", response_model=List[SessionRecordRead])
def list_sessions(session: Session = Depends(db_session)):
    stmt = select(SessionRecord).order_by(SessionRecord.created_at.desc()).limit(100)
    return session.exec(stmt).all()


@router.get("/{session_id}", response_model=SessionRecordRead)
def get_session(session_id: str, session: Session = Depends(db_session)):
    record = session.get(SessionRecord, session_id)
    if not record:
        raise HTTPException(status_code=404, detail="Session not found")
    return record


@router.patch("/{session_id}", response_model=SessionRecordRead)
def update_status(
    session_id: str,
    payload: SessionStatusUpdate,
    session: Session = Depends(db_session),
):
    record = session.get(SessionRecord, session_id)
    if not record:
        raise HTTPException(status_code=404, detail="Session not found")
    record.status = payload.status
    session.add(record)
    session.flush()
    session.refresh(record)
    return record
