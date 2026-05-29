from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.dependencies import get_current_user, get_pipeline_service
from src.services import PipelineService

router = APIRouter(prefix="/pipelines", tags=["pipelines"])


class PipelineNodeRef(BaseModel):
    pipeline_node_id: str
    config_overrides: dict[str, Any] = {}
    node_id: str | None = None


class PipelineCreate(BaseModel):
    name: str
    description: str = ""
    nodes: list[PipelineNodeRef] = []


class PipelineUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    nodes: list[PipelineNodeRef] | None = None


@router.get("")
async def list_pipelines(
    pipeline_service: PipelineService = Depends(get_pipeline_service),
    current_user: dict = Depends(get_current_user),
):
    return pipeline_service.list_pipelines(owner_id=current_user["_id"])


@router.post("", status_code=201)
async def create_pipeline(
    body: PipelineCreate,
    pipeline_service: PipelineService = Depends(get_pipeline_service),
    current_user: dict = Depends(get_current_user),
):
    data = body.model_dump()
    return pipeline_service.create_pipeline(owner_id=current_user["_id"], data=data)


@router.get("/{pipeline_id}")
async def get_pipeline(
    pipeline_id: str,
    pipeline_service: PipelineService = Depends(get_pipeline_service),
    current_user: dict = Depends(get_current_user),
):
    pipeline = pipeline_service.get_pipeline(pipeline_id, owner_id=current_user["_id"])
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return pipeline


@router.put("/{pipeline_id}")
async def update_pipeline(
    pipeline_id: str,
    body: PipelineUpdate,
    pipeline_service: PipelineService = Depends(get_pipeline_service),
    current_user: dict = Depends(get_current_user),
):
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    updated = pipeline_service.update_pipeline(
        pipeline_id, owner_id=current_user["_id"], data=data
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return updated


@router.delete("/{pipeline_id}", status_code=204)
async def delete_pipeline(
    pipeline_id: str,
    pipeline_service: PipelineService = Depends(get_pipeline_service),
    current_user: dict = Depends(get_current_user),
):
    deleted = pipeline_service.delete_pipeline(pipeline_id, owner_id=current_user["_id"])
    if not deleted:
        raise HTTPException(status_code=404, detail="Pipeline not found")
