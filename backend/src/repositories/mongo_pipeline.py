from __future__ import annotations

from datetime import timedelta
from typing import Any

from src.models import (
    DEFAULT_EXTENSIONS,
    FileObservation,
    ImageAsset,
    ModelOutput,
    PipelineDefinition,
    PipelineNode,
    PipelineRun,
    ProcessingJob,
    User,
    WorkspaceDefinition,
    WorkspaceMember,
    utcnow,
)

# Re-exported for back-compat: callers (and the in-memory repo) import utcnow from here.
__all__ = ["MongoPipelineRepository", "utcnow"]


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
        # Assets and jobs are scoped per workspace: the same image content in two
        # workspaces is processed and stored independently. Drop the older global
        # uniqueness constraints if they survive from a previous schema.
        self._drop_index_if_exists(self.image_assets, "content_sha256_1")
        self._drop_index_if_exists(
            self.processing_jobs, "asset_id_1_pipeline_id_1_pipeline_version_1"
        )
        self.image_assets.create_index(
            [("workspace_id", 1), ("content_sha256", 1)], unique=True
        )
        self.image_assets.create_index("content_sha256")
        self.users.create_index("username", unique=True)
        self.file_observations.create_index(
            [("workspace_id", 1), ("relative_path", 1)], unique=True
        )
        self.processing_jobs.create_index(
            [("workspace_id", 1), ("asset_id", 1), ("pipeline_id", 1), ("pipeline_version", 1)],
            unique=True,
        )
        self.model_outputs.create_index([("asset_id", 1), ("pipeline_run_id", 1)])
        self.pipeline_nodes_col.create_index("node_type")
        self.pipeline_nodes_col.create_index("owner_id")
        # One system node per node_type. Partial so user nodes (which may repeat a
        # node_type) are unaffected. Best-effort: creation is skipped if legacy
        # duplicates still exist (the dedupe migration clears them) or the backend
        # lacks partial-index support (in-memory tests).
        try:
            self.pipeline_nodes_col.create_index(
                [("node_type", 1)],
                unique=True,
                name="system_node_type_unique",
                partialFilterExpression={"owner_id": "system"},
            )
        except Exception:
            pass
        self.pipeline_definitions.create_index("owner_id")
        self.workspace_definitions.create_index("owner_id")
        self._seed_system_nodes()

    @staticmethod
    def _drop_index_if_exists(collection, index_name: str) -> None:
        try:
            collection.drop_index(index_name)
        except Exception:
            # Index absent (fresh DB) or backend without index support (in-memory tests).
            pass

    _SYSTEM_NODES = [
        {
            "name": "Object Detection (YOLOv8)",
            "description": "Detects objects using YOLOv8 and returns their bounding boxes.",
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
            "description": "Detects human faces (OpenCV Haar cascade) as bounding-box detections.",
            "node_type": "face_detection",
            "context_inputs": ["image"],
            "context_outputs": ["detections"],
            "config_schema": {
                "scale_factor": {"type": "number"},
                "min_neighbors": {"type": "integer"},
                "min_size": {"type": "integer"},
            },
            "default_config": {"scale_factor": 1.1, "min_neighbors": 5, "min_size": 30},
        },
        {
            "name": "Image Classification",
            "description": "Classifies the image into top-N ImageNet categories (MobileNetV3).",
            "node_type": "classification",
            "context_inputs": ["image"],
            "context_outputs": ["labels"],
            "config_schema": {"top_k": {"type": "integer"}},
            "default_config": {"top_k": 5},
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
            "name": "Write Image to Disk",
            "description": "Saves the current (transformed) image to a folder. The original file is never modified. Add multiple to save several outputs.",
            "node_type": "image_write",
            "context_inputs": ["image"],
            "context_outputs": ["written_image"],
            "config_schema": {
                "directory": {"type": "string"},
                "filename": {"type": "string"},
                "format": {"type": "string", "enum": ["jpeg", "png", "webp", "bmp", "tiff"]},
                "quality": {"type": "integer"},
            },
            "default_config": {
                "directory": "pixquery_output",
                "filename": "{stem}.{ext}",
                "format": "jpeg",
                "quality": 90,
            },
        },
        {
            "name": "OCR (Tesseract)",
            "description": "Extracts text from the image with optical character recognition.",
            "node_type": "ocr",
            "context_inputs": ["image"],
            "context_outputs": ["ocr_text"],
            "config_schema": {"lang": {"type": "string"}},
            "default_config": {"lang": "eng"},
        },
    ]

    def _seed_system_nodes(self) -> None:
        # Upsert (not check-then-insert): the API, worker, and monitor processes
        # all seed at startup, so a non-atomic insert races and creates duplicate
        # system nodes. With the partial-unique index on system node_type, this
        # upsert is idempotent under concurrency.
        for node_def in self._SYSTEM_NODES:
            doc = PipelineNode(owner_id="system", **node_def).to_doc()
            self.pipeline_nodes_col.update_one(
                {"node_type": node_def["node_type"], "owner_id": "system"},
                {"$setOnInsert": doc},
                upsert=True,
            )

    def upsert_asset(
        self,
        *,
        content_sha256: str,
        mime_type: str | None,
        size_bytes: int,
        current_path: str,
        workspace_id: str | None = None,
        owner_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = utcnow()
        # Assets are scoped per workspace, so identity is (workspace_id, content_sha256):
        # identical bytes in two workspaces become two independent assets.
        existing = self.image_assets.find_one(
            {"content_sha256": content_sha256, "workspace_id": workspace_id}
        )
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

        asset = ImageAsset(
            content_sha256=content_sha256,
            workspace_id=workspace_id,
            mime_type=mime_type,
            size_bytes=size_bytes,
            first_seen_at=now,
            latest_seen_at=now,
            current_path=current_path,
            owner_id=owner_id,
            metadata=metadata or {},
        ).to_doc()
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
        obs = FileObservation(
            asset_id=asset_id,
            workspace_id=workspace_id,
            relative_path=relative_path,
            absolute_path=absolute_path,
            content_sha256=content_sha256,
            last_seen_at=now,
        ).to_doc()
        update = {
            "$set": {
                field: obs[field]
                for field in ("asset_id", "absolute_path", "content_sha256", "status", "last_seen_at", "missing_since")
            },
            "$setOnInsert": {"_id": obs["_id"], "first_seen_at": obs["first_seen_at"]},
        }
        self.file_observations.update_one(key, update, upsert=True)
        return self.file_observations.find_one(key)

    def ensure_processing_job(
        self,
        *,
        asset_id: str,
        pipeline_id: str,
        pipeline_version: str,
        workspace_id: str | None = None,
    ) -> tuple[dict[str, Any], bool]:
        key = {
            "workspace_id": workspace_id,
            "asset_id": asset_id,
            "pipeline_id": pipeline_id,
            "pipeline_version": pipeline_version,
        }
        existing = self.processing_jobs.find_one(key)
        if existing:
            return existing, False

        now = utcnow()
        job = ProcessingJob(
            workspace_id=workspace_id,
            asset_id=asset_id,
            pipeline_id=pipeline_id,
            pipeline_version=pipeline_version,
            next_attempt_at=now,
            created_at=now,
            updated_at=now,
        ).to_doc()
        self.processing_jobs.insert_one(job)
        return job, True

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        return self.processing_jobs.find_one({"_id": job_id})

    def list_jobs(self, status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        query = {"status": status} if status else {}
        return list(self.processing_jobs.find(query).sort("updated_at", -1).limit(limit))

    def requeue_job(self, job_id: str) -> dict[str, Any] | None:
        # A deliberate requeue (manual retry or re-scan) starts fresh: reset the
        # attempt counter and clear the last error so it gets a full retry budget.
        now = utcnow()
        self.processing_jobs.update_one(
            {"_id": job_id},
            {"$set": {
                "status": "queued",
                "next_attempt_at": now,
                "updated_at": now,
                "attempt_count": 0,
                "last_error": None,
            }},
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
        # Reprocessing replaces, not accumulates: drop this job's previous runs and
        # their model outputs so a re-scan/retry doesn't pile up duplicate outputs.
        prior_runs = [r["_id"] for r in self.pipeline_runs.find({"job_id": job_id})]
        if prior_runs:
            self.model_outputs.delete_many({"pipeline_run_id": {"$in": prior_runs}})
            self.pipeline_runs.delete_many({"job_id": job_id})
        run = PipelineRun(
            job_id=job_id,
            asset_id=job["asset_id"],
            pipeline_id=job["pipeline_id"],
            pipeline_version=job["pipeline_version"],
            started_at=now,
        ).to_doc()
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
        permanent: bool = False,
    ) -> str:
        now = utcnow()
        job = self.get_job(job_id)
        attempts = int(job.get("attempt_count", 0)) if job else max_attempts
        retry_delays = [60, 300, 900]
        # A permanent (config) error can never succeed on retry — fail it outright.
        final_status = "failed" if (permanent or attempts >= max_attempts) else "queued"
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
        self.model_outputs.insert_one(output)
        return output

    def get_asset(self, asset_id: str) -> dict[str, Any] | None:
        return self.image_assets.find_one({"_id": asset_id})

    def accessible_workspace_ids(self, user_id: str) -> list[str]:
        """Workspaces this user owns or is a member of."""
        return [ws["_id"] for ws in self.list_workspaces(owner_id=user_id)]

    def accessible_asset_ids(self, user_id: str) -> set[str]:
        """Assets visible to the user: those with an active observation in a workspace
        they can access. Driven by file_observations (which carry workspace_id), so it
        works regardless of whether the asset doc has been re-tagged with workspace_id."""
        ws_ids = self.accessible_workspace_ids(user_id)
        observations = self.file_observations.find(
            {"workspace_id": {"$in": ws_ids}, "status": "active"}
        )
        return {obs["asset_id"] for obs in observations}

    def can_access_asset(self, user_id: str, asset_id: str) -> bool:
        ws_ids = set(self.accessible_workspace_ids(user_id))
        observations = self.file_observations.find({"asset_id": asset_id})
        return any(obs.get("workspace_id") in ws_ids for obs in observations)

    def list_active_assets(self, *, user_id: str | None = None, limit: int = 100, skip: int = 0) -> list[dict[str, Any]]:
        if user_id is not None:
            query: dict = {"active": True, "_id": {"$in": list(self.accessible_asset_ids(user_id))}}
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
        user = User(username=username, hashed_password=password_hash).to_doc()
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
        node = PipelineNode(
            name=name,
            description=description,
            node_type=node_type,
            context_inputs=context_inputs,
            context_outputs=context_outputs,
            config_schema=config_schema,
            default_config=default_config,
            owner_id=owner_id,
        ).to_doc()
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
        edges: list[dict[str, Any]] | None = None,
        extract_metadata: bool = False,
    ) -> dict[str, Any]:
        pipeline = PipelineDefinition(
            name=name,
            description=description,
            owner_id=owner_id,
            nodes=nodes or [],
            edges=edges or [],
            extract_metadata=extract_metadata,
        ).to_doc()
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
        # ``owner_id`` here is the acting user: return workspaces they own OR are a member of.
        query = {"$or": [{"owner_id": owner_id}, {"members.user_id": owner_id}]}
        return list(self.workspace_definitions.find(query).sort("created_at", -1))

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
        workspace = WorkspaceDefinition(
            name=name,
            workspace_path=workspace_path,
            owner_id=owner_id,
            active=active,
            pipeline_ids=pipeline_ids or [],
            extensions=extensions or list(DEFAULT_EXTENSIONS),
        ).to_doc()
        self.workspace_definitions.insert_one(workspace)
        return workspace

    def update_workspace(self, workspace_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        updates.pop("_id", None)
        updates.pop("owner_id", None)
        self.workspace_definitions.update_one({"_id": workspace_id}, {"$set": updates})
        return self.get_workspace(workspace_id)

    def delete_workspace(self, workspace_id: str) -> bool:
        # Cascade: drop this workspace's observations, then any asset (and its jobs,
        # model outputs, and runs) that is left without an observation in another
        # workspace. Orphaned Weaviate vectors are harmless — semantic search resolves
        # each hit back through MongoDB and skips assets that no longer exist.
        observations = list(self.file_observations.find({"workspace_id": workspace_id}))
        asset_ids = {obs["asset_id"] for obs in observations}
        self.file_observations.delete_many({"workspace_id": workspace_id})

        for asset_id in asset_ids:
            if self.file_observations.find_one({"asset_id": asset_id}):
                continue  # still referenced by another workspace (legacy shared asset)
            self.processing_jobs.delete_many({"asset_id": asset_id})
            self.model_outputs.delete_many({"asset_id": asset_id})
            self.pipeline_runs.delete_many({"asset_id": asset_id})
            self.image_assets.delete_one({"_id": asset_id})

        result = self.workspace_definitions.delete_one({"_id": workspace_id})
        return result.deleted_count > 0

    # ──────────────────────────────────────────────────────────────
    # Workspace Membership
    # ──────────────────────────────────────────────────────────────

    def add_workspace_member(
        self, workspace_id: str, user_id: str, role: str
    ) -> dict[str, Any] | None:
        """Add (or re-role) a member. Read-modify-write keeps this portable to the
        in-memory test repository, which only implements ``$set``."""
        workspace = self.get_workspace(workspace_id)
        if not workspace:
            return None
        members = [m for m in workspace.get("members", []) if m.get("user_id") != user_id]
        members.append(WorkspaceMember(user_id=user_id, role=role).model_dump())
        self.workspace_definitions.update_one(
            {"_id": workspace_id}, {"$set": {"members": members}}
        )
        return self.get_workspace(workspace_id)

    def set_workspace_member_role(
        self, workspace_id: str, user_id: str, role: str
    ) -> dict[str, Any] | None:
        workspace = self.get_workspace(workspace_id)
        if not workspace:
            return None
        members = workspace.get("members", [])
        if not any(m.get("user_id") == user_id for m in members):
            return None
        for m in members:
            if m.get("user_id") == user_id:
                m["role"] = role
        self.workspace_definitions.update_one(
            {"_id": workspace_id}, {"$set": {"members": members}}
        )
        return self.get_workspace(workspace_id)

    def remove_workspace_member(
        self, workspace_id: str, user_id: str
    ) -> dict[str, Any] | None:
        workspace = self.get_workspace(workspace_id)
        if not workspace:
            return None
        members = [m for m in workspace.get("members", []) if m.get("user_id") != user_id]
        self.workspace_definitions.update_one(
            {"_id": workspace_id}, {"$set": {"members": members}}
        )
        return self.get_workspace(workspace_id)

    def search_users(
        self, prefix: str, *, exclude_ids: set[str] | None = None, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Case-insensitive username prefix search for invite autocomplete."""
        import re

        exclude_ids = exclude_ids or set()
        pattern = f"^{re.escape(prefix)}"
        cursor = self.users.find({"username": {"$regex": pattern, "$options": "i"}})
        results: list[dict[str, Any]] = []
        for user in cursor:
            if user["_id"] in exclude_ids:
                continue
            results.append({"user_id": user["_id"], "username": user["username"]})
            if len(results) >= limit:
                break
        return results

    # ──────────────────────────────────────────────────────────────
    # Statistics
    # ──────────────────────────────────────────────────────────────

    def get_stats_overview(self, *, owner_id: str) -> dict[str, Any]:
        workspaces = self.list_workspaces(owner_id=owner_id)
        asset_ids = list(self.accessible_asset_ids(owner_id))

        total_images = self.image_assets.count_documents(
            {"_id": {"$in": asset_ids}, "active": True}
        )
        active_workspaces = sum(1 for ws in workspaces if ws.get("active"))
        pipelines_defined = self.pipeline_definitions.count_documents({"owner_id": owner_id})

        # Scope jobs by accessible assets (works for legacy jobs lacking workspace_id too).
        job_query_base: dict[str, Any] = {"asset_id": {"$in": asset_ids}}
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

    def list_recent_jobs(self, *, user_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        query: dict[str, Any] = {}
        if user_id is not None:
            query = {"asset_id": {"$in": list(self.accessible_asset_ids(user_id))}}
        return list(
            self.processing_jobs.find(query)
            .sort("updated_at", -1)
            .limit(limit)
        )
