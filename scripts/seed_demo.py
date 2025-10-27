#!/usr/bin/env python3
"""Seed Concordia DB with demo sessions and events."""
from __future__ import annotations

import argparse
import random
from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session

from concordia.app.domain.models import ActType, ActorType, SessionRecord, UnderstandingEventCreate
from concordia.app.services.ledger import LedgerService
from concordia.app.services.telemetry import TelemetryService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed DB with demo sessions/events")
    parser.add_argument("--sessions", type=int, default=3)
    parser.add_argument(
        "--database-url",
        default="postgresql+psycopg://concordia:concordia@db:5432/concordia",
    )
    return parser.parse_args()


def ensure_session(db: Session, session_id: str, doctor_id: str, artifact_hash: str) -> None:
    if db.get(SessionRecord, session_id):
        return
    record = SessionRecord(
        id=session_id,
        doctor_id=doctor_id,
        title=f"Demo Session {session_id}",
        artifact_hash=artifact_hash,
        created_at=datetime.utcnow() - timedelta(days=random.randint(0, 5)),
    )
    db.add(record)
    db.flush()


def create_demo_events(db: Session, session_id: str, patient_id: str, doctor_id: str):
    ledger = LedgerService(db)
    base_time = datetime.utcnow() - timedelta(hours=2)
    events = [
        (doctor_id, ActorType.DOCTOR, ActType.PRESENT, {"step": "intro"}),
        (patient_id, ActorType.PATIENT, ActType.CLARIFY_REQUEST, {"preset": "details"}),
        (doctor_id, ActorType.DOCTOR, ActType.RE_EXPLAIN, {"note": "diagram"}),
        (patient_id, ActorType.PATIENT, ActType.RE_VIEW, {}),
        (patient_id, ActorType.PATIENT, ActType.AGREE, {}),
    ]
    for offset, (actor_id, actor_type, act_type, payload) in enumerate(events):
        event = UnderstandingEventCreate(
            session_id=session_id,
            actor_id=actor_id,
            actor_type=actor_type,
            act_type=act_type,
            payload=payload,
        )
        inserted = ledger.append(event)
        inserted.created_at = base_time + timedelta(minutes=offset * 10)
        db.add(inserted)


def main() -> int:
    args = parse_args()
    engine = create_engine(args.database_url, future=True)
    SessionLocal = sessionmaker(bind=engine, class_=Session, autoflush=False)
    with SessionLocal() as db:
        for idx in range(1, args.sessions + 1):
            session_id = f"demo-{idx}"
            doctor_id = f"doc-{idx}"
            patient_id = f"pat-{idx}"
            ensure_session(db, session_id, doctor_id, f"hash-{idx:04}")
            create_demo_events(db, session_id, patient_id, doctor_id)
            TelemetryService(db).snapshot_for_session(session_id)
        db.commit()
    print(f"Seeded {args.sessions} demo sessions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
