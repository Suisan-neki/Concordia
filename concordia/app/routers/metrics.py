"""Metrics endpoints for Zero Pressure telemetry."""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from ..deps import db_session
from ..domain.models import MetricsSnapshot
from ..domain.schemas import MetricsSnapshotOut
from ..services.telemetry import TelemetryService

router = APIRouter()


@router.get("/", response_model=List[MetricsSnapshotOut])
def list_metrics(session: Session = Depends(db_session)) -> List[MetricsSnapshotOut]:
    stmt = select(MetricsSnapshot).order_by(MetricsSnapshot.calculated_at.desc()).limit(50)
    return session.exec(stmt).all()


@router.get("/{session_id}", response_model=MetricsSnapshotOut)
def get_latest_metrics(session_id: str, session: Session = Depends(db_session)) -> MetricsSnapshotOut:
    stmt = (
        select(MetricsSnapshot)
        .where(MetricsSnapshot.session_id == session_id)
        .order_by(MetricsSnapshot.calculated_at.desc())
        .limit(1)
    )
    snapshot = session.exec(stmt).first()
    if not snapshot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Snapshot not found")
    return snapshot


@router.post("/{session_id}", response_model=MetricsSnapshotOut, status_code=status.HTTP_201_CREATED)
def recalc_metrics(session_id: str, session: Session = Depends(db_session)) -> MetricsSnapshotOut:
    snapshot = TelemetryService(session).snapshot_for_session(session_id)
    return snapshot
