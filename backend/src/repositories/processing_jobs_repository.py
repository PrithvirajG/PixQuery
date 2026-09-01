"""Pure data access for the ``processing_jobs`` collection.

No retry policy here — ``fail`` takes the already-decided ``final_status`` and
``next_attempt_at`` rather than computing them. Deciding *how* to retry (delay
schedule, max attempts, which errors are permanent) is
``PipelineExecutionService``'s job; this repository only persists the decision.
No event emission either — announcing a state change is the orchestrating
service's call, not a fact about the write itself.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from src.models import ProcessingJob
from src.utils.time import utcnow


class ProcessingJobsRepository:
    def __init__(self, database):
        self.collection = database["processing_jobs"]

    def ensure_indexes(self) -> None:
        # Jobs are scoped per workspace: the same image in two workspaces is
        # processed independently. Drop the older global uniqueness constraint if
        # it survives from a previous schema.
        _drop_index_if_exists(self.collection, "asset_id_1_pipeline_id_1_pipeline_version_1")
        self.collection.create_index(
            [("workspace_id", 1), ("asset_id", 1), ("pipeline_id", 1), ("pipeline_version", 1)],
            unique=True,
        )

    def get(self, job_id: str) -> dict[str, Any] | None:
        return self.collection.find_one({"_id": job_id})

    def get_or_create(
        self,
        *,
        asset_id: str,
        pipeline_id: str,
        pipeline_version: str,
        workspace_id: str | None = None,
    ) -> tuple[dict[str, Any], bool]:
        key = {
            "workspace_id": workspace_id,
            "asset_id": asset_id,
            "pipeline_id": pipeline_id,
            "pipeline_version": pipeline_version,
        }
        existing = self.collection.find_one(key)
        if existing:
            return existing, False

        now = utcnow()
        job = ProcessingJob(
            workspace_id=workspace_id,
            asset_id=asset_id,
            pipeline_id=pipeline_id,
            pipeline_version=pipeline_version,
            next_attempt_at=now,
            created_at=now,
            updated_at=now,
        ).to_doc()
        self.collection.insert_one(job)
        return job, True

    def list_all(self, status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        query = {"status": status} if status else {}
        return list(self.collection.find(query).sort("updated_at", -1).limit(limit))

    def list_for_asset(self, asset_id: str) -> list[dict[str, Any]]:
        return list(self.collection.find({"asset_id": asset_id}))

    def list_for_asset_ids(self, asset_ids: list[str], *, limit: int = 50) -> list[dict[str, Any]]:
        return list(
            self.collection.find({"asset_id": {"$in": asset_ids}})
            .sort("updated_at", -1)
            .limit(limit)
        )

    def requeue(self, job_id: str) -> dict[str, Any] | None:
        """Reset for a fresh retry budget: clears attempt count and last error."""
        now = utcnow()
        self.collection.update_one(
            {"_id": job_id},
            {"$set": {
                "status": "queued",
                "next_attempt_at": now,
                "updated_at": now,
                "attempt_count": 0,
                "last_error": None,
            }},
        )
        return self.get(job_id)

    def start(self, job_id: str) -> dict[str, Any]:
        """Atomically mark a job processing and bump its attempt count."""
        now = utcnow()
        try:
            from pymongo import ReturnDocument

            return_document = ReturnDocument.AFTER
        except ImportError:
            return_document = True
        job = self.collection.find_one_and_update(
            {"_id": job_id},
            {
                "$set": {"status": "processing", "updated_at": now},
                "$inc": {"attempt_count": 1},
            },
            return_document=return_document,
        )
        if not job:
            raise ValueError(f"Processing job not found: {job_id}")
        return job

    def complete(self, job_id: str) -> None:
        self.collection.update_one(
            {"_id": job_id},
            {"$set": {"status": "completed", "updated_at": utcnow(), "last_error": None}},
        )

    def fail(
        self,
        job_id: str,
        *,
        final_status: str,
        next_attempt_at: datetime | None,
        error: dict[str, Any],
    ) -> None:
        self.collection.update_one(
            {"_id": job_id},
            {
                "$set": {
                    "status": final_status,
                    "next_attempt_at": next_attempt_at,
                    "last_error": error,
                    "updated_at": utcnow(),
                }
            },
        )

    def count_by_status(self, asset_ids: list[str], status: str) -> int:
        return self.collection.count_documents({"asset_id": {"$in": asset_ids}, "status": status})

    def delete_for_workspace_pipeline(self, workspace_id: str, pipeline_id: str) -> tuple[list[str], int]:
        """Delete every job for this (workspace, pipeline) pair; returns (their ids, count deleted).

        Ids are returned pre-deletion so the caller can cascade to pipeline_runs/model_outputs
        keyed by job_id before those rows lose their only link back.
        """
        query = {"workspace_id": workspace_id, "pipeline_id": pipeline_id}
        job_ids = [j["_id"] for j in self.collection.find(query)]
        deleted = self.collection.delete_many(query).deleted_count
        return job_ids, deleted

    def delete_for_asset_pipeline(self, asset_id: str, pipeline_id: str) -> tuple[list[str], int]:
        query = {"asset_id": asset_id, "pipeline_id": pipeline_id}
        job_ids = [j["_id"] for j in self.collection.find(query)]
        deleted = self.collection.delete_many(query).deleted_count
        return job_ids, deleted

    def delete_for_pipeline(self, pipeline_id: str) -> int:
        return self.collection.delete_many({"pipeline_id": pipeline_id}).deleted_count

    def delete_for_asset(self, asset_id: str) -> int:
        return self.collection.delete_many({"asset_id": asset_id}).deleted_count


def _drop_index_if_exists(collection, index_name: str) -> None:
    try:
        collection.drop_index(index_name)
    except Exception:
        pass
