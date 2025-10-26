#!/usr/bin/env python3
"""Interactive CLI to simulate talker-listener sessions."""
from __future__ import annotations

import argparse
import random

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session

from concordia.app.domain.models import ActType, ActorType, UnderstandingEvent
from concordia.app.infra.db import ensure_acttype_enum_values
from concordia.app.services.telemetry import TelemetryService

PROMPTS = [
    "話し手> ",
    "聞き手> ",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Simulate a dialog session")
    parser.add_argument("session_id")
    parser.add_argument("--doctor-id", default="doc-cli")
    parser.add_argument("--patient-id", default="pat-cli")
    parser.add_argument("--database-url",
                        default="postgresql+psycopg://concordia:concordia@localhost:5432/concordia")
    return parser.parse_args()


def record_event(db: Session, session_id: str, actor_id: str, actor_type: ActorType,
                 act_type: ActType, payload: dict):
    event = UnderstandingEvent(
        session_id=session_id,
        actor_id=actor_id,
        actor_type=actor_type,
        act_type=act_type,
        payload=payload,
    )
    db.add(event)
    db.flush()
    db.refresh(event)
    return event


def phase_comment(summary: dict) -> str:
    counts = summary.get("zone_counts", {})
    if counts.get("focus", 0) > 0:
        return "集中して理解しようとしてくれています。要点を小分けにすると安心感が戻るかもしれません。"
    if counts.get("observe", 0) > 0:
        return "様子見モードです。質問のきっかけをもう一度提示してみましょう。"
    return "Calm が続いています。この調子で対話を続けましょう。"


def main() -> int:
    args = parse_args()
    engine = create_engine(args.database_url, future=True)
    ensure_acttype_enum_values(engine)
    SessionLocal = sessionmaker(bind=engine, class_=Session, autoflush=False)

    with SessionLocal() as db:
        print(f"Simulating session {args.session_id}. 空行で終了します。")
        while True:
            utter = input(PROMPTS[0])
            if not utter:
                break
            record_event(db, args.session_id, args.doctor_id, ActorType.DOCTOR,
                         ActType.PRESENT, {"text": utter})
            reply = input(PROMPTS[1])
            if not reply:
                break
            choice = random.choice([
                ActType.CLARIFY_REQUEST,
                ActType.SIGNAL_PRAISE,
                ActType.SIGNAL_QUESTION,
            ])
            record_event(db, args.session_id, args.patient_id, ActorType.PATIENT,
                         choice, {"text": reply})
            db.commit()

        snapshot = TelemetryService(db).snapshot_for_session(args.session_id)
        print(f"Comfort Zone: {snapshot.comfort_zone}")
        doctor_summary = TelemetryService(db).doctor_summary(args.doctor_id)
        print(phase_comment(doctor_summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
