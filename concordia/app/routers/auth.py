"""Authentication / key management routes."""
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from ..deps import db_session
from ..domain.schemas import ActorKeyIn, ActorKeyOut
from ..services.keys import KeyRegistry

router = APIRouter()


@router.post("/keys", response_model=ActorKeyOut)
def register_key(payload: ActorKeyIn, session: Session = Depends(db_session)):
    key = KeyRegistry(session).register(payload.actor_id, payload.public_key_hex)
    return key


@router.get("/keys/{actor_id}", response_model=ActorKeyOut)
def get_key(actor_id: str, session: Session = Depends(db_session)):
    key = KeyRegistry(session).get(actor_id)
    if not key:
        raise HTTPException(status_code=404, detail="Key not found")
    return key


@router.get("/keys", response_model=list[ActorKeyOut])
def list_keys(session: Session = Depends(db_session)):
    return KeyRegistry(session).list()
