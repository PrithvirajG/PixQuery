from src.repositories.image_assets_repository import ImageAssetsRepository
from src.repositories.file_observations_repository import FileObservationsRepository
from src.repositories.model_outputs_repository import ModelOutputsRepository
from src.repositories.pipeline_definitions_repository import PipelineDefinitionsRepository
from src.repositories.pipeline_runs_repository import PipelineRunsRepository
from src.repositories.processing_jobs_repository import ProcessingJobsRepository
from src.repositories.workspace_definitions_repository import WorkspaceDefinitionsRepository
from src.services.access_scope import accessible_asset_ids, can_access_asset
from src.services.document_serializer import serialize_document, serialize_documents
from src.utils.collections import top_by_frequency


class ImageService:
    def __init__(
        self,
        *,
        assets: ImageAssetsRepository,
        observations: FileObservationsRepository,
        workspaces: WorkspaceDefinitionsRepository,
        pipelines: PipelineDefinitionsRepository,
        jobs: ProcessingJobsRepository,
        runs: PipelineRunsRepository,
        outputs: ModelOutputsRepository,
    ):
        self.assets = assets
        self.observations = observations
        self.workspaces = workspaces
        self.pipelines = pipelines
        self.jobs = jobs
        self.runs = runs
        self.outputs = outputs

    def list_images(self, *, user_id: str | None = None, limit: int = 100, skip: int = 0):
        if user_id is not None:
            scope = accessible_asset_ids(self.workspaces, self.observations, user_id)
            assets = self.assets.list_by_ids(scope, limit=limit, skip=skip)
        else:
            assets = self.assets.list_all(active_only=True, limit=limit, skip=skip)
        return serialize_documents(assets)

    def get_image(self, asset_id: str, *, user_id: str | None = None):
        asset = self.assets.get(asset_id)
        if not asset or not asset.get("active"):
            return None
        # Access is granted when the asset is observed in a workspace the user can reach.
        if user_id is not None and not can_access_asset(
            self.workspaces, self.observations, user_id, asset_id
        ):
            return None
        return serialize_document(asset)

    def get_image_detail(self, asset_id: str, *, user_id: str | None = None):
        """Image plus its caption, detections, and processing provenance.

        Provenance lets the detail view explain where each signal came from:
        which model/version produced it, which pipeline node and run, and when.
        """
        asset = self.get_image(asset_id, user_id=user_id)
        if not asset:
            return None

        outputs = self.outputs.list_for_asset(asset_id)
        caption = next(
            (o["payload"].get("text", "") for o in outputs if o.get("output_type") == "caption"),
            "",
        )
        # Merge every detections output (object + face detectors may each emit one)
        # so the overlay shows all boxes, not just the first detector's.
        detections: list = []
        for o in outputs:
            if o.get("output_type") == "detections":
                detections.extend(o["payload"].get("detections", []) or [])
        return {
            **asset,
            "description": caption,
            "detections": detections,
            "provenance": self._build_provenance(asset, outputs),
        }

    def _build_provenance(self, asset: dict, outputs: list[dict]):
        """One entry per pipeline attached to this asset's workspace, with its state.

        Driven by the workspace's ``pipeline_ids`` — NOT by which outputs happen to
        exist — so a pipeline that has never run (or whose outputs were cleared)
        still gets a section, and the UI can offer "Process"/"Reprocess" for it.
        Each entry carries a ``state`` derived from the job for this
        (asset, pipeline) pair; see ``_pipeline_state``.
        """
        asset_id = asset["_id"]
        runs = self.runs.list_for_asset(asset_id)
        run_by_id = {r["_id"]: r for r in runs}
        jobs = self.jobs.list_for_asset(asset_id)
        job_by_pipeline = {j.get("pipeline_id"): j for j in jobs}

        outputs_by_pipeline: dict = {}
        for o in outputs:
            pid = o.get("pipeline_id") or (run_by_id.get(o.get("pipeline_run_id")) or {}).get("pipeline_id")
            outputs_by_pipeline.setdefault(pid, []).append(o)

        workspace = (
            self.workspaces.get(asset["workspace_id"])
            if asset.get("workspace_id")
            else None
        )
        attached_ids = list((workspace or {}).get("pipeline_ids", []) or [])

        # Attached pipelines always get a section (even with zero outputs, so they
        # can be run). Pipelines that only have leftover outputs — detached from the
        # workspace since they ran — are still listed, flagged `attached: False`, so
        # their data is visible and clearable rather than silently orphaned.
        detached_ids = [
            pid for pid in outputs_by_pipeline if pid is not None and pid not in attached_ids
        ]

        pipelines = []
        for pid in attached_ids + detached_ids:
            definition = self.pipelines.get(pid)
            outs = outputs_by_pipeline.get(pid, [])
            if not definition and not outs:
                continue  # deleted pipeline with nothing left to show
            outs.sort(key=lambda x: (x.get("order") is None, x.get("order") or 0))
            runs_for = [r for r in runs if r.get("pipeline_id") == pid]
            latest = max(runs_for, key=lambda r: r.get("started_at") or "", default=None)
            job = job_by_pipeline.get(pid)
            pipelines.append({
                "pipeline_id": pid,
                "name": (definition or {}).get("name") or pid,
                # Only an attached pipeline can be run against this image; a detached
                # one is read-only history until its outputs are cleared.
                "attached": pid in attached_ids,
                "pipeline_version": (latest or {}).get("pipeline_version")
                    or (outs[0].get("pipeline_version") if outs else None),
                "state": _pipeline_state(job, outs),
                # Legacy field: the raw pipeline_run status. Prefer `state`.
                "status": (latest or {}).get("status"),
                "last_error": (job or {}).get("last_error"),
                "started_at": _iso((latest or {}).get("started_at")),
                "finished_at": _iso((latest or {}).get("finished_at")),
                "outputs": [self._output_item(o) for o in outs],
            })
        pipelines.sort(key=lambda p: (p["name"] or "").lower())
        return {"pipelines": pipelines}

    @staticmethod
    def _output_item(o: dict):
        payload = o.get("payload") or {}
        return {
            "output_type": o.get("output_type"),
            "model_name": o.get("model_name"),
            "model_version": o.get("model_version"),
            "node_type": o.get("node_type"),
            "order": o.get("order"),
            "created_at": _iso(o.get("created_at")),
            "summary": _summarize(o.get("output_type"), payload),
            "payload": payload,
        }


# Lifecycle of one (image, pipeline) pair, as shown in the UI. A pipeline with no
# job row has never been picked up by the reconciler; clearing a pipeline's outputs
# deletes its job rows, which returns the pair to NOT_STARTED.
NOT_STARTED = "not_started"
QUEUED = "queued"
PROCESSING = "processing"
COMPLETED = "completed"
FAILED = "failed"

_JOB_STATUS_TO_STATE = {
    "queued": QUEUED,
    "processing": PROCESSING,
    "completed": COMPLETED,
    "failed": FAILED,
}


def _pipeline_state(job: dict | None, outputs: list[dict]) -> str:
    """Derive the (image, pipeline) state from its processing job.

    No job row means nothing has ever been dispatched for this pair — NOT_STARTED.
    A job marked ``completed`` whose outputs have since been cleared is also
    NOT_STARTED: there is nothing to show, and the pair is ready to run again.
    """
    if not job:
        return NOT_STARTED
    state = _JOB_STATUS_TO_STATE.get(job.get("status"), NOT_STARTED)
    if state == COMPLETED and not outputs:
        return NOT_STARTED
    return state


def _summarize(output_type: str, payload: dict) -> str:
    """A short human-readable line describing an output's payload."""
    if output_type == "caption":
        return payload.get("text", "") or "—"
    if output_type == "ocr":
        text = (payload.get("text") or "").strip().replace("\n", " ")
        return (text[:120] + "…") if len(text) > 120 else (text or "—")
    if output_type == "detections":
        dets = payload.get("detections", []) or []
        labels = top_by_frequency([d.get("label") for d in dets])
        return f"{len(dets)} detection{'' if len(dets) == 1 else 's'}" + (f": {labels}" if labels else "")
    if output_type == "labels":
        labels = payload.get("labels", []) or []
        return ", ".join(f"{l.get('label')} ({float(l.get('confidence', 0)):.2f})" for l in labels[:3]) or "—"
    if output_type == "metadata":
        meta = payload.get("metadata", {}) or {}
        bits = []
        if meta.get("width") and meta.get("height"):
            bits.append(f"{meta['width']}×{meta['height']}")
        for key in ("camera_make", "camera_model", "datetime_original"):
            if meta.get(key):
                bits.append(str(meta[key]))
        if meta.get("gps_latitude") is not None and meta.get("gps_longitude") is not None:
            bits.append(f"GPS {meta['gps_latitude']:.4f},{meta['gps_longitude']:.4f}")
        return " · ".join(bits) or "dimensions only"
    if output_type == "written_image":
        wi = payload.get("written_image", {}) or {}
        return wi.get("path", "—")
    # generic: list the payload keys
    return ", ".join(payload.keys()) or "—"


def _iso(value):
    return value.isoformat() if hasattr(value, "isoformat") else value
