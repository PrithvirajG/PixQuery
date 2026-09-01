"""Pure data access for the ``workspace_definitions`` collection.

Membership lives as an embedded array on the workspace document itself, so
add/set-role/remove are genuinely single-collection reads-then-writes here, not
a join. Deleting a workspace's cascade to observations/assets/jobs/outputs/runs
in other collections is not this repository's job — the caller composes this
with the other repositories.
"""

from __future__ import annotations

from typing import Any

from src.models import DEFAULT_EXTENSIONS, WorkspaceDefinition, WorkspaceMember


class WorkspaceDefinitionsRepository:
    def __init__(self, database):
        self.collection = database["workspace_definitions"]

    def ensure_indexes(self) -> None:
        self.collection.create_index("owner_id")

    def list_for_owner(self, owner_id: str) -> list[dict[str, Any]]:
        """Workspaces this user owns OR is a member of — ``owner_id`` here is the acting user."""
        query = {"$or": [{"owner_id": owner_id}, {"members.user_id": owner_id}]}
        return list(self.collection.find(query).sort("created_at", -1))

    def list_all_active(self) -> list[dict[str, Any]]:
        """Every active workspace across all users — used by the monitor process."""
        return list(self.collection.find({"active": True}))

    def list_referencing_pipeline(self, pipeline_id: str) -> list[dict[str, Any]]:
        return list(self.collection.find({"pipeline_ids": pipeline_id}))

    def get(self, workspace_id: str) -> dict[str, Any] | None:
        return self.collection.find_one({"_id": workspace_id})

    def create(
        self,
        *,
        owner_id: str,
        name: str,
        workspace_path: str,
        pipeline_ids: list[str] | None = None,
        extensions: list[str] | None = None,
        active: bool = True,
    ) -> dict[str, Any]:
        workspace = WorkspaceDefinition(
            name=name,
            workspace_path=workspace_path,
            owner_id=owner_id,
            active=active,
            pipeline_ids=pipeline_ids or [],
            extensions=extensions or list(DEFAULT_EXTENSIONS),
        ).to_doc()
        self.collection.insert_one(workspace)
        return workspace

    def update(self, workspace_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        updates.pop("_id", None)
        updates.pop("owner_id", None)
        self.collection.update_one({"_id": workspace_id}, {"$set": updates})
        return self.get(workspace_id)

    def remove_pipeline_id(self, workspace_id: str, pipeline_id: str) -> None:
        """Pull one pipeline id out of a workspace's ``pipeline_ids`` list.

        Read-modify-write rather than ``$pull`` so this stays portable to the
        in-memory test fake, which only implements ``$set``.
        """
        workspace = self.get(workspace_id)
        if not workspace:
            return
        remaining = [p for p in workspace.get("pipeline_ids", []) if p != pipeline_id]
        self.collection.update_one({"_id": workspace_id}, {"$set": {"pipeline_ids": remaining}})

    def delete(self, workspace_id: str) -> bool:
        return self.collection.delete_one({"_id": workspace_id}).deleted_count > 0

    def add_member(self, workspace_id: str, user_id: str, role: str) -> dict[str, Any] | None:
        """Add (or re-role) a member."""
        workspace = self.get(workspace_id)
        if not workspace:
            return None
        members = [m for m in workspace.get("members", []) if m.get("user_id") != user_id]
        members.append(WorkspaceMember(user_id=user_id, role=role).model_dump())
        self.collection.update_one({"_id": workspace_id}, {"$set": {"members": members}})
        return self.get(workspace_id)

    def set_member_role(self, workspace_id: str, user_id: str, role: str) -> dict[str, Any] | None:
        workspace = self.get(workspace_id)
        if not workspace:
            return None
        members = workspace.get("members", [])
        if not any(m.get("user_id") == user_id for m in members):
            return None
        for m in members:
            if m.get("user_id") == user_id:
                m["role"] = role
        self.collection.update_one({"_id": workspace_id}, {"$set": {"members": members}})
        return self.get(workspace_id)

    def remove_member(self, workspace_id: str, user_id: str) -> dict[str, Any] | None:
        workspace = self.get(workspace_id)
        if not workspace:
            return None
        members = [m for m in workspace.get("members", []) if m.get("user_id") != user_id]
        self.collection.update_one({"_id": workspace_id}, {"$set": {"members": members}})
        return self.get(workspace_id)
