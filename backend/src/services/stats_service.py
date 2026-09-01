from __future__ import annotations

from typing import Any

from src.repositories.file_observations_repository import FileObservationsRepository
from src.repositories.image_assets_repository import ImageAssetsRepository
from src.repositories.pipeline_definitions_repository import PipelineDefinitionsRepository
from src.repositories.processing_jobs_repository import ProcessingJobsRepository
from src.repositories.workspace_definitions_repository import WorkspaceDefinitionsRepository
from src.services.access_scope import accessible_asset_ids
from src.services.document_serializer import serialize_documents


class StatsService:
    def __init__(
        self,
        *,
        workspaces: WorkspaceDefinitionsRepository,
        observations: FileObservationsRepository,
        assets: ImageAssetsRepository,
        pipelines: PipelineDefinitionsRepository,
        jobs: ProcessingJobsRepository,
    ):
        self.workspaces = workspaces
        self.observations = observations
        self.assets = assets
        self.pipelines = pipelines
        self.jobs = jobs

    def get_overview(self, *, owner_id: str) -> dict[str, Any]:
        workspaces = self.workspaces.list_for_owner(owner_id)
        asset_ids = list(accessible_asset_ids(self.workspaces, self.observations, owner_id))

        total_images = self.assets.count_by_ids(asset_ids, active_only=True)
        active_workspaces = sum(1 for ws in workspaces if ws.get("active"))
        pipelines_defined = self.pipelines.count_for_owner(owner_id)

        return {
            "total_images": total_images,
            "active_workspaces": active_workspaces,
            "pipelines_defined": pipelines_defined,
            "jobs_queued": self.jobs.count_by_status(asset_ids, "queued"),
            "jobs_processing": self.jobs.count_by_status(asset_ids, "processing"),
            "jobs_completed": self.jobs.count_by_status(asset_ids, "completed"),
            "jobs_failed": self.jobs.count_by_status(asset_ids, "failed"),
        }

    def list_recent_jobs(self, *, user_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        if user_id is not None:
            asset_ids = list(accessible_asset_ids(self.workspaces, self.observations, user_id))
            jobs = self.jobs.list_for_asset_ids(asset_ids, limit=limit)
        else:
            jobs = self.jobs.list_all(limit=limit)
        return serialize_documents(jobs)
