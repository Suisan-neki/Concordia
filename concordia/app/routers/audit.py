"""Audit routes."""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from ..deps import db_session
from ..domain.models import AccessLog, AccessLogRead, SignatureRecord, SignatureRecordRead

router = APIRouter()


def _templates() -> Jinja2Templates:
    try:
        return Jinja2Templates(directory="concordia/app/templates")
    except AssertionError as exc:
        raise HTTPException(status_code=500, detail="Template engine not available") from exc


@router.get("/logs", response_model=List[AccessLogRead])
def audit_logs(
    actor_id: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    session: Session = Depends(db_session),
) -> List[AccessLogRead]:
    stmt = select(AccessLog).order_by(AccessLog.created_at.desc()).limit(limit)
    if actor_id:
        stmt = stmt.where(AccessLog.actor_id == actor_id)
    if action:
        stmt = stmt.where(AccessLog.action == action)
    logs = session.exec(stmt).all()
    return logs


@router.get("/logs/html", response_class=HTMLResponse)
def audit_logs_html(
    request: Request,
    actor_id: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    session: Session = Depends(db_session),
):
    logs = audit_logs(actor_id=actor_id, action=action, session=session)
    return _templates().TemplateResponse(
        "audit_logs.html",
        {
            "request": request,
            "logs": logs,
            "actor_id": actor_id or "",
            "action": action or "",
        },
    )


@router.get("/signatures", response_model=List[SignatureRecordRead])
def signature_records(
    session_id: Optional[str] = Query(None),
    session: Session = Depends(db_session),
):
    stmt = select(SignatureRecord).order_by(SignatureRecord.created_at.desc()).limit(200)
    if session_id:
        stmt = stmt.where(SignatureRecord.event_id.like(f"{session_id}%"))
    return session.exec(stmt).all()
