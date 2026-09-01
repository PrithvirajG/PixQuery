from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from src.api.dependencies import (
    get_current_user,
    get_image_service,
    get_job_service,
    get_workspace_service,
)
from src.errors.jobs import JobConflictError
from src.errors.workspaces import WorkspaceAccessError
from src.services import ImageService, JobService, WorkspaceService

router = APIRouter(prefix="/images", tags=["images"])


class ReprocessRequest(BaseModel):
    pipeline_id: str


@router.get("")
async def list_images(
    limit: int = 100,
    skip: int = 0,
    image_service: ImageService = Depends(get_image_service),
    current_user: dict = Depends(get_current_user),
):
    return image_service.list_images(user_id=current_user["_id"], limit=limit, skip=skip)


@router.get("/{asset_id}/thumbnail")
async def get_thumbnail(
    asset_id: str,
    image_service: ImageService = Depends(get_image_service),
):
    """No auth required — UUIDs are not guessable and images need to load in <img> tags."""
    asset = image_service.get_image(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Image not found")
    path = Path(asset["current_path"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")
    return FileResponse(str(path), media_type=asset.get("mime_type") or "image/jpeg")


@router.get("/{asset_id}/detail")
async def get_image_detail(
    asset_id: str,
    image_service: ImageService = Depends(get_image_service),
    current_user: dict = Depends(get_current_user),
):
    detail = image_service.get_image_detail(asset_id, user_id=current_user["_id"])
    if not detail:
        raise HTTPException(status_code=404, detail="Image not found")
    return detail


@router.get("/{asset_id}")
async def get_image(
    asset_id: str,
    image_service: ImageService = Depends(get_image_service),
    current_user: dict = Depends(get_current_user),
):
    asset = image_service.get_image(asset_id, user_id=current_user["_id"])
    if not asset:
        raise HTTPException(status_code=404, detail="Image not found")
    return asset


@router.post("/{asset_id}/reprocess")
async def reprocess_image(
    asset_id: str,
    body: ReprocessRequest,
    job_service: JobService = Depends(get_job_service),
    current_user: dict = Depends(get_current_user),
):
    """Manually re-run one pipeline against this image, overriding its prior outputs."""
    try:
        job = await job_service.retrigger_pipeline(
            asset_id, body.pipeline_id, user_id=current_user["_id"]
        )
    except WorkspaceAccessError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except JobConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if not job:
        raise HTTPException(status_code=404, detail="Image or pipeline not found")
    return job


@router.delete("/{asset_id}/outputs/{pipeline_id}")
async def clear_image_pipeline_outputs(
    asset_id: str,
    pipeline_id: str,
    workspace_service: WorkspaceService = Depends(get_workspace_service),
    current_user: dict = Depends(get_current_user),
):
    """Delete one pipeline's outputs for this image only.

    The workspace-wide equivalent lives on the workspaces router; this is the
    per-image control, and returns the pair to NOT_STARTED so it can be run again.
    """
    try:
        result = workspace_service.clear_asset_pipeline_outputs(
            asset_id, pipeline_id, owner_id=current_user["_id"]
        )
    except WorkspaceAccessError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail="Image not found")
    return result
