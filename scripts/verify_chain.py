#!/usr/bin/env python3
"""
Verify Concordia understanding event hashes for tamper detection.

Usage:
    python scripts/verify_chain.py --session-id sess-1
"""
from __future__ import annotations

import argparse
import os
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, select

from concordia.app.domain.merkle import canonical_bytes, compute_chain_hash
from concordia.app.domain.models import UnderstandingEvent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify Merkle chain integrity.")
    parser.add_argument(
        "--session-id",
        help="Optional session ID to restrict verification scope",
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg://concordia:concordia@localhost:5432/concordia",
        ),
        help="Database URL (SQLAlchemy compatible)",
    )
    return parser.parse_args()


def load_events(db: Session, session_id: str | None) -> list[UnderstandingEvent]:
    stmt = select(UnderstandingEvent).order_by(UnderstandingEvent.created_at.asc())
    if session_id:
        stmt = stmt.where(UnderstandingEvent.session_id == session_id)
    return list(db.exec(stmt))


def verify(events: list[UnderstandingEvent]) -> bool:
    ok = True
    prev_hash = None
    for event in events:
        payload = {
            "session_id": event.session_id,
            "actor_id": event.actor_id,
            "actor_type": event.actor_type.value,
            "act_type": event.act_type.value,
            "payload": event.payload,
            "artifact_hash": event.artifact_hash,
            "signature": event.signature,
            "created_at": event.created_at.isoformat(),
        }
        expected_hash = compute_chain_hash(payload, prev_hash)
        if event.prev_hash != prev_hash:
            print(
                f"[WARN] prev_hash mismatch at event {event.id}: "
                f"stored={event.prev_hash} expected={prev_hash}",
                file=sys.stderr,
            )
            ok = False
        if event.curr_hash != expected_hash:
            print(
                f"[WARN] curr_hash mismatch at event {event.id}: "
                f"stored={event.curr_hash} expected={expected_hash}",
                file=sys.stderr,
            )
            ok = False
        prev_hash = event.curr_hash
    if ok:
        print(
            f"Verified {len(events)} events; chain intact"
            + (f" for session {events[0].session_id}" if events else "")
        )
    return ok


def main() -> int:
    args = parse_args()
    engine = create_engine(args.database_url, future=True)
    SessionLocal = sessionmaker(bind=engine, class_=Session, autoflush=False)
    with SessionLocal() as db:
        events = load_events(db, args.session_id)
    if not events:
        print("No events found for verification.")
        return 0
    return 0 if verify(events) else 1


if __name__ == "__main__":
    raise SystemExit(main())
