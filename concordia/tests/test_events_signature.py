import base64

from fastapi import HTTPException
from sqlmodel import Session, SQLModel, create_engine

from concordia.app.domain.merkle import canonical_bytes
from concordia.app.domain.models import ActorKey
from concordia.app.domain.schemas import UnderstandingEventIn
from concordia.app.domain.sign import generate_keypair, sign_message
from concordia.app.routers.events import _verify_signature_input


def setup_session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_verify_signature_succeeds():
    session = setup_session()
    private, public = generate_keypair()
    session.add(ActorKey(actor_id="pat-1", public_key_hex=public.hex()))
    session.commit()

    payload = {
        "session_id": "sess-10",
        "actor_id": "pat-1",
        "actor_type": "patient",
        "act_type": "agree",
        "payload": {"note": "ok"},
        "artifact_hash": None,
    }
    message = canonical_bytes(payload)
    signature = base64.b64encode(sign_message(private, message)).decode()

    event_in = UnderstandingEventIn(**payload, signature=signature)
    info = _verify_signature_input(event_in, session)
    assert info["signature_hex"] == signature


def test_verify_signature_rejects_invalid_signature():
    session = setup_session()
    _, public = generate_keypair()
    session.add(ActorKey(actor_id="pat-2", public_key_hex=public.hex()))
    session.commit()

    payload = {
        "session_id": "sess-11",
        "actor_id": "pat-2",
        "actor_type": "patient",
        "act_type": "agree",
        "payload": {},
        "artifact_hash": None,
    }
    bad_signature = base64.b64encode(b"wrong").decode()
    event_in = UnderstandingEventIn(**payload, signature=bad_signature)

    try:
        _verify_signature_input(event_in, session)
    except HTTPException as exc:
        assert exc.status_code == 400
    else:
        assert False, "Expected HTTPException"
