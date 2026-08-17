from fastapi import APIRouter, Depends, HTTPException

from src.api.dependencies import get_current_user, get_job_service, get_stats_service
from src.services import JobService, StatsService

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/overview")
async def get_stats_overview(
    stats_service: StatsService = Depends(get_stats_service),
    current_user: dict = Depends(get_current_user),
):
    return stats_service.get_overview(owner_id=current_user["_id"])


@router.get("/jobs/recent")
async def list_recent_jobs(
    limit: int = 50,
    stats_service: StatsService = Depends(get_stats_service),
    current_user: dict = Depends(get_current_user),
):
    return stats_service.list_recent_jobs(user_id=current_user["_id"], limit=limit)
