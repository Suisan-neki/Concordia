"""Dependency injection utilities."""
from collections.abc import Generator

from sqlmodel import Session

from .infra.db import get_session


def db_session() -> Generator[Session, None, None]:
    """Provide a scoped DB session to FastAPI endpoints."""
    with get_session() as session:
        yield session
