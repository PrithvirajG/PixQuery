from src.pipelines.ingestion.reconciler import pipeline_version_hash
from src.services.document_serializer import serialize_document, serialize_documents
from src.services.workspace_service import WorkspaceAccessError, role_for


class JobConflictError(RuntimeError):
    """Raised when a job cannot be dispatched in its current state."""


class JobService:
    def __init__(self, repository, publisher_factory):
        self.repository = repository
        self.publisher_factory = publisher_factory

    def list_jobs(self, *, status: str | None = None, limit: int = 100):
        return serialize_documents(self.repository.list_jobs(status=status, limit=limit))

    async def requeue_job(self, job_id: str):
        job = self.repository.requeue_job(job_id)
        if not job:
            return None

        publisher = self.publisher_factory()
        await publisher.connect()
        try:
            await publisher.publish(job_id)
        finally:
            await publisher.close()
        return serialize_document(job)

    async def retrigger_pipeline(self, asset_id: str, pipeline_id: str, *, user_id: str):
        """Manually re-run one pipeline against one asset, overriding its prior outputs.

        Resolves (or creates) the processing job for the pipeline's CURRENT version
        and requeues it — ``start_job`` drops that job's previous pipeline_run and
        model_outputs before reprocessing, so results replace rather than pile up.
        """
        asset = self.repository.get_asset(asset_id)
        if not asset or not asset.get("active"):
            return None
        workspace = (
            self.repository.get_workspace(asset["workspace_id"])
            if asset.get("workspace_id")
            else None
        )
        if not workspace or role_for(workspace, user_id) not in {"owner", "editor"}:
            raise WorkspaceAccessError("Reprocessing an image requires the editor or owner role")

        if pipeline_id not in (workspace.get("pipeline_ids") or []):
            raise JobConflictError(
                "This pipeline is not attached to the image's workspace"
            )
        definition = self.repository.get_pipeline(pipeline_id)
        if not definition:
            return None
        version = pipeline_version_hash(definition.get("nodes", []), definition.get("edges", []))
        job, created = self.repository.ensure_processing_job(
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
        return await self.requeue_job(job["_id"])

