"""Telemetry aggregation service for Zero Pressure metrics."""
from __future__ import annotations

from datetime import datetime
from typing import Iterable

from sqlmodel import Session, select

from ..domain.models import ActType, MetricsSnapshot, UnderstandingEvent


class TelemetryService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def snapshot_for_session(self, session_id: str) -> MetricsSnapshot:
        events = self.session.exec(
            select(UnderstandingEvent).where(UnderstandingEvent.session_id == session_id)
        ).all()
        total_events = max(len(events), 1)

        clarify = self._count(events, {ActType.CLARIFY_REQUEST, ActType.ASK_LATER})
        re_explain = self._count(events, {ActType.RE_EXPLAIN})
        post_view = self._count(events, {ActType.RE_VIEW})
        pending = self._count(events, {ActType.PENDING})
        revoke = self._count(events, {ActType.REVOKE})

        snapshot = MetricsSnapshot(
            session_id=session_id,
            clarify_request_rate=clarify / total_events,
            re_explain_rate=re_explain / total_events,
            post_view_rate=post_view / total_events,
            pending_rate=pending / total_events,
            revoke_rate=revoke / total_events,
            comfort_index=self._comfort_index(
                clarify / total_events,
                post_view / total_events,
                re_explain / total_events,
                pending / total_events,
            ),
            calculated_at=datetime.utcnow(),
        )
        self.session.add(snapshot)
        self.session.flush()
        self.session.refresh(snapshot)
        return snapshot

    @staticmethod
    def _count(events: Iterable[UnderstandingEvent], targets: set[ActType]) -> int:
        return sum(1 for event in events if event.act_type in targets)

    @staticmethod
    def _comfort_index(
        clarify_rate: float,
        post_view_rate: float,
        re_explain_rate: float,
        pending_rate: float,
    ) -> float:
        base = 0.45 * clarify_rate + 0.35 * post_view_rate + 0.2 * re_explain_rate
        penalty = 0.15 * pending_rate
        return max(0.0, min(1.0, base - penalty))
