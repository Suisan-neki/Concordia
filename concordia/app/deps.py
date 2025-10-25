"""Dependency injection utilities."""
from collections.abc import Generator

from .infra.db import get_session


def db_session() -> Generator:
    """Provide a scoped DB session to FastAPI endpoints."""
    with get_session() as session:
        yield session
