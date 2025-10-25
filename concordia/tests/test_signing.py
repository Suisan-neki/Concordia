from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from concordia.app.domain.sign import generate_keypair, sign_message
from concordia.app.infra.tsa import request_timestamp


def test_ed25519_sign_and_verify():
    private_bytes, public_bytes = generate_keypair()
    message = b"zero pressure"
    signature = sign_message(private_bytes, message)

    # Should not raise when verifying
    Ed25519PublicKey.from_public_bytes(public_bytes).verify(signature, message)


def test_tsa_stub_returns_iso_timestamp():
    resp = request_timestamp(b"\x01\x02")
    assert resp["digest"] == "0102"
    assert "timestamp" in resp
