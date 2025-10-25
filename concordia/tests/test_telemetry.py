from sqlmodel import Session, SQLModel, create_engine

from concordia.app.domain.models import (
    ActType,
    ComfortZone,
    UnderstandingEvent,
)
from concordia.app.services.telemetry import TelemetryService


def _session_factory():
    engine = create_engine("sqlite://", echo=False)
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def _add_event(session: Session, session_id: str, act_type: ActType):
    event = UnderstandingEvent(
        session_id=session_id,
        actor_id="tester",
        actor_type="doctor",
        act_type=act_type,
        payload={},
    )
    session.add(event)


def test_snapshot_assigns_calm_zone():
    session = _session_factory()
    with session:
        _add_event(session, "sess-calm", ActType.PRESENT)
        _add_event(session, "sess-calm", ActType.CLARIFY_REQUEST)
        _add_event(session, "sess-calm", ActType.RE_EXPLAIN)
        _add_event(session, "sess-calm", ActType.AGREE)
        session.commit()

        snapshot = TelemetryService(session).snapshot_for_session("sess-calm")
        assert snapshot.comfort_zone == ComfortZone.CALM


def test_snapshot_assigns_focus_zone_when_pending_dominates():
    session = _session_factory()
    with session:
        _add_event(session, "sess-focus", ActType.PRESENT)
        _add_event(session, "sess-focus", ActType.PENDING)
        _add_event(session, "sess-focus", ActType.PENDING)
        _add_event(session, "sess-focus", ActType.REVOKE)
        _add_event(session, "sess-focus", ActType.AGREE)
        session.commit()

        snapshot = TelemetryService(session).snapshot_for_session("sess-focus")
        assert snapshot.comfort_zone == ComfortZone.FOCUS
