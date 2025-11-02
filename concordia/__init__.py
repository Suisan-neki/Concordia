"""
Concordia: A small, general-purpose toolkit for recording, sealing,
and verifying session-level agreements ("consent" in the broad sense)
with tamper-evident chaining and export/verification helpers.

This package is intentionally domain-agnostic. The medical app in
`SecHack365_project/` can use Concordia as an integration layer,
but Concordia itself does not depend on medical context.
"""

__all__ = [
    "SessionCapsule",
    "SessionEvent",
]

from .capsule import SessionCapsule, SessionEvent

__version__ = "0.1.0"

