from fastapi import APIRouter, Depends, HTTPException

from src.api.dependencies import get_job_service
from src.services import JobService

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("")
async def list_jobs(
    status: str | None = None,
    limit: int = 100,
    job_service: JobService = Depends(get_job_service),
):
    return job_service.list_jobs(status=status, limit=limit)


@router.post("/{job_id}/requeue")
async def requeue_job(
    job_id: str,
    job_service: JobService = Depends(get_job_service),
):
    job = await job_service.requeue_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
