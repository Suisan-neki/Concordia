"""Understanding event routes."""
from typing import List

import base64
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from ..deps import db_session
from ..domain.merkle import canonical_bytes
from ..domain.models import (
    ActType,
    SignatureRecord,
    UnderstandingEvent,
    UnderstandingEventCreate,
)
from ..domain.schemas import UnderstandingEventIn, UnderstandingEventOut
from ..domain.sign import verify_signature
from ..infra.tsa import request_timestamp
from ..services.keys import KeyRegistry
from ..services.ledger import LedgerService
from ..services.telemetry import TelemetryService

router = APIRouter()

TELEMETRY_TRIGGER_ACTS = {
    ActType.AGREE,
    ActType.REAGREE,
    ActType.REVOKE,
}
SIGNATURE_REQUIRED_ACTS = {
    ActType.AGREE,
    ActType.REAGREE,
    ActType.REVOKE,
}


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
    signature_info: Optional[dict] = None
    if event_in.act_type in SIGNATURE_REQUIRED_ACTS:
        signature_info = _verify_signature_input(event_in, session)

    ledger = LedgerService(session)
    event = ledger.append(UnderstandingEventCreate(**event_in.model_dump()))

    if event.act_type in TELEMETRY_TRIGGER_ACTS:
        TelemetryService(session).snapshot_for_session(event.session_id)
    if event.act_type in SIGNATURE_REQUIRED_ACTS and signature_info:
        session.add(
            SignatureRecord(
                event_id=event.id,
                actor_id=event.actor_id,
                signature_hex=signature_info["signature_hex"],
                tsa_token=request_timestamp(bytes.fromhex(event.curr_hash or "00")),
            )
        )

    return event


def _verify_signature_input(event_in: UnderstandingEventIn, session: Session) -> dict:
    if not event_in.signature:
        raise HTTPException(status_code=400, detail="Signature required")
    key = KeyRegistry(session).get(event_in.actor_id)
    if not key:
        raise HTTPException(status_code=400, detail="Actor key not registered")

    try:
        signature_bytes = base64.b64decode(event_in.signature)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid signature encoding") from exc

    message = canonical_bytes(
        {
            "session_id": event_in.session_id,
            "actor_id": event_in.actor_id,
            "actor_type": event_in.actor_type.value,
            "act_type": event_in.act_type.value,
            "payload": event_in.payload,
            "artifact_hash": event_in.artifact_hash,
        }
    )
    try:
        verify_signature(bytes.fromhex(key.public_key_hex), message, signature_bytes)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Signature verification failed") from exc

    return {"signature_hex": event_in.signature}
