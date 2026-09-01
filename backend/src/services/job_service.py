from src.errors.jobs import JobConflictError
from src.errors.workspaces import WorkspaceAccessError
from src.logging_config import get_logger
from src.repositories.image_assets_repository import ImageAssetsRepository
from src.repositories.pipeline_definitions_repository import PipelineDefinitionsRepository
from src.repositories.processing_jobs_repository import ProcessingJobsRepository
from src.repositories.workspace_definitions_repository import WorkspaceDefinitionsRepository
from src.services.document_serializer import serialize_document, serialize_documents
from src.services.pipeline_versioning import pipeline_version_hash
from src.services.workspace_service import role_for

logger = get_logger(__name__)


class JobService:
    def __init__(
        self,
        *,
        jobs: ProcessingJobsRepository,
        assets: ImageAssetsRepository,
        workspaces: WorkspaceDefinitionsRepository,
        pipelines: PipelineDefinitionsRepository,
        publisher_factory,
    ):
        self.jobs = jobs
        self.assets = assets
        self.workspaces = workspaces
        self.pipelines = pipelines
        self.publisher_factory = publisher_factory

    def list_jobs(self, *, status: str | None = None, limit: int = 100):
        return serialize_documents(self.jobs.list_all(status=status, limit=limit))

    async def requeue_job(self, job_id: str):
        job = self.jobs.requeue(job_id)
        if not job:
            return None

        publisher = self.publisher_factory()
        await publisher.connect()
        try:
            await publisher.publish(job_id)
        finally:
            await publisher.close()
        logger.info("Job requeued job_id=%s asset_id=%s", job_id, job.get("asset_id"))
        return serialize_document(job)

    async def retrigger_pipeline(self, asset_id: str, pipeline_id: str, *, user_id: str):
        """Manually re-run one pipeline against one asset, overriding its prior outputs.

        Resolves (or creates) the processing job for the pipeline's CURRENT version
        and requeues it — ``start_job`` drops that job's previous pipeline_run and
        model_outputs before reprocessing, so results replace rather than pile up.
        """
        asset = self.assets.get(asset_id)
        if not asset or not asset.get("active"):
            return None
        workspace = (
            self.workspaces.get(asset["workspace_id"])
            if asset.get("workspace_id")
            else None
        )
        if not workspace or role_for(workspace, user_id) not in {"owner", "editor"}:
            raise WorkspaceAccessError("Reprocessing an image requires the editor or owner role")

        if pipeline_id not in (workspace.get("pipeline_ids") or []):
            raise JobConflictError(
                "This pipeline is not attached to the image's workspace"
            )
        definition = self.pipelines.get(pipeline_id)
        if not definition:
            return None
        version = pipeline_version_hash(definition.get("nodes", []), definition.get("edges", []))
        job, created = self.jobs.get_or_create(
            asset_id=asset_id,
            pipeline_id=pipeline_id,
            pipeline_version=version,
            workspace_id=asset.get("workspace_id"),
        )
        # A job we just created starts life as "queued" and still needs dispatching;
        # only a PRE-EXISTING in-flight job would be double-dispatched by requeuing.
        if not created and job.get("status") in {"queued", "processing"}:
            raise JobConflictError(
                f"This pipeline is already {job['status']} for this image"
            )
        logger.info(
            "Pipeline retriggered asset_id=%s pipeline_id=%s by user_id=%s",
            asset_id, pipeline_id, user_id,
        )
        return await self.requeue_job(job["_id"])
