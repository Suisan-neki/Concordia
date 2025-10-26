"""Patient/physician view routes."""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from ..deps import db_session
from ..domain.models import (
    ActType,
    ActorType,
    SessionRecord,
    UnderstandingEvent,
    UnderstandingEventCreate,
)
from ..domain.schemas import (
    ClarifyRequestBody,
    RevisitRequestBody,
    UnderstandingEventOut,
)
from ..domain.policy import PolicyContext
from ..services.abac import AccessEvaluator
from ..services.ledger import LedgerService
from ..services.telemetry import TelemetryService

router = APIRouter()


def _templates() -> Jinja2Templates:
    try:
        return Jinja2Templates(directory="concordia/app/templates")
    except AssertionError as exc:
        raise HTTPException(status_code=500, detail="Template engine not available") from exc


@router.get(
    "/sessions/{session_id}/timeline",
    response_model=List[UnderstandingEventOut],
)
def session_timeline(
    session_id: str,
    viewer_id: str,
    viewer_role: ActorType,
    session: Session = Depends(db_session),
):
    AccessEvaluator(session).enforce(
        PolicyContext(subject_id=viewer_id, role=viewer_role.value),
        action="view_timeline",
        resource=session_id,
    )
    stmt = (
        select(UnderstandingEvent)
        .where(UnderstandingEvent.session_id == session_id)
        .order_by(UnderstandingEvent.created_at.asc())
    )
    return session.exec(stmt).all()


@router.get(
    "/sessions/{session_id}/timeline/html",
    response_class=HTMLResponse,
)
def session_timeline_html(
    request: Request,
    session_id: str,
    viewer_id: str,
    session: Session = Depends(db_session),
):
    session_record = session.get(SessionRecord, session_id)
    events = session_timeline(
        session_id=session_id,
        viewer_id=viewer_id,
        viewer_role=ActorType.PATIENT,
        session=session,
    )
    metrics = (
        TelemetryService(session).snapshot_for_session(session_id)
        if events
        else None
    )
    return _templates().TemplateResponse(
        "timeline.html",
        {
            "request": request,
            "session_id": session_id,
            "session_title": session_record.title if session_record else session_id,
            "artifact_hash": session_record.artifact_hash if session_record else "",
            "viewer_id": viewer_id,
            "events": events,
            "metrics": metrics,
        },
    )


@router.post(
    "/sessions/{session_id}/clarify",
    response_model=UnderstandingEventOut,
    status_code=status.HTTP_201_CREATED,
)
def post_clarify(
    session_id: str,
    body: ClarifyRequestBody,
    session: Session = Depends(db_session),
):
    """Record a clarify request or ask-later intent."""
    AccessEvaluator(session).enforce(
        PolicyContext(subject_id=body.actor_id, role=body.actor_type.value),
        action="submit_clarify",
        resource=session_id,
    )
    act_type = ActType.ASK_LATER if body.ask_later else ActType.CLARIFY_REQUEST
    payload = {"preset": body.preset, "note": body.note}
    event = UnderstandingEventCreate(
        session_id=session_id,
        actor_id=body.actor_id,
        actor_type=body.actor_type,
        act_type=act_type,
        payload={k: v for k, v in payload.items() if v},
    )
    return LedgerService(session).append(event)


@router.post(
    "/sessions/{session_id}/revisit",
    response_model=UnderstandingEventOut,
    status_code=status.HTTP_201_CREATED,
)
def post_revisit(
    session_id: str,
    body: RevisitRequestBody,
    session: Session = Depends(db_session),
):
    """Record a re_view event when patients revisit later."""
    AccessEvaluator(session).enforce(
        PolicyContext(subject_id=body.actor_id, role=body.actor_type.value),
        action="revisit",
        resource=session_id,
    )
    event = UnderstandingEventCreate(
        session_id=session_id,
        actor_id=body.actor_id,
        actor_type=body.actor_type,
        act_type=ActType.RE_VIEW,
        payload={"note": body.note} if body.note else {},
    )
    return LedgerService(session).append(event)
