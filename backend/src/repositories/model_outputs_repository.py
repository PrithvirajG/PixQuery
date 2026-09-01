"""Pure data access for the ``model_outputs`` collection."""

from __future__ import annotations

from typing import Any

from src.models import ModelOutput


class ModelOutputsRepository:
    def __init__(self, database):
        self.collection = database["model_outputs"]

    def ensure_indexes(self) -> None:
        self.collection.create_index([("asset_id", 1), ("pipeline_run_id", 1)])

    def add(
        self,
        *,
        asset_id: str,
        pipeline_run_id: str,
        model_name: str,
        model_version: str,
        output_type: str,
        payload: dict[str, Any],
        node_id: str | None = None,
        node_type: str | None = None,
        order: int | None = None,
        workspace_id: str | None = None,
        pipeline_id: str | None = None,
        pipeline_version: str | None = None,
    ) -> dict[str, Any]:
        output = ModelOutput(
            asset_id=asset_id,
            workspace_id=workspace_id,
            pipeline_run_id=pipeline_run_id,
            pipeline_id=pipeline_id,
            pipeline_version=pipeline_version,
            model_name=model_name,
            model_version=model_version,
            output_type=output_type,
            payload=payload,
            node_id=node_id,
            node_type=node_type,
            order=order,
        ).to_doc()
        self.collection.insert_one(output)
        return output

    def list_for_asset(self, asset_id: str) -> list[dict[str, Any]]:
        return list(self.collection.find({"asset_id": asset_id}))

    def list_by_type(self, output_type: str) -> list[dict[str, Any]]:
        """Every output of one type, across all assets — backs the search text maps."""
        return list(self.collection.find({"output_type": output_type}))

    def delete_for_workspace_pipeline(self, workspace_id: str, pipeline_id: str) -> int:
        return self.collection.delete_many(
            {"workspace_id": workspace_id, "pipeline_id": pipeline_id}
        ).deleted_count

    def delete_for_asset_pipeline(self, asset_id: str, pipeline_id: str) -> int:
        return self.collection.delete_many(
            {"asset_id": asset_id, "pipeline_id": pipeline_id}
        ).deleted_count

    def delete_for_runs(self, run_ids: list[str]) -> int:
        if not run_ids:
            return 0
        return self.collection.delete_many({"pipeline_run_id": {"$in": run_ids}}).deleted_count

    def delete_for_pipeline(self, pipeline_id: str) -> int:
        return self.collection.delete_many({"pipeline_id": pipeline_id}).deleted_count

    def delete_for_asset(self, asset_id: str) -> int:
        return self.collection.delete_many({"asset_id": asset_id}).deleted_count
