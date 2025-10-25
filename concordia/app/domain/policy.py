"""ABAC policy helpers."""
from dataclasses import dataclass


@dataclass
class PolicyContext:
    role: str
    purpose: str
    sensitivity: str


def is_allowed(context: PolicyContext, action: str) -> bool:
    """Placeholder hook for oso/casbin evaluation."""
    # TODO: integrate actual policy engine
    return True
