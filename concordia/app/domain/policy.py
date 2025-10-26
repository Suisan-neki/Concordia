"""ABAC policy helpers."""
from dataclasses import dataclass
from typing import Optional


@dataclass
class PolicyContext:
    subject_id: str
    role: str  # "doctor" or "patient"


def is_allowed(
    context: PolicyContext,
    action: str,
    resource_owner: Optional[str] = None,
) -> bool:
    if context.role == "doctor":
        return True
    if context.role == "patient":
        if action in {"submit_clarify", "revisit"}:
            return True
        if action == "view_timeline":
            return resource_owner is None or resource_owner == context.subject_id
    return False
