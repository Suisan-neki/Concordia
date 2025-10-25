"""Persistent storage adapters."""
from pathlib import Path

STORAGE_ROOT = Path("/tmp/concordia-storage")


def write_blob(name: str, data: bytes) -> Path:
    STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
    target = STORAGE_ROOT / name
    target.write_bytes(data)
    return target
