"""Understanding event routes."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_events():
    return {"events": []}
