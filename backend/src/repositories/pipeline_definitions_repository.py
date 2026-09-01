"""Pure data access for the ``pipeline_definitions`` collection."""

from __future__ import annotations

from typing import Any

from src.models import PipelineDefinition
from src.utils.time import utcnow


class PipelineDefinitionsRepository:
    def __init__(self, database):
        self.collection = database["pipeline_definitions"]

    def ensure_indexes(self) -> None:
        self.collection.create_index("owner_id")

    def list_for_owner(self, owner_id: str) -> list[dict[str, Any]]:
        return list(self.collection.find({"owner_id": owner_id}).sort("created_at", -1))

    def get(self, pipeline_id: str) -> dict[str, Any] | None:
        return self.collection.find_one({"_id": pipeline_id})

    def count_for_owner(self, owner_id: str) -> int:
        return self.collection.count_documents({"owner_id": owner_id})

    def create(
        self,
        *,
        owner_id: str,
        name: str,
        description: str = "",
        nodes: list[dict[str, Any]] | None = None,
        edges: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        pipeline = PipelineDefinition(
            name=name,
            description=description,
            owner_id=owner_id,
            nodes=nodes or [],
            edges=edges or [],
        ).to_doc()
        self.collection.insert_one(pipeline)
        return pipeline

    def update(self, pipeline_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        updates.pop("_id", None)
        updates.pop("owner_id", None)
        updates["updated_at"] = utcnow()
        self.collection.update_one({"_id": pipeline_id}, {"$set": updates})
        return self.get(pipeline_id)

    def delete(self, pipeline_id: str) -> bool:
        return self.collection.delete_one({"_id": pipeline_id}).deleted_count > 0
