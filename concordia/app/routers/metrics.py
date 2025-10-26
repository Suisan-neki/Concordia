"""Metrics endpoints for Zero Pressure telemetry."""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select

from ..deps import db_session
from ..domain.models import MetricsSnapshot
from ..domain.schemas import MetricsSnapshotOut, zone_label, zone_message
from ..services.telemetry import TelemetryService

router = APIRouter()


@router.get("/", response_model=List[MetricsSnapshotOut])
def list_metrics(session: Session = Depends(db_session)) -> List[MetricsSnapshotOut]:
    stmt = select(MetricsSnapshot).order_by(MetricsSnapshot.calculated_at.desc()).limit(50)
    return [_with_zone_copy(snapshot) for snapshot in session.exec(stmt).all()]



@router.get("/summary")
def metrics_summary(days: int = Query(7, ge=1, le=90), session: Session = Depends(db_session)):
    """Return averaged metrics and zone distribution over the past N days."""
    summary = TelemetryService(session).summary(days=days)
    return summary


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
    return _with_zone_copy(snapshot)


@router.post("/{session_id}", response_model=MetricsSnapshotOut, status_code=status.HTTP_201_CREATED)
def recalc_metrics(session_id: str, session: Session = Depends(db_session)) -> MetricsSnapshotOut:
    snapshot = TelemetryService(session).snapshot_for_session(session_id)
    return _with_zone_copy(snapshot)


def _with_zone_copy(snapshot: MetricsSnapshot) -> MetricsSnapshotOut:
    base = MetricsSnapshotOut.from_orm(snapshot)
    base.zone_label = zone_label(snapshot.comfort_zone)
    base.zone_message = zone_message(snapshot.comfort_zone)
    return base


@router.get("/summary")
def metrics_summary(days: int = Query(7, ge=1, le=90), session: Session = Depends(db_session)):
    """Return averaged metrics and zone distribution over the past N days."""
    summary = TelemetryService(session).summary(days=days)
    return summary
