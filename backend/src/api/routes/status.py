from pathlib import Path

from fastapi import APIRouter

from src.config import WATCH_ROOT

router = APIRouter(tags=["status"])


@router.get("/status")
async def status():
    return {"status": "ok", "workspace_path": str(Path(WATCH_ROOT))}

