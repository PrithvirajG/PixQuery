from __future__ import annotations

from typing import Any
from uuid import uuid4

from src.services.document_serializer import serialize_document, serialize_documents


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
        raw_nodes = data.get("nodes", [])
        nodes = _build_node_chain(raw_nodes)
        pipeline = self.repository.create_pipeline(
            owner_id=owner_id,
            name=data["name"],
            description=data.get("description", ""),
            nodes=nodes,
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
            updates["nodes"] = _build_node_chain(data["nodes"])
        updated = self.repository.update_pipeline(pipeline_id, updates)
        return serialize_document(updated) if updated else None

    def delete_pipeline(self, pipeline_id: str, *, owner_id: str) -> bool:
        existing = self.repository.get_pipeline(pipeline_id)
        if not existing or existing.get("owner_id") != owner_id:
            return False
        return self.repository.delete_pipeline(pipeline_id)


def _build_node_chain(raw_nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Assign order + prev/next linked-list pointers to a flat node list."""
    nodes = []
    for i, raw in enumerate(raw_nodes):
        node_id = raw.get("node_id") or str(uuid4())
        nodes.append(
            {
                "node_id": node_id,
                "pipeline_node_id": raw["pipeline_node_id"],
                "order": i,
                "config_overrides": raw.get("config_overrides", {}),
                "prev_node_id": None,
                "next_node_id": None,
            }
        )
    for i, node in enumerate(nodes):
        node["prev_node_id"] = nodes[i - 1]["node_id"] if i > 0 else None
        node["next_node_id"] = nodes[i + 1]["node_id"] if i < len(nodes) - 1 else None
    return nodes
