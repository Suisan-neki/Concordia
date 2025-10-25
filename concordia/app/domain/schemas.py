"""API I/O schemas."""
from pydantic import BaseModel


class ChallengeRequest(BaseModel):
    user_id: str


class ChallengeResponse(BaseModel):
    challenge: str
