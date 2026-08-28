from __future__ import annotations

from typing import Any

from src.services.document_serializer import serialize_document, serialize_documents


# Assignable member roles (the owner has the implicit "owner" role via owner_id).
ASSIGNABLE_ROLES = {"viewer", "editor"}


class WorkspaceAccessError(PermissionError):
    """Raised when the acting user lacks the role required for an operation."""


class WorkspaceValidationError(ValueError):
    """Raised when an operation is invalid for the workspace's current state."""


def role_for(workspace: dict[str, Any], user_id: str) -> str | None:
    """Return the acting user's role in a workspace: 'owner', 'editor', 'viewer', or None."""
    if workspace.get("owner_id") == user_id:
        return "owner"
    for member in workspace.get("members", []):
        if member.get("user_id") == user_id:
            return member.get("role", "viewer")
    return None


def _can_view(role: str | None) -> bool:
    return role in {"owner", "editor", "viewer"}


def _can_edit(role: str | None) -> bool:
    return role in {"owner", "editor"}


def _can_manage(role: str | None) -> bool:
    return role == "owner"


class WorkspaceService:
    def __init__(self, repository):
        self.repository = repository

    def _serialize(self, workspace: dict[str, Any], user_id: str) -> dict[str, Any]:
        doc = serialize_document(workspace)
        doc["my_role"] = role_for(workspace, user_id)
        return doc

    def list_workspaces(self, *, owner_id: str) -> list[dict[str, Any]]:
        workspaces = self.repository.list_workspaces(owner_id=owner_id)
        return [self._serialize(ws, owner_id) for ws in workspaces]

    def get_workspace(self, workspace_id: str, *, owner_id: str) -> dict[str, Any] | None:
        workspace = self.repository.get_workspace(workspace_id)
        if not workspace or not _can_view(role_for(workspace, owner_id)):
            return None
        return self._serialize(workspace, owner_id)

    def create_workspace(self, *, owner_id: str, data: dict[str, Any]) -> dict[str, Any]:
        workspace = self.repository.create_workspace(
            owner_id=owner_id,
            name=data["name"],
            workspace_path=data["workspace_path"],
            pipeline_ids=data.get("pipeline_ids", []),
            extensions=data.get("extensions", [".jpg", ".jpeg", ".png", ".webp"]),
            active=data.get("active", True),
        )
        return self._serialize(workspace, owner_id)

    def update_workspace(
        self, workspace_id: str, *, owner_id: str, data: dict[str, Any]
    ) -> dict[str, Any] | None:
        existing = self.repository.get_workspace(workspace_id)
        if not existing or not _can_view(role_for(existing, owner_id)):
            return None
        if not _can_edit(role_for(existing, owner_id)):
            raise WorkspaceAccessError("Editing a workspace requires the editor or owner role")
        allowed_fields = {"name", "workspace_path", "pipeline_ids", "extensions", "active"}
        updates = {k: v for k, v in data.items() if k in allowed_fields}
        updated = self.repository.update_workspace(workspace_id, updates)
        return self._serialize(updated, owner_id) if updated else None

    def delete_workspace(self, workspace_id: str, *, owner_id: str) -> bool:
        existing = self.repository.get_workspace(workspace_id)
        if not existing or not _can_view(role_for(existing, owner_id)):
            return False
        if not _can_manage(role_for(existing, owner_id)):
            raise WorkspaceAccessError("Only the owner can delete a workspace")
        return self.repository.delete_workspace(workspace_id)

    def trigger_scan(self, workspace_id: str, *, owner_id: str) -> dict[str, Any] | None:
        """Return workspace info; actual reconciliation is handled by the watcher process."""
        workspace = self.repository.get_workspace(workspace_id)
        if not workspace or not _can_view(role_for(workspace, owner_id)):
            return None
        if not _can_edit(role_for(workspace, owner_id)):
            raise WorkspaceAccessError("Triggering a scan requires the editor or owner role")
        if not workspace.get("pipeline_ids"):
            raise WorkspaceValidationError(
                "This workspace has no pipelines attached — attach at least one pipeline before syncing"
            )
        return self._serialize(workspace, owner_id)

    def clear_pipeline_outputs(
        self, workspace_id: str, pipeline_id: str, *, owner_id: str
    ) -> dict[str, int] | None:
        """Delete every output one pipeline has produced in this workspace so far.

        Resets its jobs to 'queued' without dispatching them — a rescan only
        redispatches 'failed' jobs, so getting outputs back requires a manual
        per-image retrigger, not an accidental rescan.
        """
        workspace = self.repository.get_workspace(workspace_id)
        if not workspace or not _can_view(role_for(workspace, owner_id)):
            return None
        if not _can_edit(role_for(workspace, owner_id)):
            raise WorkspaceAccessError(
                "Clearing pipeline outputs requires the editor or owner role"
            )
        return self.repository.clear_pipeline_outputs(workspace_id, pipeline_id)

    def clear_asset_pipeline_outputs(
        self, asset_id: str, pipeline_id: str, *, owner_id: str
    ) -> dict[str, int] | None:
        """Delete one pipeline's outputs for a single image.

        Same authorization as the workspace-wide clear — it is the same
        destructive act, just scoped to one image — resolved through the
        workspace the asset belongs to.
        """
        asset = self.repository.get_asset(asset_id)
        if not asset or not asset.get("active"):
            return None
        workspace = (
            self.repository.get_workspace(asset["workspace_id"])
            if asset.get("workspace_id")
            else None
        )
        if not workspace or not _can_view(role_for(workspace, owner_id)):
            return None
        if not _can_edit(role_for(workspace, owner_id)):
            raise WorkspaceAccessError(
                "Clearing pipeline outputs requires the editor or owner role"
            )
        return self.repository.clear_asset_pipeline_outputs(asset_id, pipeline_id)

    # ──────────────────────────────────────────────────────────────
    # Membership
    # ──────────────────────────────────────────────────────────────

    def list_members(self, workspace_id: str, *, actor_id: str) -> list[dict[str, Any]] | None:
        workspace = self.repository.get_workspace(workspace_id)
        if not workspace or not _can_view(role_for(workspace, actor_id)):
            return None
        return self._member_view(workspace)

    def _member_view(self, workspace: dict[str, Any]) -> list[dict[str, Any]]:
        members: list[dict[str, Any]] = []
        owner = self.repository.get_user(workspace.get("owner_id"))
        members.append(
            {
                "user_id": workspace.get("owner_id"),
                "username": owner["username"] if owner else "(unknown)",
                "role": "owner",
            }
        )
        for entry in workspace.get("members", []):
            user = self.repository.get_user(entry.get("user_id"))
            added_at = entry.get("added_at")
            members.append(
                {
                    "user_id": entry.get("user_id"),
                    "username": user["username"] if user else "(unknown)",
                    "role": entry.get("role", "viewer"),
                    "added_at": added_at.isoformat() if hasattr(added_at, "isoformat") else added_at,
                }
            )
        return members

    def add_member(
        self, workspace_id: str, *, actor_id: str, username: str, role: str
    ) -> list[dict[str, Any]] | None:
        workspace = self._require_manage(workspace_id, actor_id)
        if workspace is None:
            return None
        if role not in ASSIGNABLE_ROLES:
            raise ValueError(f"Invalid role '{role}'. Choose one of: {', '.join(sorted(ASSIGNABLE_ROLES))}")
        user = self.repository.get_user_by_username(username)
        if not user:
            raise ValueError(f"No user named '{username}'")
        if user["_id"] == workspace.get("owner_id"):
            raise ValueError("That user is the workspace owner")
        updated = self.repository.add_workspace_member(workspace_id, user["_id"], role)
        if updated is None:  # workspace removed between the access check and the write
            return None
        return self._member_view(updated)

    def update_member_role(
        self, workspace_id: str, member_id: str, *, actor_id: str, role: str
    ) -> list[dict[str, Any]] | None:
        workspace = self._require_manage(workspace_id, actor_id)
        if workspace is None:
            return None
        if role not in ASSIGNABLE_ROLES:
            raise ValueError(f"Invalid role '{role}'. Choose one of: {', '.join(sorted(ASSIGNABLE_ROLES))}")
        updated = self.repository.set_workspace_member_role(workspace_id, member_id, role)
        if updated is None:
            raise ValueError("That user is not a member of this workspace")
        return self._member_view(updated)

    def remove_member(
        self, workspace_id: str, member_id: str, *, actor_id: str
    ) -> list[dict[str, Any]] | None:
        workspace = self._require_manage(workspace_id, actor_id)
        if workspace is None:
            return None
        updated = self.repository.remove_workspace_member(workspace_id, member_id)
        if updated is None:  # workspace removed between the access check and the write
            return None
        return self._member_view(updated)

    def search_users_for_workspace(
        self, workspace_id: str, *, actor_id: str, query: str, limit: int = 10
    ) -> list[dict[str, Any]] | None:
        workspace = self._require_manage(workspace_id, actor_id)
        if workspace is None:
            return None
        query = (query or "").strip()
        if not query:
            return []
        exclude = {workspace.get("owner_id")} | {
            m.get("user_id") for m in workspace.get("members", [])
        }
        return self.repository.search_users(query, exclude_ids=exclude, limit=limit)

    def _require_manage(self, workspace_id: str, actor_id: str) -> dict[str, Any] | None:
        """Return the workspace if the actor can manage it, None if not found/no access,
        or raise WorkspaceAccessError if found but the actor lacks the owner role."""
        workspace = self.repository.get_workspace(workspace_id)
        if not workspace or not _can_view(role_for(workspace, actor_id)):
            return None
        if not _can_manage(role_for(workspace, actor_id)):
            raise WorkspaceAccessError("Only the owner can manage members")
        return workspace
