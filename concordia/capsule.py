from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _canonical_json(obj: Any) -> bytes:
    """Return canonicalized JSON bytes (sorted keys, fixed separators, UTF-8).

    signature fields and precomputed hashes should be excluded by caller
    from the dict they pass here.
    """
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass
class SessionEvent:
    """An atomic, ordered fact in a session.

    domain is free-form (e.g., "ui", "ehr", "consent").
    kind is the action (e.g., "view", "edit", "agree", "clarify").
    payload holds minimal necessary details for later verification.
    """

    domain: str
    kind: str
    actor: str
    payload: Dict[str, Any] = field(default_factory=dict)
    at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))
    prev_hash: Optional[str] = None
    curr_hash: Optional[str] = None
    signature: Optional[str] = None  # base64/hex string, set by caller (optional)

    def to_hash_material(self) -> Dict[str, Any]:
        # exclude non-hashed fields (curr_hash, signature)
        base = {
            "domain": self.domain,
            "kind": self.kind,
            "actor": self.actor,
            "payload": self.payload,
            "at": self.at,
            "prev_hash": self.prev_hash,
        }
        return base

    def compute_hash(self) -> str:
        self.curr_hash = _sha256_hex(_canonical_json(self.to_hash_material()))
        return self.curr_hash


@dataclass
class SessionCapsule:
    """Tamper-evident chain of session events with minimal metadata.

    This is domain-agnostic. For medical usage, map medical fields into
    event payloads and session metadata via adapters.
    """

    session_id: str
    subject_id: Optional[str] = None  # e.g., patient/user id
    context: Dict[str, Any] = field(default_factory=dict)  # free-form
    events: List[SessionEvent] = field(default_factory=list)
    sealed: bool = False
    root: Optional[str] = None  # hash of the last event at seal time

    def append(self, event: SessionEvent) -> None:
        if self.sealed:
            raise RuntimeError("capsule already sealed")

        prev = self.events[-1].curr_hash if self.events else None
        event.prev_hash = prev
        event.compute_hash()
        self.events.append(event)

    def seal(self, attestation: Optional[Dict[str, Any]] = None) -> None:
        """Seal the capsule to prevent further mutation.

        Optionally attach an attestation dict (e.g., signatures, timestamps).
        """
        if self.sealed:
            return
        self.root = self.events[-1].curr_hash if self.events else _sha256_hex(b"")
        if attestation:
            # store in context under reserved key
            self.context.setdefault("attestations", []).append(attestation)
        self.sealed = True

    def verify(self) -> Dict[str, Any]:
        """Recompute all hashes and verify linkage and root integrity.

        Returns a dict with `ok: bool` and minimal diagnostics.
        """
        problems: List[str] = []
        prev: Optional[str] = None
        last: Optional[str] = None

        for idx, ev in enumerate(self.events):
            if ev.prev_hash != prev:
                problems.append(f"event[{idx}].prev_hash mismatch")
            h = _sha256_hex(_canonical_json(ev.to_hash_material()))
            if ev.curr_hash != h:
                problems.append(f"event[{idx}].curr_hash mismatch")
            prev = ev.curr_hash
            last = ev.curr_hash

        if self.sealed:
            if self.root != (last or _sha256_hex(b"")):
                problems.append("root mismatch")

        return {"ok": len(problems) == 0, "problems": problems}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "subject_id": self.subject_id,
            "context": self.context,
            "sealed": self.sealed,
            "root": self.root,
            "events": [
                {
                    "domain": e.domain,
                    "kind": e.kind,
                    "actor": e.actor,
                    "payload": e.payload,
                    "at": e.at,
                    "prev_hash": e.prev_hash,
                    "curr_hash": e.curr_hash,
                    "signature": e.signature,
                }
                for e in self.events
            ],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionCapsule":
        cap = cls(
            session_id=data["session_id"],
            subject_id=data.get("subject_id"),
            context=data.get("context", {}),
        )
        for raw in data.get("events", []):
            ev = SessionEvent(
                domain=raw["domain"],
                kind=raw["kind"],
                actor=raw["actor"],
                payload=raw.get("payload", {}),
                at=raw.get("at"),
            )
            ev.prev_hash = raw.get("prev_hash")
            ev.curr_hash = raw.get("curr_hash")
            ev.signature = raw.get("signature")
            cap.events.append(ev)
        cap.sealed = data.get("sealed", False)
        cap.root = data.get("root")
        return cap

