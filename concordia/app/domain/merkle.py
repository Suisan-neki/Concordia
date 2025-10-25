"""Merkle chain utilities."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping, Optional


@dataclass
class MerkleNode:
    value: bytes
    prev_hash: Optional[bytes]

    @property
    def hash(self) -> bytes:
        hasher = hashlib.sha256()
        hasher.update(self.value)
        if self.prev_hash:
            hasher.update(self.prev_hash)
        return hasher.digest()


def canonical_bytes(data: Mapping[str, Any]) -> bytes:
    """Serialize data with deterministic ordering for hashing."""
    return json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")


def compute_chain_hash(payload: Mapping[str, Any], prev_hash_hex: Optional[str]) -> str:
    """Return the new chain hash from payload + previous hash."""
    node = MerkleNode(
        value=canonical_bytes(payload),
        prev_hash=bytes.fromhex(prev_hash_hex) if prev_hash_hex else None,
    )
    return node.hash.hex()
