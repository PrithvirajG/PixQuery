from __future__ import annotations

from typing import Any
from uuid import uuid4

from src.domain_events import outputs_cleared_event
from src.errors.graph import GraphCycleError, UnknownNodeError
from src.errors.pipelines import PipelineValidationError
from src.infrastructure.messaging import EventSink
from src.repositories.model_outputs_repository import ModelOutputsRepository
from src.repositories.pipeline_definitions_repository import PipelineDefinitionsRepository
from src.repositories.pipeline_nodes_repository import PipelineNodesRepository
from src.repositories.pipeline_runs_repository import PipelineRunsRepository
from src.repositories.processing_jobs_repository import ProcessingJobsRepository
from src.repositories.workspace_definitions_repository import WorkspaceDefinitionsRepository
from src.services.document_serializer import serialize_document, serialize_documents
from src.utils.graph import topological_order


class PipelineService:
    def __init__(
        self,
        *,
        pipelines: PipelineDefinitionsRepository,
        nodes: PipelineNodesRepository,
        runs: PipelineRunsRepository,
        outputs: ModelOutputsRepository,
        jobs: ProcessingJobsRepository,
        workspaces: WorkspaceDefinitionsRepository,
        event_sink: EventSink | None = None,
    ):
        self.pipelines = pipelines
        self.nodes = nodes
        self.runs = runs
        self.outputs = outputs
        self.jobs = jobs
        self.workspaces = workspaces
        self.event_sink = event_sink

    # ── Pipeline Node Library ─────────────────────────────────────

    def list_pipeline_nodes(self, *, owner_id: str) -> list[dict[str, Any]]:
        return serialize_documents(self.nodes.list_all(owner_id=owner_id))

    def get_pipeline_node(self, node_id: str) -> dict[str, Any] | None:
        node = self.nodes.get(node_id)
        return serialize_document(node) if node else None

    def create_pipeline_node(self, *, owner_id: str, data: dict[str, Any]) -> dict[str, Any]:
        node = self.nodes.create(
            name=data["name"],
            description=data.get("description", ""),
            node_type=data["node_type"],
            context_inputs=data.get("context_inputs", []),
            context_outputs=data.get("context_outputs", []),
            config_schema=data.get("config_schema", {}),
            default_config=data.get("default_config", {}),
            owner_id=owner_id,
        )
        return serialize_document(node)

    def update_pipeline_node(
        self, node_id: str, *, owner_id: str, data: dict[str, Any]
    ) -> dict[str, Any] | None:
        existing = self.nodes.get(node_id)
        if not existing:
            return None
        if existing.get("owner_id") == "system":
            return None  # system nodes are immutable
        if existing.get("owner_id") != owner_id:
            return None
        updated = self.nodes.update(node_id, data)
        return serialize_document(updated) if updated else None

    def delete_pipeline_node(self, node_id: str, *, owner_id: str) -> bool:
        existing = self.nodes.get(node_id)
        if not existing:
            return False
        if existing.get("owner_id") in ("system", None):
            return False
        if existing.get("owner_id") != owner_id:
            return False
        return self.nodes.delete(node_id)

    # ── Pipeline Definitions ──────────────────────────────────────

    def list_pipelines(self, *, owner_id: str) -> list[dict[str, Any]]:
        return serialize_documents(self.pipelines.list_for_owner(owner_id))

    def get_pipeline(self, pipeline_id: str, *, owner_id: str) -> dict[str, Any] | None:
        pipeline = self.pipelines.get(pipeline_id)
        if not pipeline or pipeline.get("owner_id") != owner_id:
            return None
        return serialize_document(pipeline)

    def create_pipeline(self, *, owner_id: str, data: dict[str, Any]) -> dict[str, Any]:
        nodes, edges = _build_graph(data.get("nodes", []), data.get("edges"))
        pipeline = self.pipelines.create(
            owner_id=owner_id,
            name=data["name"],
            description=data.get("description", ""),
            nodes=nodes,
            edges=edges,
        )
        return serialize_document(pipeline)

    def update_pipeline(
        self, pipeline_id: str, *, owner_id: str, data: dict[str, Any]
    ) -> dict[str, Any] | None:
        existing = self.pipelines.get(pipeline_id)
        if not existing or existing.get("owner_id") != owner_id:
            return None
        updates: dict[str, Any] = {}
        if "name" in data:
            updates["name"] = data["name"]
        if "description" in data:
            updates["description"] = data["description"]
        if "nodes" in data:
            updates["nodes"], updates["edges"] = _build_graph(
                data["nodes"], data.get("edges")
            )
        updated = self.pipelines.update(pipeline_id, updates)
        return serialize_document(updated) if updated else None

    def delete_pipeline(self, pipeline_id: str, *, owner_id: str) -> bool:
        """Delete a pipeline and everything downstream of it.

        Cascade, mirroring ``WorkspaceService.delete_workspace``: the pipeline's
        runs, jobs and model outputs go with it (across every workspace), and the
        id is pulled from any workspace still referencing it — a dangling id would
        otherwise make the reconciler keep minting jobs for a pipeline that no
        longer exists. Assets and the shared pipeline-node library are untouched:
        the images themselves outlive any one pipeline.
        """
        existing = self.pipelines.get(pipeline_id)
        if not existing or existing.get("owner_id") != owner_id:
            return False

        run_ids = [r["_id"] for r in self.runs.list_for_pipeline(pipeline_id)]

        # Outputs carry a denormalized pipeline_id, but older rows may not — also
        # sweep anything tied to this pipeline's runs so nothing is orphaned.
        self.outputs.delete_for_pipeline(pipeline_id)
        self.outputs.delete_for_runs(run_ids)
        self.runs.delete_for_pipeline(pipeline_id)
        self.jobs.delete_for_pipeline(pipeline_id)

        affected_workspaces = [
            ws["_id"] for ws in self.workspaces.list_referencing_pipeline(pipeline_id)
        ]
        for workspace_id in affected_workspaces:
            self.workspaces.remove_pipeline_id(workspace_id, pipeline_id)

        deleted = self.pipelines.delete(pipeline_id)
        if deleted and self.event_sink is not None:
            # One event per affected workspace: any image detail view open on that
            # workspace drops the section instead of showing outputs that are gone.
            for workspace_id in affected_workspaces:
                self.event_sink.emit(
                    outputs_cleared_event(
                        workspace_id=workspace_id,
                        pipeline_id=pipeline_id,
                        counts={"pipeline_deleted": 1},
                    )
                )
        return deleted


def _build_graph(
    raw_nodes: list[dict[str, Any]],
    raw_edges: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Build the stored (nodes, edges) DAG from an API payload.

    Nodes get a stable ``node_id`` and canvas ``position``. Edges are taken as-is
    (validated against node ids) or, when a caller sends none — e.g. the linear
    stage editor — synthesized as a straight chain so ordering is preserved.
    Rejects graphs with a cycle up front so a bad pipeline can never be saved.
    """
    nodes: list[dict[str, Any]] = []
    for i, raw in enumerate(raw_nodes):
        nodes.append(
            {
                "node_id": raw.get("node_id") or str(uuid4()),
                "pipeline_node_id": raw["pipeline_node_id"],
                "config_overrides": raw.get("config_overrides", {}),
                "position": raw.get("position") or {"x": 0, "y": i * 120},
            }
        )
    node_ids = {n["node_id"] for n in nodes}

    if raw_edges:
        edges: list[dict[str, Any]] = []
        for raw in raw_edges:
            frm, to = raw.get("from_node_id"), raw.get("to_node_id")
            if frm not in node_ids or to not in node_ids:
                raise PipelineValidationError(
                    f"Edge references an unknown node ({frm} → {to})."
                )
            edges.append(
                {
                    "edge_id": raw.get("edge_id") or str(uuid4()),
                    "from_node_id": frm,
                    "to_node_id": to,
                    "from_output": raw.get("from_output"),
                    "to_input": raw.get("to_input"),
                }
            )
    else:
        edges = [
            {
                "edge_id": str(uuid4()),
                "from_node_id": nodes[i]["node_id"],
                "to_node_id": nodes[i + 1]["node_id"],
                "from_output": None,
                "to_input": None,
            }
            for i in range(len(nodes) - 1)
        ]

    _assert_acyclic(nodes, edges)
    return nodes, edges


def _assert_acyclic(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> None:
    """Reject a graph that can't be topologically ordered.

    Edge refs are already validated by ``_build_graph`` before this runs, so in
    practice only ``GraphCycleError`` is reachable here — ``UnknownNodeError``
    is caught too, defensively, rather than letting a generic exception leak
    out of the service layer.
    """
    try:
        topological_order((n["node_id"] for n in nodes), edges)
    except (GraphCycleError, UnknownNodeError) as exc:
        raise PipelineValidationError("Pipeline graph has a cycle.") from exc
