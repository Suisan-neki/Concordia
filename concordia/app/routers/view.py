"""Patient/physician view routes."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/sessions/{session_id}")
async def get_session_view(session_id: str):
    return {"session_id": session_id, "steps": []}
