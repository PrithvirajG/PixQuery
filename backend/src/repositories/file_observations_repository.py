"""Pure data access for the ``file_observations`` collection.

An observation is one (workspace, relative_path) sighting of an asset on disk.
Resolving a workspace's ``watch_root_id`` (the legacy field name) or turning
observations into asset visibility is the caller's job — this repository only
ever touches ``file_observations``.
"""

from __future__ import annotations

from typing import Any

from src.models import FileObservation
from src.utils.time import utcnow


class FileObservationsRepository:
    def __init__(self, database):
        self.collection = database["file_observations"]

    def ensure_indexes(self) -> None:
        self.collection.create_index(
            [("workspace_id", 1), ("relative_path", 1)], unique=True
        )

    def upsert(
        self,
        *,
        asset_id: str,
        workspace_id: str,
        relative_path: str,
        absolute_path: str,
        content_sha256: str,
    ) -> dict[str, Any]:
        now = utcnow()
        key = {"workspace_id": workspace_id, "relative_path": relative_path}
        obs = FileObservation(
            asset_id=asset_id,
            workspace_id=workspace_id,
            relative_path=relative_path,
            absolute_path=absolute_path,
            content_sha256=content_sha256,
            last_seen_at=now,
        ).to_doc()
        update = {
            "$set": {
                field: obs[field]
                for field in ("asset_id", "absolute_path", "content_sha256", "status", "last_seen_at", "missing_since")
            },
            "$setOnInsert": {"_id": obs["_id"], "first_seen_at": obs["first_seen_at"]},
        }
        self.collection.update_one(key, update, upsert=True)
        return self.collection.find_one(key)

    def mark_missing(self, workspace_id: str, active_relative_paths: set[str]) -> None:
        """Flag every previously-active observation in this workspace not in
        ``active_relative_paths`` as missing. Does not touch ``image_assets`` —
        recomputing asset activity from the result is the caller's job."""
        now = utcnow()
        active_paths = list(active_relative_paths)
        query: dict[str, Any] = {"workspace_id": workspace_id, "status": "active"}
        if active_paths:
            query["relative_path"] = {"$nin": active_paths}
        self.collection.update_many(
            query,
            {"$set": {"status": "missing", "missing_since": now, "last_seen_at": now}},
        )

    def distinct_active_asset_ids(self) -> set[str]:
        return set(self.collection.distinct("asset_id", {"status": "active"}))

    def list_active_for_workspace(
        self, workspace_id: str, *, legacy_watch_root_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Active observations in a workspace.

        ``legacy_watch_root_id`` matches observations recorded under a workspace's
        pre-rename field so workspaces created before it still resolve their
        assets — the caller looks it up on the workspace document and passes it in.
        """
        return list(
            self.collection.find(
                {
                    "$or": [
                        {"workspace_id": workspace_id},
                        {"watch_root_id": legacy_watch_root_id or "__none__"},
                    ],
                    "status": "active",
                }
            )
        )

    def list_active_for_workspaces(self, workspace_ids: list[str]) -> list[dict[str, Any]]:
        return list(
            self.collection.find({"workspace_id": {"$in": workspace_ids}, "status": "active"})
        )

    def list_for_workspace(self, workspace_id: str) -> list[dict[str, Any]]:
        return list(self.collection.find({"workspace_id": workspace_id}))

    def list_for_asset(self, asset_id: str) -> list[dict[str, Any]]:
        return list(self.collection.find({"asset_id": asset_id}))

    def exists_for_asset(self, asset_id: str) -> bool:
        return self.collection.find_one({"asset_id": asset_id}) is not None

    def delete_for_workspace(self, workspace_id: str) -> int:
        return self.collection.delete_many({"workspace_id": workspace_id}).deleted_count
