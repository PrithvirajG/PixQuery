"""Composes workspace + observation repositories into "what can this user see."

Visibility is scoped by workspace membership, not by ``owner_id`` on the asset
itself (see CLAUDE.md's data-visibility convention): a user reaches an asset only
through an active observation in a workspace they own or belong to. That's a
two-collection join no single per-collection repository can answer on its own,
and every service that scopes a query to a user needs the same join — so it lives
here once rather than copied into each service that needs it.
"""

from __future__ import annotations

from src.repositories.file_observations_repository import FileObservationsRepository
from src.repositories.workspace_definitions_repository import WorkspaceDefinitionsRepository


def accessible_workspace_ids(
    workspaces: WorkspaceDefinitionsRepository, user_id: str
) -> list[str]:
    """Workspaces this user owns or is a member of."""
    return [ws["_id"] for ws in workspaces.list_for_owner(user_id)]


def accessible_asset_ids(
    workspaces: WorkspaceDefinitionsRepository,
    observations: FileObservationsRepository,
    user_id: str,
) -> set[str]:
    """Assets visible to the user: those with an active observation in a
    workspace they can access."""
    ws_ids = accessible_workspace_ids(workspaces, user_id)
    return {
        obs["asset_id"]
        for obs in observations.list_active_for_workspaces(ws_ids)
    }


def workspace_asset_ids(
    workspaces: WorkspaceDefinitionsRepository,
    observations: FileObservationsRepository,
    workspace_id: str,
) -> set[str]:
    """Assets with an active observation in one workspace.

    Matches both the current ``workspace_id`` field and the legacy
    ``watch_root_id`` one, so workspaces created before the rename still
    resolve their assets. Returns an empty set for an unknown workspace.
    """
    workspace = workspaces.get(workspace_id)
    if not workspace:
        return set()
    observed = observations.list_active_for_workspace(
        workspace["_id"], legacy_watch_root_id=workspace.get("watch_root_id")
    )
    return {obs["asset_id"] for obs in observed}


def can_access_asset(
    workspaces: WorkspaceDefinitionsRepository,
    observations: FileObservationsRepository,
    user_id: str,
    asset_id: str,
) -> bool:
    ws_ids = set(accessible_workspace_ids(workspaces, user_id))
    return any(
        obs.get("workspace_id") in ws_ids
        for obs in observations.list_for_asset(asset_id)
    )
