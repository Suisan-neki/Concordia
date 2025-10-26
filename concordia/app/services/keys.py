"""Actor key registry helpers."""
from sqlmodel import Session, select

from ..domain.models import ActorKey


class KeyRegistry:
    def __init__(self, session: Session) -> None:
        self.session = session

    def register(self, actor_id: str, public_key_hex: str) -> ActorKey:
        key = self.session.get(ActorKey, actor_id)
        if key:
            key.public_key_hex = public_key_hex
        else:
            key = ActorKey(actor_id=actor_id, public_key_hex=public_key_hex)
            self.session.add(key)
        self.session.flush()
        self.session.refresh(key)
        return key

    def get(self, actor_id: str) -> ActorKey | None:
        return self.session.get(ActorKey, actor_id)

    def list(self) -> list[ActorKey]:
        stmt = select(ActorKey).order_by(ActorKey.actor_id)
        return list(self.session.exec(stmt).all())
