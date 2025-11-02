"""FastAPI application bootstrap for Concordia."""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .infra.db import init_db
from .routers import audit, auth, debug, events, metrics, sessions, view, lab


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Concordia API", version="0.1.0", lifespan=lifespan)

    app.include_router(events.router, prefix="/events", tags=["events"])
    app.include_router(sessions.router, prefix="/sessions", tags=["sessions"])
    app.include_router(auth.router, prefix="/auth", tags=["auth"])
    app.include_router(audit.router, prefix="/audit", tags=["audit"])
    app.include_router(debug.router, prefix="/debug", tags=["debug"])
    app.include_router(view.router, prefix="/view", tags=["view"])
    app.include_router(metrics.router, prefix="/metrics", tags=["metrics"])
    app.include_router(lab.router, tags=["consent-lab"])  # /lab endpoints

    return app


app = create_app()
