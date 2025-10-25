"""Telemetry aggregation service for Zero Pressure metrics."""
from __future__ import annotations

from datetime import datetime
from typing import Iterable

from sqlmodel import Session, select

from ..domain.models import ActType, ComfortZone, MetricsSnapshot, UnderstandingEvent


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

        zone = self._zone_from_rates(
            clarify / total_events,
            post_view / total_events,
            re_explain / total_events,
            pending / total_events,
            revoke / total_events,
        )

        snapshot = MetricsSnapshot(
            session_id=session_id,
            clarify_request_rate=clarify / total_events,
            re_explain_rate=re_explain / total_events,
            post_view_rate=post_view / total_events,
            pending_rate=pending / total_events,
            revoke_rate=revoke / total_events,
            comfort_zone=zone,
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
    def _zone_from_rates(
        clarify_rate: float,
        post_view_rate: float,
        re_explain_rate: float,
        pending_rate: float,
        revoke_rate: float,
    ) -> ComfortZone:
        """Classify the current session into Calm / Observe / Focus zones.

        Heuristics (PoC):
        - score >= 0.15 => Calm
        - score >= -0.05 => Observe
        - else Focus
        """

        positive = 0.4 * clarify_rate + 0.35 * post_view_rate + 0.25 * re_explain_rate
        penalties = 0.2 * pending_rate + 0.1 * revoke_rate
        score = positive - penalties

        if score >= 0.15:
            return ComfortZone.CALM
        if score >= -0.05:
            return ComfortZone.OBSERVE
        return ComfortZone.FOCUS
