"""Celery task stubs for telemetry aggregation."""
from __future__ import annotations

import os

from celery import Celery

from concordia.app.infra.db import get_session
from concordia.app.services.telemetry import TelemetryService
from concordia.app.services.llm_assessment import LLMAssessmentService

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
CELERY_BACKEND_URL = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/1")

celery_app = Celery("concordia", broker=CELERY_BROKER_URL, backend=CELERY_BACKEND_URL)


@celery_app.task(name="metrics.calculate_for_session")
def calculate_metrics_for_session(session_id: str) -> str:
    """Aggregate Zero Pressure metrics for a completed session."""
    with get_session() as session:
        snapshot = TelemetryService(session).snapshot_for_session(session_id)
        return snapshot.id


@celery_app.task(name="metrics.assess_comprehension")
def assess_comprehension_quality(session_id: str) -> str:
    """Evaluate comprehension quality using LLM for a completed session."""
    with get_session() as session:
        assessment = LLMAssessmentService(session).assess_session(session_id)
        return assessment.id
