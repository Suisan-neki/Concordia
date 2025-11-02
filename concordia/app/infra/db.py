"""Database session utilities."""
from contextlib import contextmanager
import os
from typing import Iterator, List, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel, Session

from ..domain.models import ActType
import time

# Read DATABASE_URL from environment; fall back to local SQLite for no‑Docker demo
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./concordia.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, echo=False, future=True, connect_args=connect_args)
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    class_=Session,
)


def ensure_acttype_enum_values(bind_engine: Optional[Engine] = None) -> None:
    """Add any new ActType enum values to the PostgreSQL enum."""
    target_engine = bind_engine or engine
    if "postgresql" not in target_engine.dialect.name:
        return

    with target_engine.begin() as conn:
        type_exists = conn.execute(
            text("SELECT 1 FROM pg_type WHERE typname = 'acttype'")
        ).first()
        if not type_exists:
            return  # tables (and enum) not created yet

        rows = conn.execute(
            text(
                """
                SELECT e.enumlabel
                FROM pg_type t
                JOIN pg_enum e ON t.oid = e.enumtypid
                WHERE t.typname = 'acttype'
                """
            )
        ).fetchall()
        existing: List[str] = [row[0] for row in rows]
        missing = [
            enum_value
            for enum_value in ActType._value2member_map_.keys()
            if enum_value not in existing
        ]
        for enum_value in missing:
            # Note: Can't use parameterized query with ADD VALUE IF NOT EXISTS
            # PostgreSQL doesn't support placeholders in enum alterations
            conn.execute(
                text(f"ALTER TYPE acttype ADD VALUE IF NOT EXISTS '{enum_value}'")
            )


def init_db() -> None:
    """Create tables if they do not exist and keep enums in sync.

    Retries on startup to wait for the database service in Docker.
    """
    attempts = 0
    last_err: Exception | None = None
    while attempts < 30:
        try:
            SQLModel.metadata.create_all(engine)
            ensure_acttype_enum_values(engine)
            return
        except Exception as exc:  # pragma: no cover
            last_err = exc
            attempts += 1
            print(f"[init_db] waiting for database... ({attempts}/30) {exc}")
            time.sleep(1)
    if last_err:
        raise last_err


@contextmanager
def get_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
