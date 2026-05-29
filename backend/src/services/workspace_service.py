from __future__ import annotations

from typing import Any

from src.services.document_serializer import serialize_document, serialize_documents


class WorkspaceService:
    def __init__(self, repository):
        self.repository = repository

    def list_workspaces(self, *, owner_id: str) -> list[dict[str, Any]]:
        workspaces = self.repository.list_workspaces(owner_id=owner_id)
        return serialize_documents(workspaces)

    def get_workspace(self, workspace_id: str, *, owner_id: str) -> dict[str, Any] | None:
        workspace = self.repository.get_workspace(workspace_id)
        if not workspace or workspace.get("owner_id") != owner_id:
            return None
        return serialize_document(workspace)

    def create_workspace(self, *, owner_id: str, data: dict[str, Any]) -> dict[str, Any]:
        workspace = self.repository.create_workspace(
            owner_id=owner_id,
            name=data["name"],
            workspace_path=data["workspace_path"],
            pipeline_ids=data.get("pipeline_ids", []),
            extensions=data.get("extensions", [".jpg", ".jpeg", ".png", ".webp"]),
            active=data.get("active", True),
        )
        return serialize_document(workspace)

    def update_workspace(
        self, workspace_id: str, *, owner_id: str, data: dict[str, Any]
    ) -> dict[str, Any] | None:
        existing = self.repository.get_workspace(workspace_id)
        if not existing or existing.get("owner_id") != owner_id:
            return None
        allowed_fields = {"name", "workspace_path", "pipeline_ids", "extensions", "active"}
        updates = {k: v for k, v in data.items() if k in allowed_fields}
        updated = self.repository.update_workspace(workspace_id, updates)
        return serialize_document(updated) if updated else None

    def delete_workspace(self, workspace_id: str, *, owner_id: str) -> bool:
        existing = self.repository.get_workspace(workspace_id)
        if not existing or existing.get("owner_id") != owner_id:
            return False
        return self.repository.delete_workspace(workspace_id)

    def trigger_scan(self, workspace_id: str, *, owner_id: str) -> dict[str, Any] | None:
        """Return workspace info; actual reconciliation is handled by the watcher process."""
        workspace = self.repository.get_workspace(workspace_id)
        if not workspace or workspace.get("owner_id") != owner_id:
            return None
        return serialize_document(workspace)
