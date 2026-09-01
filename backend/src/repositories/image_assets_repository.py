"""Pure data access for the ``image_assets`` collection.

No cross-collection reads, no cascades, no policy. Anything that used to reach
into another collection from here (visibility scoping via ``file_observations``,
the assets ↔ observations "which assets are still active" reconciliation) is a
service-layer concern now — the service composes this repository with
:class:`~src.repositories.file_observations.FileObservationsRepository` itself.
"""

from __future__ import annotations

from typing import Any

from src.models import ImageAsset
from src.utils.time import utcnow


class ImageAssetsRepository:
    def __init__(self, database):
        self.collection = database["image_assets"]

    def ensure_indexes(self) -> None:
        _drop_index_if_exists(self.collection, "content_sha256_1")
        self.collection.create_index(
            [("workspace_id", 1), ("content_sha256", 1)], unique=True
        )
        self.collection.create_index("content_sha256")

    def upsert(
        self,
        *,
        content_sha256: str,
        mime_type: str | None,
        size_bytes: int,
        current_path: str,
        workspace_id: str | None = None,
        owner_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = utcnow()
        # Assets are scoped per workspace, so identity is (workspace_id, content_sha256):
        # identical bytes in two workspaces become two independent assets.
        existing = self.collection.find_one(
            {"content_sha256": content_sha256, "workspace_id": workspace_id}
        )
        if existing:
            update_payload = {
                "mime_type": mime_type,
                "size_bytes": size_bytes,
                "latest_seen_at": now,
                "active": True,
                "current_path": current_path,
            }
            if owner_id and not existing.get("owner_id"):
                update_payload["owner_id"] = owner_id
            self.collection.update_one(
                {"_id": existing["_id"]},
                {"$set": update_payload, "$setOnInsert": {"metadata": metadata or {}}},
            )
            existing.update(update_payload)
            return existing

        asset = ImageAsset(
            content_sha256=content_sha256,
            workspace_id=workspace_id,
            mime_type=mime_type,
            size_bytes=size_bytes,
            first_seen_at=now,
            latest_seen_at=now,
            current_path=current_path,
            owner_id=owner_id,
            metadata=metadata or {},
        ).to_doc()
        self.collection.insert_one(asset)
        return asset

    def update_metadata(self, asset_id: str, metadata: dict[str, Any]) -> None:
        self.collection.update_one({"_id": asset_id}, {"$set": {"metadata": metadata}})

    def get(self, asset_id: str) -> dict[str, Any] | None:
        return self.collection.find_one({"_id": asset_id})

    def list_by_ids(
        self, asset_ids: set[str] | list[str], *, active_only: bool = True, limit: int = 100, skip: int = 0
    ) -> list[dict[str, Any]]:
        """Assets from an explicit id set, newest first.

        The caller decides which ids are in scope — no visibility rules live here.
        """
        query: dict[str, Any] = {"_id": {"$in": list(asset_ids)}}
        if active_only:
            query["active"] = True
        return list(
            self.collection.find(query).sort("latest_seen_at", -1).skip(skip).limit(limit)
        )

    def list_all(self, *, active_only: bool = False, limit: int = 100, skip: int = 0) -> list[dict[str, Any]]:
        query: dict[str, Any] = {"active": True} if active_only else {}
        return list(
            self.collection.find(query).sort("latest_seen_at", -1).skip(skip).limit(limit)
        )

    def list_all_ids(self) -> list[str]:
        return [asset["_id"] for asset in self.collection.find({})]

    def set_active(self, asset_id: str, active: bool) -> None:
        self.collection.update_one({"_id": asset_id}, {"$set": {"active": active}})

    def delete(self, asset_id: str) -> bool:
        return self.collection.delete_one({"_id": asset_id}).deleted_count > 0

    def count_by_ids(self, asset_ids: set[str] | list[str], *, active_only: bool = True) -> int:
        query: dict[str, Any] = {"_id": {"$in": list(asset_ids)}}
        if active_only:
            query["active"] = True
        return self.collection.count_documents(query)

    def claim_unowned(self, user_id: str) -> int:
        result = self.collection.update_many(
            {"$or": [{"owner_id": {"$exists": False}}, {"owner_id": None}]},
            {"$set": {"owner_id": user_id}},
        )
        return result.modified_count


def _drop_index_if_exists(collection, index_name: str) -> None:
    try:
        collection.drop_index(index_name)
    except Exception:
        pass
