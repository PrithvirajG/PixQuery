from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from src.api.dependencies import get_image_service, get_current_user
from src.services import ImageService

router = APIRouter(prefix="/images", tags=["images"])


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
