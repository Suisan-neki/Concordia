"""Debug dashboard endpoints."""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from ..deps import db_session
from ..domain.models import AccessLog, MetricsSnapshot, SignatureRecord
from ..services.telemetry import TelemetryService

router = APIRouter()
templates = Jinja2Templates(directory="concordia/app/templates")


@router.get("/overview", response_class=HTMLResponse)
def debug_overview(request: Request, session: Session = Depends(db_session)):
    summary = TelemetryService(session).summary(days=7)
    metrics = (
        session.exec(
            select(MetricsSnapshot).order_by(MetricsSnapshot.calculated_at.desc()).limit(15)
        ).all()
    )
    access_logs = (
        session.exec(select(AccessLog).order_by(AccessLog.created_at.desc()).limit(20)).all()
    )
    signatures = (
        session.exec(select(SignatureRecord).order_by(SignatureRecord.created_at.desc()).limit(10)).all()
    )
    return templates.TemplateResponse(
        "debug_overview.html",
        {
            "request": request,
            "summary": summary,
            "metrics": metrics,
            "access_logs": access_logs,
            "signatures": signatures,
        },
    )
