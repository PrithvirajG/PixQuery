from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.dependencies import get_current_user, get_pipeline_service
from src.services import PipelineService

router = APIRouter(prefix="/pipeline-nodes", tags=["pipeline-nodes"])


class PipelineNodeCreate(BaseModel):
    name: str
    description: str = ""
    node_type: str
    context_inputs: list[str] = []
    context_outputs: list[str] = []
    config_schema: dict[str, Any] = {}
    default_config: dict[str, Any] = {}


class PipelineNodeUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    context_inputs: list[str] | None = None
    context_outputs: list[str] | None = None
    config_schema: dict[str, Any] | None = None
    default_config: dict[str, Any] | None = None


@router.get("")
async def list_pipeline_nodes(
    pipeline_service: PipelineService = Depends(get_pipeline_service),
    current_user: dict = Depends(get_current_user),
):
    return pipeline_service.list_pipeline_nodes(owner_id=current_user["_id"])


@router.post("", status_code=201)
async def create_pipeline_node(
    body: PipelineNodeCreate,
    pipeline_service: PipelineService = Depends(get_pipeline_service),
    current_user: dict = Depends(get_current_user),
):
    return pipeline_service.create_pipeline_node(
        owner_id=current_user["_id"], data=body.model_dump()
    )


@router.put("/{node_id}")
async def update_pipeline_node(
    node_id: str,
    body: PipelineNodeUpdate,
    pipeline_service: PipelineService = Depends(get_pipeline_service),
    current_user: dict = Depends(get_current_user),
):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    updated = pipeline_service.update_pipeline_node(
        node_id, owner_id=current_user["_id"], data=updates
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Pipeline node not found or not editable")
    return updated


@router.delete("/{node_id}", status_code=204)
async def delete_pipeline_node(
    node_id: str,
    pipeline_service: PipelineService = Depends(get_pipeline_service),
    current_user: dict = Depends(get_current_user),
):
    deleted = pipeline_service.delete_pipeline_node(node_id, owner_id=current_user["_id"])
    if not deleted:
        raise HTTPException(status_code=404, detail="Pipeline node not found or not deletable")
