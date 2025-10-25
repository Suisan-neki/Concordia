"""FastAPI application bootstrap for Concordia."""
from fastapi import FastAPI

from .routers import audit, auth, events, view


def create_app() -> FastAPI:
    app = FastAPI(title="Concordia API", version="0.1.0")

    app.include_router(events.router, prefix="/events", tags=["events"])
    app.include_router(auth.router, prefix="/auth", tags=["auth"])
    app.include_router(audit.router, prefix="/audit", tags=["audit"])
    app.include_router(view.router, prefix="/view", tags=["view"])

    return app


app = create_app()
