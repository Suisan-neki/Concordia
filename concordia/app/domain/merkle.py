"""Merkle chain utilities."""
import hashlib
from dataclasses import dataclass
from typing import Optional


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
