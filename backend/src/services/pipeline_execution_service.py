from __future__ import annotations

import traceback
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from src.config import DEFAULT_PIPELINE_ID, DEFAULT_PIPELINE_VERSION
from src.domain_events import pipeline_stage_event, pipeline_state_event
from src.errors.executors import PermanentNodeError
from src.errors.graph import GraphCycleError, UnknownNodeError
from src.infrastructure.messaging import EventSink
from src.repositories.image_assets_repository import ImageAssetsRepository
from src.repositories.model_outputs_repository import ModelOutputsRepository
from src.repositories.pipeline_definitions_repository import PipelineDefinitionsRepository
from src.repositories.pipeline_nodes_repository import PipelineNodesRepository
from src.repositories.pipeline_runs_repository import PipelineRunsRepository
from src.repositories.processing_jobs_repository import ProcessingJobsRepository
from src.utils.files import sha256_file
from src.utils.graph import topological_order
from src.utils.time import utcnow
from src.utils.vectors import normalize


# ──────────────────────────────────────────────────────────────────────────────
# Default node chain — used when a job's pipeline has no stored definition
# (legacy "default_image_analysis" jobs and workspaces with no pipeline assigned).
# Mirrors the historical YOLO -> BLIP -> CLIP behaviour.

DEFAULT_PIPELINE_NODES: list[dict[str, Any]] = [
    {
        "node_type": "object_detection",
        "config": {"model": "yolov8n", "threshold": 0.5},
        "context_inputs": ["image"],
        "context_outputs": ["detections"],
    },
    {
        "node_type": "captioning",
        "config": {"model": "blip-base"},
        "context_inputs": ["image"],
        "context_outputs": ["caption"],
    },
    {
        "node_type": "embedding",
        "config": {"model": "openai/clip-vit-base-patch32"},
        "context_inputs": ["image"],
        "context_outputs": ["embeddings"],
    },
]

# Context keys that are working state, not persisted as model_outputs.
_PERSIST_SKIP_KEYS = {"image", "asset", "embeddings", "text_embedding"}


@dataclass
class ResolvedNode:
    """A pipeline node ready to execute: its type, merged config, and I/O keys."""

    node_type: str
    config: dict[str, Any] = field(default_factory=dict)
    context_inputs: list[str] = field(default_factory=list)
    context_outputs: list[str] = field(default_factory=list)
    order: int = 0
    node_id: str | None = None


def _linear_edges(node_ids: list[str]) -> list[dict[str, Any]]:
    """Chain node ids into a straight line of edges (n0 → n1 → …)."""
    return [
        {"from_node_id": node_ids[i], "to_node_id": node_ids[i + 1],
         "from_output": None, "to_input": None}
        for i in range(len(node_ids) - 1)
    ]


def _resolve_pipeline_graph(
    pipelines: PipelineDefinitionsRepository,
    nodes: PipelineNodesRepository,
    pipeline_id: str | None,
) -> tuple[dict[str, ResolvedNode], list[dict[str, Any]]]:
    """Resolve a stored pipeline definition into (nodes_by_id, edges).

    Falls back to ``DEFAULT_PIPELINE_NODES`` (as a straight chain) when the pipeline
    id has no stored definition. A definition with nodes but no stored ``edges`` —
    e.g. one written directly in a test — is chained in node order, so a linear
    pipeline stays linear.
    """
    definition = pipelines.get(pipeline_id) if pipeline_id else None
    if not definition or not definition.get("nodes"):
        nodes_by_id: dict[str, ResolvedNode] = {}
        for i, n in enumerate(DEFAULT_PIPELINE_NODES):
            nid = f"d{i}"
            nodes_by_id[nid] = ResolvedNode(
                node_type=n["node_type"],
                config=dict(n["config"]),
                context_inputs=list(n["context_inputs"]),
                context_outputs=list(n["context_outputs"]),
                node_id=nid,
            )
        return nodes_by_id, _linear_edges(list(nodes_by_id))

    nodes_by_id = {}
    for node in sorted(definition["nodes"], key=lambda n: n.get("order", 0)):
        library_node = nodes.get(node["pipeline_node_id"])
        if not library_node:
            raise PermanentNodeError(
                f"Pipeline node {node['pipeline_node_id']} not found in node library"
            )
        nid = node.get("node_id") or node["pipeline_node_id"]
        nodes_by_id[nid] = ResolvedNode(
            node_type=library_node["node_type"],
            config={
                **library_node.get("default_config", {}),
                **node.get("config_overrides", {}),
            },
            context_inputs=list(library_node.get("context_inputs", [])),
            context_outputs=list(library_node.get("context_outputs", [])),
            node_id=nid,
        )
    edges = definition.get("edges") or _linear_edges(list(nodes_by_id))
    return nodes_by_id, edges


def _topological_order(
    nodes_by_id: dict[str, ResolvedNode], edges: list[dict[str, Any]]
) -> list[str]:
    """Order this pipeline's nodes so every edge runs parent-before-child.

    Zero-indegree nodes are processed in insertion order, so a linear pipeline
    executes in its authored order and results are deterministic. Delegates the
    actual algorithm to ``utils.graph.topological_order``, translating its
    generic exceptions into ``PermanentNodeError`` — a bad graph can't succeed
    on retry, so it fails the job outright rather than requeuing.
    """
    try:
        return topological_order(nodes_by_id.keys(), edges)
    except UnknownNodeError as exc:
        raise PermanentNodeError(str(exc)) from exc
    except GraphCycleError:
        raise PermanentNodeError("Pipeline graph has a cycle") from None


class PipelineExecutionService:
    """Executes a job's pipeline definition node-by-node.

    Owns the retry policy that used to live on the repository's ``fail_job``:
    ``RETRY_DELAYS``/``MAX_ATTEMPTS`` are a processing decision, not a storage
    fact, so they live here and the repository just persists the outcome. Same
    for job-state events — the repository no longer emits anything, so every
    transition (processing/completed/failed, plus per-node stage progress) is
    announced explicitly through the injected ``event_sink``.

    The executor lookup, embedding store, and image loader are injectable so the
    orchestration can be unit-tested without model weights or real image files.
    """

    RETRY_DELAYS = [60, 300, 900]
    MAX_ATTEMPTS = 3

    def __init__(
        self,
        *,
        jobs: ProcessingJobsRepository,
        runs: PipelineRunsRepository,
        outputs: ModelOutputsRepository,
        assets: ImageAssetsRepository,
        pipelines: PipelineDefinitionsRepository,
        nodes: PipelineNodesRepository,
        embedding_store=None,
        event_sink: EventSink | None = None,
        get_executor: Callable[[str], Any] | None = None,
        image_loader: Callable[[dict[str, Any]], Any] | None = None,
    ):
        self.jobs = jobs
        self.runs = runs
        self.outputs = outputs
        self.assets = assets
        self.pipelines = pipelines
        self.nodes = nodes
        self.embedding_store = embedding_store
        self.event_sink = event_sink
        self._get_executor = get_executor or _default_get_executor
        self._image_loader = image_loader or _default_image_loader

    def run_job(self, job_id: str) -> None:
        pipeline_run_id = None
        try:
            job = self.jobs.start(job_id)
            pipeline_run_id = self._begin_run(job)
            self._emit_state(job, "processing")

            asset = self.assets.get(job["asset_id"])
            if not asset or not asset.get("active"):
                raise ValueError(f"Asset is inactive or missing for job {job_id}")

            image = self._image_loader(asset)

            # EXIF/GPS metadata is always extracted (not a node, not a per-pipeline
            # setting): read it from the ORIGINAL file so the result is independent
            # of any transform node.
            self._maybe_extract_metadata(asset)

            final_context = self._run_graph(job, asset, image, pipeline_run_id)

            self._store_embeddings(job, asset, final_context)
            self.jobs.complete(job_id)
            self.runs.update_status(pipeline_run_id, status="completed", finished_at=utcnow(), error=None)
            self._emit_state({**job, "last_error": None}, "completed")
        except Exception as exc:
            error = {
                "class": exc.__class__.__name__,
                "message": str(exc),
                "trace": traceback.format_exc(limit=8),
            }
            # Config errors (unknown/unbuilt node, cycle, missing input) can't
            # succeed on retry — fail them now instead of looping with backoff.
            self._fail(job_id, pipeline_run_id, error, permanent=isinstance(exc, PermanentNodeError))
            raise

    def _begin_run(self, job: dict[str, Any]) -> str:
        """Start a fresh pipeline_run for this job.

        Reprocessing replaces, not accumulates: drop this job's previous runs
        and their model outputs first so a re-scan/retry doesn't pile up
        duplicate outputs.
        """
        prior_run_ids = [r["_id"] for r in self.runs.list_for_job(job["_id"])]
        self.outputs.delete_for_runs(prior_run_ids)
        self.runs.delete_for_job(job["_id"])
        run = self.runs.create(
            job_id=job["_id"],
            asset_id=job["asset_id"],
            pipeline_id=job["pipeline_id"],
            pipeline_version=job["pipeline_version"],
        )
        return run["_id"]

    def _fail(
        self,
        job_id: str,
        pipeline_run_id: str | None,
        error: dict[str, Any],
        *,
        permanent: bool,
    ) -> None:
        job = self.jobs.get(job_id)
        attempts = int(job.get("attempt_count", 0)) if job else self.MAX_ATTEMPTS
        final_status = "failed" if (permanent or attempts >= self.MAX_ATTEMPTS) else "queued"
        next_attempt_at: datetime | None = None
        if final_status == "queued":
            next_attempt_at = utcnow() + timedelta(
                seconds=self.RETRY_DELAYS[min(attempts - 1, 2)]
            )
        self.jobs.fail(job_id, final_status=final_status, next_attempt_at=next_attempt_at, error=error)
        if pipeline_run_id:
            self.runs.update_status(pipeline_run_id, status="failed", finished_at=utcnow(), error=error)
        # `final_status` is "queued" when a retry is still pending, so the UI shows
        # the pair going back to waiting rather than reporting a failure it will
        # recover from on its own.
        if job:
            self._emit_state({**job, "last_error": error}, final_status)

    def _emit_state(self, job: dict[str, Any] | None, state: str) -> None:
        if self.event_sink is None or not job:
            return
        self.event_sink.emit(
            pipeline_state_event(
                workspace_id=job.get("workspace_id"),
                asset_id=job.get("asset_id"),
                pipeline_id=job.get("pipeline_id"),
                state=state,
                job_id=job.get("_id"),
                error=job.get("last_error"),
            )
        )

    def _run_graph(self, job, asset, image, pipeline_run_id) -> dict[str, Any]:
        """Execute the pipeline DAG and return the merged final context.

        Each node runs once, in topological order. A node's input context is built
        from its incoming edges: with no explicit port mapping it inherits its
        parent's full context (so a straight chain threads ``image`` through exactly
        as a linear pipeline did); with ``from_output``/``to_input`` it pulls a
        single named value (used to disambiguate fan-in). Because each node builds
        its own context copy, divergent branches don't clobber one another.
        """
        nodes_by_id, edges = _resolve_pipeline_graph(self.pipelines, self.nodes, job["pipeline_id"])
        order = _topological_order(nodes_by_id, edges)

        incoming: dict[str, list[dict[str, Any]]] = {nid: [] for nid in nodes_by_id}
        for edge in edges:
            incoming[edge["to_node_id"]].append(edge)

        outputs: dict[str, dict[str, Any]] = {}  # node_id → its accumulated context
        for topo_index, nid in enumerate(order):
            node = nodes_by_id[nid]
            context: dict[str, Any] = {"asset": asset}
            in_edges = incoming[nid]
            if not in_edges:
                context["image"] = image  # source nodes get the original image
            for edge in in_edges:
                parent = outputs[edge["from_node_id"]]
                if edge.get("from_output") or edge.get("to_input"):
                    src = edge.get("from_output") or edge.get("to_input")
                    dst = edge.get("to_input") or edge.get("from_output")
                    context[dst] = parent.get(src)
                else:
                    for key, value in parent.items():
                        if key != "asset":
                            context[key] = value

            missing = [key for key in node.context_inputs if key not in context]
            if missing:
                raise PermanentNodeError(
                    f"Node '{node.node_type}' requires {missing} "
                    f"which no upstream node produced"
                )
            executor = self._get_executor(node.node_type)
            updates = executor.run(context, node.config) or {}
            node.order = topo_index
            self._persist_outputs(job, asset, pipeline_run_id, node, executor, updates)
            outputs[nid] = {**context, **updates}
            # Announce progress *within* the run, so a watching UI can show
            # "stage 3 of 5 · captioning" instead of one opaque "processing" span.
            if self.event_sink is not None:
                self.event_sink.emit(
                    pipeline_stage_event(
                        workspace_id=asset.get("workspace_id"),
                        asset_id=asset["_id"],
                        pipeline_id=job.get("pipeline_id"),
                        node_id=node.node_id,
                        node_type=node.node_type,
                        index=topo_index + 1,
                        total=len(order),
                    )
                )

        # Merge every node's outputs (topological order, last write wins) so the
        # embedding step sees embeddings/caption regardless of which node made them.
        final_context: dict[str, Any] = {"asset": asset, "image": image}
        for nid in order:
            for key, value in outputs[nid].items():
                if key != "asset":
                    final_context[key] = value
        return final_context

    def _maybe_extract_metadata(self, asset) -> None:
        """Extract EXIF/GPS/dimension metadata and persist it onto the asset itself.

        Always runs, for every job — not a node, not a per-pipeline setting — and
        reads from the original file on disk, so it captures true camera metadata
        regardless of resize/grayscale nodes. Stored on the asset (not
        model_outputs): it's generic file info, not a pipeline output, so it isn't
        scoped to a particular pipeline run. Failures here never fail the job.
        """
        try:
            from src.utils.exif import extract_image_metadata

            metadata = extract_image_metadata(asset["current_path"])
        except Exception:
            return  # metadata is best-effort; never block processing on it
        self.assets.update_metadata(asset["_id"], metadata)

    def _persist_outputs(self, job, asset, pipeline_run_id, node, executor, updates):
        for key, value in updates.items():
            if key in _PERSIST_SKIP_KEYS:
                continue
            output_type, payload = _shape_output(key, value)
            self.outputs.add(
                asset_id=asset["_id"],
                pipeline_run_id=pipeline_run_id,
                model_name=getattr(executor, "model_name", "") or node.node_type,
                model_version=getattr(executor, "model_version", "") or "v1",
                output_type=output_type,
                payload=payload,
                node_id=node.node_id,
                node_type=node.node_type,
                order=node.order,
                workspace_id=asset.get("workspace_id"),
                pipeline_id=job.get("pipeline_id"),
                pipeline_version=job.get("pipeline_version"),
            )

    def _store_embeddings(self, job, asset, context) -> None:
        if not self.embedding_store:
            return
        image_embedding = normalize(context.get("embeddings"))
        if image_embedding is None:
            return
        base_props = {
            "asset_id": asset["_id"],
            "content_sha256": asset["content_sha256"],
            "workspace_id": asset.get("workspace_id"),
            "pipeline_id": job["pipeline_id"],
            "pipeline_version": job["pipeline_version"],
            "active": bool(asset.get("active", True)),
        }
        self.embedding_store.upsert_image_embedding(
            vector=image_embedding, properties=base_props
        )
        text_embedding = normalize(context.get("text_embedding"))
        if text_embedding is not None:
            self.embedding_store.upsert_text_embedding(
                vector=text_embedding,
                properties={**base_props, "text": context.get("caption") or ""},
            )


def _shape_output(key: str, value: Any) -> tuple[str, dict[str, Any]]:
    """Map a context key to a (output_type, payload) for model_outputs.

    Captions and detections keep their historical shape so search and the image
    detail view continue to work; everything else is stored generically.
    """
    if key == "caption":
        return "caption", {"text": value or ""}
    if key == "ocr_text":
        return "ocr", {"text": value or ""}
    if key == "detections":
        return "detections", {"detections": value or []}
    return key, {key: value}


def _default_get_executor(node_type: str):
    from src.services.executors.registry import get_executor

    return get_executor(node_type)


def _default_image_loader(asset: dict[str, Any]):
    from PIL import Image

    path = Path(asset["current_path"])
    if not path.exists():
        raise FileNotFoundError(str(path))
    if sha256_file(path) != asset["content_sha256"]:
        raise ValueError(f"File hash changed before processing: {path}")
    return Image.open(path).convert("RGB")
