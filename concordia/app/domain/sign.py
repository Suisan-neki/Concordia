"""Ed25519 signing helper."""
from typing import Tuple

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, PublicFormat, NoEncryption


def generate_keypair() -> Tuple[bytes, bytes]:
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    return (
        private_key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption()),
        public_key.public_bytes(Encoding.Raw, PublicFormat.Raw),
    )


def sign_message(private_bytes: bytes, message: bytes) -> bytes:
    private_key = Ed25519PrivateKey.from_private_bytes(private_bytes)
    return private_key.sign(message)
