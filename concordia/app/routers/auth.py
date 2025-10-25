"""Authentication routes."""
from fastapi import APIRouter

router = APIRouter()


@router.post("/challenge")
async def create_challenge():
    return {"challenge": "demo"}
