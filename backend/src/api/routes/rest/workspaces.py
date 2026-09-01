import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from src.api.dependencies import get_current_user, get_workspace_service
from src.config import RABBITMQ_URL, SCAN_COMMAND_QUEUE
from src.errors.workspaces import WorkspaceAccessError, WorkspaceValidationError
from src.services import WorkspaceService

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.get("/browse")
async def browse_directory(
    path: str = Query(default="", description="Server-side directory path to list"),
    current_user: dict = Depends(get_current_user),
):
    """Return the children of a server-side directory so the frontend can build a path picker."""
    if not path:
        # Return filesystem roots
        if os.name == "nt":
            import string
            drives = [
                f"{d}:\\" for d in string.ascii_uppercase
                if Path(f"{d}:\\").exists()
            ]
            return {"current": "", "parent": None, "entries": [
                {"name": d, "path": d, "is_dir": True} for d in drives
            ]}
        else:
            path = "/"

    target = Path(path).expanduser().resolve()
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"Path not found: {path}")
    if not target.is_dir():
        raise HTTPException(status_code=400, detail=f"Not a directory: {path}")

    entries = []
    try:
        for entry in sorted(target.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower())):
            try:
                entries.append({
                    "name": entry.name,
                    "path": str(entry),
                    "is_dir": entry.is_dir(),
                })
            except PermissionError:
                pass
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")

    parent = str(target.parent) if target != target.parent else None
    return {"current": str(target), "parent": parent, "entries": entries}


class WorkspaceCreate(BaseModel):
    name: str
    workspace_path: str
    pipeline_ids: list[str] = []
    extensions: list[str] = [".jpg", ".jpeg", ".png", ".webp"]
    active: bool = True


class WorkspaceUpdate(BaseModel):
    name: str | None = None
    workspace_path: str | None = None
    pipeline_ids: list[str] | None = None
    extensions: list[str] | None = None
    active: bool | None = None


@router.get("")
async def list_workspaces(
    workspace_service: WorkspaceService = Depends(get_workspace_service),
    current_user: dict = Depends(get_current_user),
):
    return workspace_service.list_workspaces(owner_id=current_user["_id"])


@router.post("", status_code=201)
async def create_workspace(
    body: WorkspaceCreate,
    workspace_service: WorkspaceService = Depends(get_workspace_service),
    current_user: dict = Depends(get_current_user),
):
    return workspace_service.create_workspace(
        owner_id=current_user["_id"], data=body.model_dump()
    )


@router.get("/{workspace_id}")
async def get_workspace(
    workspace_id: str,
    workspace_service: WorkspaceService = Depends(get_workspace_service),
    current_user: dict = Depends(get_current_user),
):
    workspace = workspace_service.get_workspace(workspace_id, owner_id=current_user["_id"])
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace


@router.put("/{workspace_id}")
async def update_workspace(
    workspace_id: str,
    body: WorkspaceUpdate,
    workspace_service: WorkspaceService = Depends(get_workspace_service),
    current_user: dict = Depends(get_current_user),
):
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        updated = workspace_service.update_workspace(
            workspace_id, owner_id=current_user["_id"], data=data
        )
    except WorkspaceAccessError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    if not updated:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return updated


@router.delete("/{workspace_id}", status_code=204)
async def delete_workspace(
    workspace_id: str,
    workspace_service: WorkspaceService = Depends(get_workspace_service),
    current_user: dict = Depends(get_current_user),
):
    try:
        deleted = workspace_service.delete_workspace(workspace_id, owner_id=current_user["_id"])
    except WorkspaceAccessError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    if not deleted:
        raise HTTPException(status_code=404, detail="Workspace not found")


@router.post("/{workspace_id}/scan")
async def scan_workspace(
    workspace_id: str,
    workspace_service: WorkspaceService = Depends(get_workspace_service),
    current_user: dict = Depends(get_current_user),
):
    try:
        workspace = workspace_service.trigger_scan(workspace_id, owner_id=current_user["_id"])
    except WorkspaceAccessError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except WorkspaceValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    # Publish a scan command so the monitor process triggers an immediate reconcile
    try:
        import aio_pika
        connection = await aio_pika.connect_robust(RABBITMQ_URL)
        async with connection:
            channel = await connection.channel()
            await channel.declare_queue(SCAN_COMMAND_QUEUE, durable=True)
            await channel.default_exchange.publish(
                aio_pika.Message(
                    body=workspace_id.encode(),
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                ),
                routing_key=SCAN_COMMAND_QUEUE,
            )
    except Exception:
        # Scan command is best-effort; the monitor will pick it up on next interval anyway
        pass

    return {"message": "Scan triggered", "workspace": workspace}


@router.delete("/{workspace_id}/pipelines/{pipeline_id}/outputs")
async def clear_pipeline_outputs(
    workspace_id: str,
    pipeline_id: str,
    workspace_service: WorkspaceService = Depends(get_workspace_service),
    current_user: dict = Depends(get_current_user),
):
    """Delete every output this pipeline has produced in this workspace so far."""
    try:
        result = workspace_service.clear_pipeline_outputs(
            workspace_id, pipeline_id, owner_id=current_user["_id"]
        )
    except WorkspaceAccessError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return result


# ──────────────────────────────────────────────────────────────
# Membership
# ──────────────────────────────────────────────────────────────


class MemberAdd(BaseModel):
    username: str
    role: str = "viewer"


class MemberRoleUpdate(BaseModel):
    role: str


@router.get("/{workspace_id}/user-search")
async def search_workspace_users(
    workspace_id: str,
    q: str = Query(default="", description="Username prefix to search for"),
    workspace_service: WorkspaceService = Depends(get_workspace_service),
    current_user: dict = Depends(get_current_user),
):
    try:
        results = workspace_service.search_users_for_workspace(
            workspace_id, actor_id=current_user["_id"], query=q
        )
    except WorkspaceAccessError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    if results is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return results


@router.get("/{workspace_id}/members")
async def list_workspace_members(
    workspace_id: str,
    workspace_service: WorkspaceService = Depends(get_workspace_service),
    current_user: dict = Depends(get_current_user),
):
    members = workspace_service.list_members(workspace_id, actor_id=current_user["_id"])
    if members is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return members


@router.post("/{workspace_id}/members", status_code=201)
async def add_workspace_member(
    workspace_id: str,
    body: MemberAdd,
    workspace_service: WorkspaceService = Depends(get_workspace_service),
    current_user: dict = Depends(get_current_user),
):
    try:
        members = workspace_service.add_member(
            workspace_id, actor_id=current_user["_id"], username=body.username, role=body.role
        )
    except WorkspaceAccessError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if members is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return members


@router.patch("/{workspace_id}/members/{member_id}")
async def update_workspace_member(
    workspace_id: str,
    member_id: str,
    body: MemberRoleUpdate,
    workspace_service: WorkspaceService = Depends(get_workspace_service),
    current_user: dict = Depends(get_current_user),
):
    try:
        members = workspace_service.update_member_role(
            workspace_id, member_id, actor_id=current_user["_id"], role=body.role
        )
    except WorkspaceAccessError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if members is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return members


@router.delete("/{workspace_id}/members/{member_id}")
async def remove_workspace_member(
    workspace_id: str,
    member_id: str,
    workspace_service: WorkspaceService = Depends(get_workspace_service),
    current_user: dict = Depends(get_current_user),
):
    try:
        members = workspace_service.remove_member(
            workspace_id, member_id, actor_id=current_user["_id"]
        )
    except WorkspaceAccessError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    if members is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return members
