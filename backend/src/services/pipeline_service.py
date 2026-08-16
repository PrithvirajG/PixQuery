from __future__ import annotations

from typing import Any
from uuid import uuid4

from src.services.document_serializer import serialize_document, serialize_documents


class PipelineValidationError(ValueError):
    """Raised when a pipeline graph is malformed (bad edge ref or a cycle)."""


class PipelineService:
    def __init__(self, repository):
        self.repository = repository

    # ── Pipeline Node Library ─────────────────────────────────────

    def list_pipeline_nodes(self, *, owner_id: str) -> list[dict[str, Any]]:
        nodes = self.repository.list_pipeline_nodes(owner_id=owner_id)
        return serialize_documents(nodes)

    def get_pipeline_node(self, node_id: str) -> dict[str, Any] | None:
        node = self.repository.get_pipeline_node(node_id)
        return serialize_document(node) if node else None

    def create_pipeline_node(self, *, owner_id: str, data: dict[str, Any]) -> dict[str, Any]:
        node = self.repository.create_pipeline_node(
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
        existing = self.repository.get_pipeline_node(node_id)
        if not existing:
            return None
        if existing.get("owner_id") == "system":
            return None  # system nodes are immutable
        if existing.get("owner_id") != owner_id:
            return None
        updated = self.repository.update_pipeline_node(node_id, data)
        return serialize_document(updated) if updated else None

    def delete_pipeline_node(self, node_id: str, *, owner_id: str) -> bool:
        existing = self.repository.get_pipeline_node(node_id)
        if not existing:
            return False
        if existing.get("owner_id") in ("system", None):
            return False
        if existing.get("owner_id") != owner_id:
            return False
        return self.repository.delete_pipeline_node(node_id)

    # ── Pipeline Definitions ──────────────────────────────────────

    def list_pipelines(self, *, owner_id: str) -> list[dict[str, Any]]:
        pipelines = self.repository.list_pipelines(owner_id=owner_id)
        return serialize_documents(pipelines)

    def get_pipeline(self, pipeline_id: str, *, owner_id: str) -> dict[str, Any] | None:
        pipeline = self.repository.get_pipeline(pipeline_id)
        if not pipeline or pipeline.get("owner_id") != owner_id:
            return None
        return serialize_document(pipeline)

    def create_pipeline(self, *, owner_id: str, data: dict[str, Any]) -> dict[str, Any]:
        nodes, edges = _build_graph(data.get("nodes", []), data.get("edges"))
        pipeline = self.repository.create_pipeline(
            owner_id=owner_id,
            name=data["name"],
            description=data.get("description", ""),
            nodes=nodes,
            edges=edges,
            extract_metadata=bool(data.get("extract_metadata", False)),
        )
        return serialize_document(pipeline)

    def update_pipeline(
        self, pipeline_id: str, *, owner_id: str, data: dict[str, Any]
    ) -> dict[str, Any] | None:
        existing = self.repository.get_pipeline(pipeline_id)
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
        if "extract_metadata" in data:
            updates["extract_metadata"] = bool(data["extract_metadata"])
        updated = self.repository.update_pipeline(pipeline_id, updates)
        return serialize_document(updated) if updated else None

    def delete_pipeline(self, pipeline_id: str, *, owner_id: str) -> bool:
        existing = self.repository.get_pipeline(pipeline_id)
        if not existing or existing.get("owner_id") != owner_id:
            return False
        return self.repository.delete_pipeline(pipeline_id)


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
    """Kahn's algorithm: if we can't consume every node, there's a cycle."""
    indegree = {n["node_id"]: 0 for n in nodes}
    adjacency: dict[str, list[str]] = {n["node_id"]: [] for n in nodes}
    for edge in edges:
        adjacency[edge["from_node_id"]].append(edge["to_node_id"])
        indegree[edge["to_node_id"]] += 1
    queue = [nid for nid, deg in indegree.items() if deg == 0]
    consumed = 0
    while queue:
        nid = queue.pop()
        consumed += 1
        for nxt in adjacency[nid]:
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                queue.append(nxt)
    if consumed != len(nodes):
        raise PipelineValidationError("Pipeline graph has a cycle.")
