"""Understanding event routes."""
from typing import List

from fastapi import APIRouter, Depends, status
from sqlmodel import Session, select

from ..deps import db_session
from ..domain.models import UnderstandingEvent, UnderstandingEventCreate
from ..domain.schemas import UnderstandingEventIn, UnderstandingEventOut
from ..services.ledger import LedgerService

router = APIRouter()


@router.get("/", response_model=List[UnderstandingEventOut])
def list_events(session: Session = Depends(db_session)) -> List[UnderstandingEventOut]:
    stmt = select(UnderstandingEvent).order_by(UnderstandingEvent.created_at.desc()).limit(50)
    events = session.exec(stmt).all()
    return events


@router.post(
    "/",
    response_model=UnderstandingEventOut,
    status_code=status.HTTP_201_CREATED,
)
def append_event(
    event_in: UnderstandingEventIn,
    session: Session = Depends(db_session),
) -> UnderstandingEventOut:
    ledger = LedgerService(session)
    event = ledger.append(UnderstandingEventCreate(**event_in.model_dump()))
    return event
