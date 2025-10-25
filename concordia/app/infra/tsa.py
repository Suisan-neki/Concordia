"""TSA abstraction (RFC3161 placeholder)."""
from datetime import datetime


def request_timestamp(digest: bytes) -> dict:
    """Stub for RFC3161 client call."""
    return {"digest": digest.hex(), "timestamp": datetime.utcnow().isoformat()}
