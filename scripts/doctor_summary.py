#!/usr/bin/env python3
"""CLI for viewing doctor-specific telemetry summary."""
from __future__ import annotations

import argparse
import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session

from concordia.app.services.telemetry import TelemetryService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Show doctor telemetry summary")
    parser.add_argument("doctor_id")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument(
        "--database-url",
        default="postgresql+psycopg://concordia:concordia@localhost:5432/concordia",
    )
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    engine = create_engine(args.database_url, future=True)
    SessionLocal = sessionmaker(bind=engine, class_=Session, autoflush=False)
    with SessionLocal() as db:
        summary = TelemetryService(db).doctor_summary(args.doctor_id, days=args.days)
    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        print(f"Doctor: {summary['doctor_id']} | Window: {summary['window_days']} days")
        print(f"Snapshots: {summary['snapshots']}")
        print("Averages:")
        for k, v in summary.get("averages", {}).items():
            print(f"  {k}: {v:.2f}")
        print("Zone counts:")
        for zone, count in summary.get("zone_counts", {}).items():
            print(f"  {zone}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
