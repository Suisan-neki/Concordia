"""Simple ABAC evaluator with access logging."""
from fastapi import HTTPException, status
from sqlmodel import Session

from ..domain.models import AccessLog
from ..domain.policy import PolicyContext, is_allowed


class AccessEvaluator:
    def __init__(self, session: Session) -> None:
        self.session = session

    def enforce(
        self,
        context: PolicyContext,
        action: str,
        resource: str,
        resource_owner: str | None = None,
    ) -> None:
        allowed = is_allowed(context, action, resource_owner)
        self.session.add(
            AccessLog(
                actor_id=context.subject_id,
                role=context.role,
                action=action,
                resource=resource,
                allowed=allowed,
            )
        )
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied",
            )
