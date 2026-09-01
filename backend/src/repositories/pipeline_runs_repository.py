"""Pure data access for the ``pipeline_runs`` collection."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from src.models import PipelineRun
from src.utils.time import utcnow


class PipelineRunsRepository:
    def __init__(self, database):
        self.collection = database["pipeline_runs"]

    def create(
        self, *, job_id: str, asset_id: str, pipeline_id: str, pipeline_version: str
    ) -> dict[str, Any]:
        run = PipelineRun(
            job_id=job_id,
            asset_id=asset_id,
            pipeline_id=pipeline_id,
            pipeline_version=pipeline_version,
            started_at=utcnow(),
        ).to_doc()
        self.collection.insert_one(run)
        return run

    def get(self, run_id: str) -> dict[str, Any] | None:
        return self.collection.find_one({"_id": run_id})

    def list_for_asset(self, asset_id: str) -> list[dict[str, Any]]:
        return list(self.collection.find({"asset_id": asset_id}))

    def list_for_asset_pipeline(self, asset_id: str, pipeline_id: str) -> list[dict[str, Any]]:
        return list(self.collection.find({"asset_id": asset_id, "pipeline_id": pipeline_id}))

    def list_for_job(self, job_id: str) -> list[dict[str, Any]]:
        return list(self.collection.find({"job_id": job_id}))

    def list_for_jobs(self, job_ids: list[str]) -> list[dict[str, Any]]:
        if not job_ids:
            return []
        return list(self.collection.find({"job_id": {"$in": job_ids}}))

    def list_for_pipeline(self, pipeline_id: str) -> list[dict[str, Any]]:
        return list(self.collection.find({"pipeline_id": pipeline_id}))

    def update_status(
        self,
        run_id: str,
        *,
        status: str,
        finished_at: datetime | None = None,
        error: dict[str, Any] | None = None,
    ) -> None:
        self.collection.update_one(
            {"_id": run_id},
            {"$set": {"status": status, "finished_at": finished_at, "error": error}},
        )

    def delete_by_ids(self, run_ids: list[str]) -> int:
        if not run_ids:
            return 0
        return self.collection.delete_many({"_id": {"$in": run_ids}}).deleted_count

    def delete_for_job(self, job_id: str) -> int:
        return self.collection.delete_many({"job_id": job_id}).deleted_count

    def delete_for_jobs(self, job_ids: list[str]) -> int:
        if not job_ids:
            return 0
        return self.collection.delete_many({"job_id": {"$in": job_ids}}).deleted_count

    def delete_for_pipeline(self, pipeline_id: str) -> int:
        return self.collection.delete_many({"pipeline_id": pipeline_id}).deleted_count

    def delete_for_asset(self, asset_id: str) -> int:
        return self.collection.delete_many({"asset_id": asset_id}).deleted_count
