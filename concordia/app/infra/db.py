"""Database session utilities."""
from contextlib import contextmanager
from typing import Iterator, List, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel, Session

from ..domain.models import ActType

DATABASE_URL = "postgresql+psycopg://concordia:concordia@db:5432/concordia"

engine = create_engine(DATABASE_URL, echo=False, future=True)
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
            conn.execute(
                text("ALTER TYPE acttype ADD VALUE IF NOT EXISTS :value"),
                {"value": enum_value},
            )


def init_db() -> None:
    """Create tables if they do not exist and keep enums in sync."""
    SQLModel.metadata.create_all(engine)
    ensure_acttype_enum_values(engine)


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
