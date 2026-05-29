from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MongoPipelineRepository:
    def __init__(self, database):
        self.db = database
        self.image_assets = database["image_assets"]
        self.file_observations = database["file_observations"]
        self.processing_jobs = database["processing_jobs"]
        self.pipeline_runs = database["pipeline_runs"]
        self.model_outputs = database["model_outputs"]
        self.users = database["users"]
        self.pipeline_nodes_col = database["pipeline_nodes"]
        self.pipeline_definitions = database["pipeline_definitions"]
        self.workspace_definitions = database["workspace_definitions"]
        self.ensure_indexes()

    @classmethod
    def from_uri(cls, mongo_uri: str, database_name: str) -> "MongoPipelineRepository":
        from pymongo import MongoClient

        return cls(MongoClient(mongo_uri)[database_name])

    def ensure_indexes(self) -> None:
        self.image_assets.create_index("content_sha256", unique=True)
        self.users.create_index("username", unique=True)
        self.file_observations.create_index(
            [("workspace_id", 1), ("relative_path", 1)], unique=True
        )
        self.processing_jobs.create_index(
            [("asset_id", 1), ("pipeline_id", 1), ("pipeline_version", 1)], unique=True
        )
        self.model_outputs.create_index([("asset_id", 1), ("pipeline_run_id", 1)])
        self.pipeline_nodes_col.create_index("node_type")
        self.pipeline_nodes_col.create_index("owner_id")
        self.pipeline_definitions.create_index("owner_id")
        self.workspace_definitions.create_index("owner_id")
        self._seed_system_nodes()

    _SYSTEM_NODES = [
        {
            "name": "Object Detection (YOLOv8)",
            "description": "Detects objects using YOLOv8 and annotates with bounding boxes.",
            "node_type": "object_detection",
            "context_inputs": ["image"],
            "context_outputs": ["detections"],
            "config_schema": {"model": {"type": "string"}, "threshold": {"type": "number"}},
            "default_config": {"model": "yolov8n", "threshold": 0.5},
        },
        {
            "name": "Image Captioning (BLIP)",
            "description": "Generates a natural language caption for the image.",
            "node_type": "captioning",
            "context_inputs": ["image"],
            "context_outputs": ["caption"],
            "config_schema": {"model": {"type": "string"}},
            "default_config": {"model": "blip-base"},
        },
        {
            "name": "CLIP Embedding",
            "description": "Produces a vector embedding for semantic search.",
            "node_type": "embedding",
            "context_inputs": ["image"],
            "context_outputs": ["embeddings"],
            "config_schema": {"model": {"type": "string"}},
            "default_config": {"model": "openai/clip-vit-base-patch32"},
        },
        {
            "name": "Face Detection",
            "description": "Detects human faces and returns bounding boxes.",
            "node_type": "face_detection",
            "context_inputs": ["image"],
            "context_outputs": ["faces"],
            "config_schema": {"min_confidence": {"type": "number"}},
            "default_config": {"min_confidence": 0.8},
        },
        {
            "name": "Image Classification",
            "description": "Classifies image into top-N categories.",
            "node_type": "classification",
            "context_inputs": ["image"],
            "context_outputs": ["labels"],
            "config_schema": {"model": {"type": "string"}, "top_k": {"type": "integer"}},
            "default_config": {"model": "resnet50", "top_k": 5},
        },
        {
            "name": "Resize",
            "description": "Resizes the image to specified dimensions.",
            "node_type": "resize",
            "context_inputs": ["image"],
            "context_outputs": ["image"],
            "config_schema": {"width": {"type": "integer"}, "height": {"type": "integer"}},
            "default_config": {"width": 640, "height": 640},
        },
        {
            "name": "Grayscale",
            "description": "Converts the image to grayscale.",
            "node_type": "grayscale",
            "context_inputs": ["image"],
            "context_outputs": ["image"],
            "config_schema": {},
            "default_config": {},
        },
        {
            "name": "Draw Bounding Boxes",
            "description": "Draws detection bounding boxes onto the image.",
            "node_type": "draw_boxes",
            "context_inputs": ["image", "detections"],
            "context_outputs": ["image"],
            "config_schema": {"color": {"type": "string"}, "thickness": {"type": "integer"}},
            "default_config": {"color": "#00FF00", "thickness": 2},
        },
    ]

    def _seed_system_nodes(self) -> None:
        for node_def in self._SYSTEM_NODES:
            if not self.pipeline_nodes_col.find_one({"node_type": node_def["node_type"], "owner_id": "system"}):
                self.pipeline_nodes_col.insert_one(
                    {
                        "_id": str(uuid4()),
                        **node_def,
                        "owner_id": "system",
                        "created_at": utcnow(),
                    }
                )

    def upsert_asset(
        self,
        *,
        content_sha256: str,
        mime_type: str | None,
        size_bytes: int,
        current_path: str,
        owner_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = utcnow()
        existing = self.image_assets.find_one({"content_sha256": content_sha256})
        if existing:
            update_payload = {
                "mime_type": mime_type,
                "size_bytes": size_bytes,
                "latest_seen_at": now,
                "active": True,
                "current_path": current_path,
            }
            if owner_id and not existing.get("owner_id"):
                update_payload["owner_id"] = owner_id

            self.image_assets.update_one(
                {"_id": existing["_id"]},
                {
                    "$set": update_payload,
                    "$setOnInsert": {"metadata": metadata or {}},
                },
            )
            existing.update(update_payload)
            return existing

        asset = {
            "_id": str(uuid4()),
            "content_sha256": content_sha256,
            "mime_type": mime_type,
            "size_bytes": size_bytes,
            "first_seen_at": now,
            "latest_seen_at": now,
            "active": True,
            "current_path": current_path,
            "owner_id": owner_id,
            "metadata": metadata or {},
        }
        self.image_assets.insert_one(asset)
        return asset

    def upsert_file_observation(
        self,
        *,
        asset_id: str,
        workspace_id: str,
        relative_path: str,
        absolute_path: str,
        content_sha256: str,
    ) -> dict[str, Any]:
        now = utcnow()
        key = {"workspace_id": workspace_id, "relative_path": relative_path}
        update = {
            "$set": {
                "asset_id": asset_id,
                "absolute_path": absolute_path,
                "content_sha256": content_sha256,
                "status": "active",
                "last_seen_at": now,
                "missing_since": None,
            },
            "$setOnInsert": {"_id": str(uuid4()), "first_seen_at": now},
        }
        self.file_observations.update_one(key, update, upsert=True)
        return self.file_observations.find_one(key)

    def ensure_processing_job(
        self,
        *,
        asset_id: str,
        pipeline_id: str,
        pipeline_version: str,
    ) -> tuple[dict[str, Any], bool]:
        key = {
            "asset_id": asset_id,
            "pipeline_id": pipeline_id,
            "pipeline_version": pipeline_version,
        }
        existing = self.processing_jobs.find_one(key)
        if existing:
            return existing, False

        now = utcnow()
        job = {
            "_id": str(uuid4()),
            **key,
            "status": "queued",
            "attempt_count": 0,
            "next_attempt_at": now,
            "last_error": None,
            "created_at": now,
            "updated_at": now,
        }
        self.processing_jobs.insert_one(job)
        return job, True

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        return self.processing_jobs.find_one({"_id": job_id})

    def list_jobs(self, status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        query = {"status": status} if status else {}
        return list(self.processing_jobs.find(query).sort("updated_at", -1).limit(limit))

    def requeue_job(self, job_id: str) -> dict[str, Any] | None:
        now = utcnow()
        self.processing_jobs.update_one(
            {"_id": job_id},
            {"$set": {"status": "queued", "next_attempt_at": now, "updated_at": now}},
        )
        return self.get_job(job_id)

    def start_job(self, job_id: str) -> dict[str, Any]:
        now = utcnow()
        try:
            from pymongo import ReturnDocument

            return_document = ReturnDocument.AFTER
        except ImportError:
            return_document = True
        job = self.processing_jobs.find_one_and_update(
            {"_id": job_id},
            {
                "$set": {"status": "processing", "updated_at": now},
                "$inc": {"attempt_count": 1},
            },
            return_document=return_document,
        )
        if not job:
            raise ValueError(f"Processing job not found: {job_id}")
        run = {
            "_id": str(uuid4()),
            "job_id": job_id,
            "asset_id": job["asset_id"],
            "pipeline_id": job["pipeline_id"],
            "pipeline_version": job["pipeline_version"],
            "started_at": now,
            "finished_at": None,
            "status": "processing",
            "error": None,
        }
        self.pipeline_runs.insert_one(run)
        job["pipeline_run_id"] = run["_id"]
        return job

    def complete_job(self, job_id: str, pipeline_run_id: str) -> None:
        now = utcnow()
        self.processing_jobs.update_one(
            {"_id": job_id},
            {"$set": {"status": "completed", "updated_at": now, "last_error": None}},
        )
        self.pipeline_runs.update_one(
            {"_id": pipeline_run_id},
            {"$set": {"status": "completed", "finished_at": now, "error": None}},
        )

    def fail_job(
        self,
        job_id: str,
        pipeline_run_id: str | None,
        error: dict[str, Any],
        *,
        max_attempts: int = 3,
    ) -> str:
        now = utcnow()
        job = self.get_job(job_id)
        attempts = int(job.get("attempt_count", 0)) if job else max_attempts
        retry_delays = [60, 300, 900]
        final_status = "failed" if attempts >= max_attempts else "queued"
        next_attempt = None
        if final_status == "queued":
            next_attempt = now + timedelta(seconds=retry_delays[min(attempts - 1, 2)])
        self.processing_jobs.update_one(
            {"_id": job_id},
            {
                "$set": {
                    "status": final_status,
                    "next_attempt_at": next_attempt,
                    "last_error": error,
                    "updated_at": now,
                }
            },
        )
        if pipeline_run_id:
            self.pipeline_runs.update_one(
                {"_id": pipeline_run_id},
                {"$set": {"status": "failed", "finished_at": now, "error": error}},
            )
        return final_status

    def add_model_output(
        self,
        *,
        asset_id: str,
        pipeline_run_id: str,
        model_name: str,
        model_version: str,
        output_type: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        output = {
            "_id": str(uuid4()),
            "asset_id": asset_id,
            "pipeline_run_id": pipeline_run_id,
            "model_name": model_name,
            "model_version": model_version,
            "output_type": output_type,
            "payload": payload,
            "created_at": utcnow(),
        }
        self.model_outputs.insert_one(output)
        return output

    def get_asset(self, asset_id: str) -> dict[str, Any] | None:
        return self.image_assets.find_one({"_id": asset_id})

    def list_active_assets(self, *, user_id: str | None = None, limit: int = 100, skip: int = 0) -> list[dict[str, Any]]:
        if user_id:
            # Include assets owned by this user OR assets with no owner yet
            query: dict = {"active": True, "$or": [{"owner_id": user_id}, {"owner_id": None}]}
        else:
            query = {"active": True}
        return list(
            self.image_assets.find(query)
            .sort("latest_seen_at", -1)
            .skip(skip)
            .limit(limit)
        )

    def mark_missing_observations(self, workspace_id: str, active_relative_paths: set[str]) -> None:
        now = utcnow()
        active_paths = list(active_relative_paths)
        query = {"workspace_id": workspace_id, "status": "active"}
        if active_paths:
            query["relative_path"] = {"$nin": active_paths}
        self.file_observations.update_many(
            query,
            {"$set": {"status": "missing", "missing_since": now, "last_seen_at": now}},
        )
        self.refresh_asset_activity()

    def refresh_asset_activity(self) -> None:
        active_asset_ids = set(
            self.file_observations.distinct("asset_id", {"status": "active"})
        )
        for asset in self.image_assets.find({}):
            active = asset["_id"] in active_asset_ids
            self.image_assets.update_one({"_id": asset["_id"]}, {"$set": {"active": active}})

    def create_user(self, username: str, password_hash: str) -> dict[str, Any]:
        user = {
            "_id": str(uuid4()),
            "username": username,
            "hashed_password": password_hash,
            "created_at": utcnow(),
        }
        self.users.insert_one(user)
        return user

    def get_user_by_username(self, username: str) -> dict[str, Any] | None:
        return self.users.find_one({"username": username})

    def get_user(self, user_id: str) -> dict[str, Any] | None:
        return self.users.find_one({"_id": user_id})

    def claim_unowned_assets(self, user_id: str) -> int:
        result = self.image_assets.update_many(
            {"$or": [{"owner_id": {"$exists": False}}, {"owner_id": None}]},
            {"$set": {"owner_id": user_id}}
        )
        return result.modified_count

    # ──────────────────────────────────────────────────────────────
    # Pipeline Node Library
    # ──────────────────────────────────────────────────────────────

    def list_pipeline_nodes(self, *, owner_id: str | None = None) -> list[dict[str, Any]]:
        query: dict[str, Any] = {"$or": [{"owner_id": "system"}, {"owner_id": owner_id}]}
        if owner_id is None:
            query = {"owner_id": "system"}
        return list(self.pipeline_nodes_col.find(query).sort("name", 1))

    def get_pipeline_node(self, node_id: str) -> dict[str, Any] | None:
        return self.pipeline_nodes_col.find_one({"_id": node_id})

    def create_pipeline_node(
        self,
        *,
        name: str,
        description: str,
        node_type: str,
        context_inputs: list[str],
        context_outputs: list[str],
        config_schema: dict[str, Any],
        default_config: dict[str, Any],
        owner_id: str,
    ) -> dict[str, Any]:
        now = utcnow()
        node = {
            "_id": str(uuid4()),
            "name": name,
            "description": description,
            "node_type": node_type,
            "context_inputs": context_inputs,
            "context_outputs": context_outputs,
            "config_schema": config_schema,
            "default_config": default_config,
            "owner_id": owner_id,
            "created_at": now,
        }
        self.pipeline_nodes_col.insert_one(node)
        return node

    def update_pipeline_node(self, node_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        updates.pop("_id", None)
        updates.pop("owner_id", None)
        self.pipeline_nodes_col.update_one({"_id": node_id}, {"$set": updates})
        return self.get_pipeline_node(node_id)

    def delete_pipeline_node(self, node_id: str) -> bool:
        result = self.pipeline_nodes_col.delete_one({"_id": node_id})
        return result.deleted_count > 0

    # ──────────────────────────────────────────────────────────────
    # Pipeline Definitions
    # ──────────────────────────────────────────────────────────────

    def list_pipelines(self, *, owner_id: str) -> list[dict[str, Any]]:
        return list(self.pipeline_definitions.find({"owner_id": owner_id}).sort("created_at", -1))

    def get_pipeline(self, pipeline_id: str) -> dict[str, Any] | None:
        return self.pipeline_definitions.find_one({"_id": pipeline_id})

    def create_pipeline(
        self,
        *,
        owner_id: str,
        name: str,
        description: str = "",
        nodes: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        now = utcnow()
        pipeline = {
            "_id": str(uuid4()),
            "name": name,
            "description": description,
            "owner_id": owner_id,
            "nodes": nodes or [],
            "created_at": now,
            "updated_at": now,
        }
        self.pipeline_definitions.insert_one(pipeline)
        return pipeline

    def update_pipeline(self, pipeline_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        updates.pop("_id", None)
        updates.pop("owner_id", None)
        updates["updated_at"] = utcnow()
        self.pipeline_definitions.update_one({"_id": pipeline_id}, {"$set": updates})
        return self.get_pipeline(pipeline_id)

    def delete_pipeline(self, pipeline_id: str) -> bool:
        result = self.pipeline_definitions.delete_one({"_id": pipeline_id})
        return result.deleted_count > 0

    # ──────────────────────────────────────────────────────────────
    # Workspace Definitions
    # ──────────────────────────────────────────────────────────────

    def list_workspaces(self, *, owner_id: str) -> list[dict[str, Any]]:
        return list(self.workspace_definitions.find({"owner_id": owner_id}).sort("created_at", -1))

    def list_workspaces_all_active(self) -> list[dict[str, Any]]:
        """Return all active workspaces across all users — used by the monitor process."""
        return list(self.workspace_definitions.find({"active": True}))

    def get_workspace(self, workspace_id: str) -> dict[str, Any] | None:
        return self.workspace_definitions.find_one({"_id": workspace_id})

    def create_workspace(
        self,
        *,
        owner_id: str,
        name: str,
        workspace_path: str,
        pipeline_ids: list[str] | None = None,
        extensions: list[str] | None = None,
        active: bool = True,
    ) -> dict[str, Any]:
        now = utcnow()
        workspace = {
            "_id": str(uuid4()),
            "name": name,
            "workspace_path": workspace_path,
            "owner_id": owner_id,
            "active": active,
            "pipeline_ids": pipeline_ids or [],
            "extensions": extensions or [".jpg", ".jpeg", ".png", ".webp"],
            "created_at": now,
        }
        self.workspace_definitions.insert_one(workspace)
        return workspace

    def update_workspace(self, workspace_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        updates.pop("_id", None)
        updates.pop("owner_id", None)
        self.workspace_definitions.update_one({"_id": workspace_id}, {"$set": updates})
        return self.get_workspace(workspace_id)

    def delete_workspace(self, workspace_id: str) -> bool:
        result = self.workspace_definitions.delete_one({"_id": workspace_id})
        return result.deleted_count > 0

    # ──────────────────────────────────────────────────────────────
    # Statistics
    # ──────────────────────────────────────────────────────────────

    def get_stats_overview(self, *, owner_id: str) -> dict[str, Any]:
        total_images = self.image_assets.count_documents({"owner_id": owner_id, "active": True})
        active_workspaces = self.workspace_definitions.count_documents({"owner_id": owner_id, "active": True})
        pipelines_defined = self.pipeline_definitions.count_documents({"owner_id": owner_id})

        job_query_base: dict[str, Any] = {}
        jobs_queued = self.processing_jobs.count_documents({**job_query_base, "status": "queued"})
        jobs_processing = self.processing_jobs.count_documents({**job_query_base, "status": "processing"})
        jobs_completed = self.processing_jobs.count_documents({**job_query_base, "status": "completed"})
        jobs_failed = self.processing_jobs.count_documents({**job_query_base, "status": "failed"})

        return {
            "total_images": total_images,
            "active_workspaces": active_workspaces,
            "pipelines_defined": pipelines_defined,
            "jobs_queued": jobs_queued,
            "jobs_processing": jobs_processing,
            "jobs_completed": jobs_completed,
            "jobs_failed": jobs_failed,
        }

    def list_recent_jobs(self, *, limit: int = 50) -> list[dict[str, Any]]:
        return list(
            self.processing_jobs.find({})
            .sort("updated_at", -1)
            .limit(limit)
        )
