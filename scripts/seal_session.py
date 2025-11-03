#!/usr/bin/env python3
"""
Seal a session into a verifiable capsule snapshot (JSON).

Outputs a JSON object with:
- session_id, events_count, first_event_at, last_event_at,
- last_curr_hash (chain tip),
- tsa_token (stubbed RFC3161-like from infra.tsa),

Usage:
    python scripts/seal_session.py --session-id <id> [--database-url ...]
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, select

from concordia.app.domain.models import UnderstandingEvent
from concordia.app.infra.tsa import request_timestamp


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Seal a session into a capsule JSON")
    p.add_argument("--session-id", required=True)
    p.add_argument(
        "--database-url",
        default=os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg://concordia:concordia@localhost:5432/concordia",
        ),
    )
    return p.parse_args()


def load_events(db: Session, session_id: str) -> list[UnderstandingEvent]:
    stmt = (
        select(UnderstandingEvent)
        .where(UnderstandingEvent.session_id == session_id)
        .order_by(UnderstandingEvent.created_at.asc())
    )
    return list(db.exec(stmt))


def main() -> int:
    args = parse_args()
    engine = create_engine(args.database_url, future=True)
    SessionLocal = sessionmaker(bind=engine, class_=Session, autoflush=False)

    with SessionLocal() as db:
        events = load_events(db, args.session_id)

    if not events:
        print(json.dumps({"session_id": args.session_id, "events_count": 0}))
        return 0

    first_ts: datetime = events[0].created_at
    last_ts: datetime = events[-1].created_at
    last_hash = events[-1].curr_hash

    capsule = {
        "session_id": args.session_id,
        "events_count": len(events),
        "first_event_at": first_ts.isoformat(),
        "last_event_at": last_ts.isoformat(),
        "last_curr_hash": last_hash,
        "tsa_token": request_timestamp(bytes.fromhex(last_hash or "00")),
    }
    print(json.dumps(capsule, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

