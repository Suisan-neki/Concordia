"""Audit routes."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/logs")
async def audit_logs():
    return {"logs": []}
