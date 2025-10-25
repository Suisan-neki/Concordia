"""Ledger service handles append-only understanding events."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Session, select

from ..domain.merkle import compute_chain_hash
from ..domain.models import UnderstandingEvent, UnderstandingEventCreate


class LedgerService:
    """Append-only ledger backed by SQLModel and Merkle chaining."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def append(self, event_in: UnderstandingEventCreate) -> UnderstandingEvent:
        prev_hash = self._latest_hash()
        timestamp = datetime.utcnow()

        event = UnderstandingEvent(
            session_id=event_in.session_id,
            actor_id=event_in.actor_id,
            actor_type=event_in.actor_type,
            act_type=event_in.act_type,
            payload=event_in.payload,
            artifact_hash=event_in.artifact_hash,
            signature=event_in.signature,
            prev_hash=prev_hash,
            created_at=timestamp,
        )

        event.curr_hash = compute_chain_hash(
            {
                "session_id": event.session_id,
                "actor_id": event.actor_id,
                "actor_type": event.actor_type,
                "act_type": event.act_type,
                "payload": event.payload,
                "artifact_hash": event.artifact_hash,
                "signature": event.signature,
                "created_at": event.created_at.isoformat(),
            },
            prev_hash,
        )

        self.session.add(event)
        self.session.flush()
        self.session.refresh(event)
        return event

    def _latest_hash(self) -> Optional[str]:
        stmt = select(UnderstandingEvent.curr_hash).order_by(
            UnderstandingEvent.created_at.desc()
        ).limit(1)
        result = self.session.exec(stmt).first()
        return result
