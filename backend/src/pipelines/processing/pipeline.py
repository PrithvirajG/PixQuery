from __future__ import annotations

import math
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from src.config import DEFAULT_PIPELINE_ID, DEFAULT_PIPELINE_VERSION
from src.pipelines.ingestion.reconciler import sha256_file
from src.pipelines.processing.executors.base import PermanentNodeError


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
    repository, pipeline_id: str | None
) -> tuple[dict[str, ResolvedNode], list[dict[str, Any]]]:
    """Resolve a stored pipeline definition into (nodes_by_id, edges).

    Falls back to ``DEFAULT_PIPELINE_NODES`` (as a straight chain) when the pipeline
    id has no stored definition. A definition with nodes but no stored ``edges`` —
    e.g. one written directly in a test — is chained in node order, so a linear
    pipeline stays linear.
    """
    definition = repository.get_pipeline(pipeline_id) if pipeline_id else None
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
        library_node = repository.get_pipeline_node(node["pipeline_node_id"])
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
    """Kahn's algorithm over the DAG. Raises on unknown edge refs or a cycle.

    Zero-indegree nodes are processed in insertion order, so a linear pipeline
    executes in its authored order and results are deterministic.
    """
    indegree = {nid: 0 for nid in nodes_by_id}
    adjacency: dict[str, list[str]] = {nid: [] for nid in nodes_by_id}
    for edge in edges:
        frm, to = edge["from_node_id"], edge["to_node_id"]
        if frm not in nodes_by_id or to not in nodes_by_id:
            raise PermanentNodeError(f"Edge references an unknown node ({frm} → {to})")
        adjacency[frm].append(to)
        indegree[to] += 1
    ready = [nid for nid in nodes_by_id if indegree[nid] == 0]
    order: list[str] = []
    while ready:
        nid = ready.pop(0)
        order.append(nid)
        for nxt in adjacency[nid]:
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                ready.append(nxt)
    if len(order) != len(nodes_by_id):
        raise PermanentNodeError("Pipeline graph has a cycle")
    return order


class DynamicPipeline:
    """Executes a job's pipeline definition node-by-node.

    The executor lookup, embedding store, and image loader are injectable so the
    orchestration can be unit-tested without model weights or real image files.
    """

    pipeline_id = DEFAULT_PIPELINE_ID
    pipeline_version = DEFAULT_PIPELINE_VERSION

    def __init__(
        self,
        embedding_store=None,
        *,
        get_executor: Callable[[str], Any] | None = None,
        image_loader: Callable[[dict[str, Any]], Any] | None = None,
    ):
        self.embedding_store = embedding_store
        self._get_executor = get_executor or _default_get_executor
        self._image_loader = image_loader or _default_image_loader

    def run_job(self, repository, job_id: str) -> None:
        pipeline_run_id = None
        try:
            job = repository.start_job(job_id)
            pipeline_run_id = job["pipeline_run_id"]
            asset = repository.get_asset(job["asset_id"])
            if not asset or not asset.get("active"):
                raise ValueError(f"Asset is inactive or missing for job {job_id}")

            image = self._image_loader(asset)

            # EXIF/GPS metadata is a pipeline-wide setting, not a node: read it from
            # the ORIGINAL file so the result is independent of any transform node.
            self._maybe_extract_metadata(repository, job, asset, pipeline_run_id)

            final_context = self._run_graph(
                repository, job, asset, image, pipeline_run_id
            )

            self._store_embeddings(job, asset, final_context)
            repository.complete_job(job_id, pipeline_run_id)
        except Exception as exc:
            repository.fail_job(
                job_id,
                pipeline_run_id,
                {
                    "class": exc.__class__.__name__,
                    "message": str(exc),
                    "trace": traceback.format_exc(limit=8),
                },
                # Config errors (unknown/unbuilt node, cycle, missing input) can't
                # succeed on retry — fail them now instead of looping with backoff.
                permanent=isinstance(exc, PermanentNodeError),
            )
            raise

    def _run_graph(self, repository, job, asset, image, pipeline_run_id) -> dict[str, Any]:
        """Execute the pipeline DAG and return the merged final context.

        Each node runs once, in topological order. A node's input context is built
        from its incoming edges: with no explicit port mapping it inherits its
        parent's full context (so a straight chain threads ``image`` through exactly
        as a linear pipeline did); with ``from_output``/``to_input`` it pulls a
        single named value (used to disambiguate fan-in). Because each node builds
        its own context copy, divergent branches don't clobber one another.
        """
        nodes_by_id, edges = _resolve_pipeline_graph(repository, job["pipeline_id"])
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
            self._persist_outputs(repository, job, asset, pipeline_run_id, node, executor, updates)
            outputs[nid] = {**context, **updates}

        # Merge every node's outputs (topological order, last write wins) so the
        # embedding step sees embeddings/caption regardless of which node made them.
        final_context: dict[str, Any] = {"asset": asset, "image": image}
        for nid in order:
            for key, value in outputs[nid].items():
                if key != "asset":
                    final_context[key] = value
        return final_context

    def _maybe_extract_metadata(self, repository, job, asset, pipeline_run_id) -> None:
        """Persist EXIF/GPS/dimension metadata if the pipeline enables it.

        Driven by ``PipelineDefinition.extract_metadata`` rather than a node, and
        read from the original file on disk — so it captures true camera metadata
        regardless of resize/grayscale nodes. Failures here never fail the job.
        """
        pipeline_id = job.get("pipeline_id")
        definition = repository.get_pipeline(pipeline_id) if pipeline_id else None
        if not definition or not definition.get("extract_metadata"):
            return
        try:
            from src.pipelines.processing.executors.builtin import extract_image_metadata

            metadata = extract_image_metadata(asset["current_path"])
        except Exception:
            return  # metadata is best-effort; never block processing on it
        repository.add_model_output(
            asset_id=asset["_id"],
            pipeline_run_id=pipeline_run_id,
            model_name="exif",
            model_version="pillow",
            output_type="metadata",
            payload={"metadata": metadata},
            node_type="metadata",
            order=-1,
            workspace_id=asset.get("workspace_id"),
            pipeline_id=pipeline_id,
            pipeline_version=job.get("pipeline_version"),
        )

    def _persist_outputs(self, repository, job, asset, pipeline_run_id, node, executor, updates):
        for key, value in updates.items():
            if key in _PERSIST_SKIP_KEYS:
                continue
            output_type, payload = _shape_output(key, value)
            repository.add_model_output(
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
        image_embedding = _normalize(context.get("embeddings"))
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
        text_embedding = _normalize(context.get("text_embedding"))
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
    from src.pipelines.processing.executors.registry import get_executor

    return get_executor(node_type)


def _default_image_loader(asset: dict[str, Any]):
    from PIL import Image

    path = Path(asset["current_path"])
    if not path.exists():
        raise FileNotFoundError(str(path))
    if sha256_file(path) != asset["content_sha256"]:
        raise ValueError(f"File hash changed before processing: {path}")
    return Image.open(path).convert("RGB")


def _normalize(vector) -> list[float] | None:
    """L2-normalize a vector (numpy array or list) to a plain list of floats."""
    if vector is None:
        return None
    values = [float(v) for v in vector]
    norm = math.sqrt(sum(v * v for v in values))
    if norm == 0:
        return values
    return [v / norm for v in values]


class DefaultImageAnalysisPipeline:
    """Legacy fixed pipeline (YOLO -> BLIP -> CLIP).

    Retained for backward compatibility; the worker now uses DynamicPipeline.
    """

    pipeline_id = DEFAULT_PIPELINE_ID
    pipeline_version = DEFAULT_PIPELINE_VERSION

    def __init__(self, embedding_store=None):
        from src.pipelines.processing.models.blip import BlipModel
        from src.pipelines.processing.models.clip import ClipModel
        from src.pipelines.processing.models.yolo import YoloModel

        self.embedding_store = embedding_store
        self.yolo = YoloModel()
        self.blip = BlipModel()
        self.clip = ClipModel()

    def run_job(self, repository, job_id: str) -> None:
        pipeline_run_id = None
        try:
            job = repository.start_job(job_id)
            pipeline_run_id = job["pipeline_run_id"]
            asset = repository.get_asset(job["asset_id"])
            if not asset or not asset.get("active"):
                raise ValueError(f"Asset is inactive or missing for job {job_id}")

            path = Path(asset["current_path"])
            if not path.exists():
                raise FileNotFoundError(str(path))
            if sha256_file(path) != asset["content_sha256"]:
                raise ValueError(f"File hash changed before processing: {path}")

            from PIL import Image

            image = Image.open(path).convert("RGB")
            detections = self.yolo.detect(image=image, write_image=False)
            caption = self.blip.describe(image)
            image_embedding = _normalize(self.clip.embed(image))
            text_embedding = _normalize(self.clip.embed_text(caption or ""))

            repository.add_model_output(
                asset_id=asset["_id"],
                pipeline_run_id=pipeline_run_id,
                model_name="yolo",
                model_version="v8n",
                output_type="detections",
                payload={"detections": detections or []},
            )
            repository.add_model_output(
                asset_id=asset["_id"],
                pipeline_run_id=pipeline_run_id,
                model_name="blip",
                model_version="image-captioning-base",
                output_type="caption",
                payload={"text": caption},
            )

            if self.embedding_store and image_embedding is not None:
                base_props = {
                    "asset_id": asset["_id"],
                    "content_sha256": asset["content_sha256"],
                    "pipeline_id": job["pipeline_id"],
                    "pipeline_version": job["pipeline_version"],
                    "active": bool(asset.get("active", True)),
                }
                self.embedding_store.upsert_image_embedding(
                    vector=image_embedding,
                    properties=base_props,
                )
                if text_embedding is not None:
                    self.embedding_store.upsert_text_embedding(
                        vector=text_embedding,
                        properties={**base_props, "text": caption or ""},
                    )
            repository.complete_job(job_id, pipeline_run_id)
        except Exception as exc:
            repository.fail_job(
                job_id,
                pipeline_run_id,
                {
                    "class": exc.__class__.__name__,
                    "message": str(exc),
                    "trace": traceback.format_exc(limit=8),
                },
            )
            raise
