"""Pure data access for the ``pipeline_nodes`` collection.

Includes system-node seeding: which node types exist and what config they accept
is owned by the executor code (see ``services/executors/``), not by an operator
editing Mongo, so this collection's system rows are bootstrapped from a hardcoded
list on every startup — the same kind of infrastructure bootstrapping as
``ensure_indexes``, not a business decision.
"""

from __future__ import annotations

from typing import Any

from src.models import PipelineNode


class PipelineNodesRepository:
    def __init__(self, database):
        self.collection = database["pipeline_nodes"]

    def ensure_indexes(self) -> None:
        self.collection.create_index("node_type")
        self.collection.create_index("owner_id")
        # One system node per node_type. Partial so user nodes (which may repeat a
        # node_type) are unaffected. Best-effort: creation is skipped if legacy
        # duplicates still exist (the dedupe migration clears them) or the backend
        # lacks partial-index support (in-memory tests).
        try:
            self.collection.create_index(
                [("node_type", 1)],
                unique=True,
                name="system_node_type_unique",
                partialFilterExpression={"owner_id": "system"},
            )
        except Exception:
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

    # Fields of a system node that are owned by the code, not the database. They
    # describe what the executor actually accepts and emits, so a stale copy in
    # Mongo silently lies to the pipeline editor (wrong knobs, wrong ports).
    _SYSTEM_NODE_MANAGED_FIELDS = (
        "name",
        "description",
        "context_inputs",
        "context_outputs",
        "config_schema",
        "default_config",
    )

    def seed_system_nodes(self) -> None:
        # Upsert (not check-then-insert): the API, worker, and monitor processes
        # all seed at startup, so a non-atomic insert races and creates duplicate
        # system nodes. With the partial-unique index on system node_type, this
        # upsert is idempotent under concurrency.
        #
        # The managed fields are $set on every startup, NOT $setOnInsert: they must
        # track the executor as it changes. A node seeded by an older build would
        # otherwise keep advertising config keys the executor no longer reads (and
        # hide the ones it does) forever, since its _id already exists. Identity
        # fields (_id, owner_id, created_at) stay $setOnInsert so they're stable,
        # and per-pipeline `config_overrides` are untouched — those are user data.
        for node_def in self._SYSTEM_NODES:
            doc = PipelineNode(owner_id="system", **node_def).to_doc()
            managed = {k: doc[k] for k in self._SYSTEM_NODE_MANAGED_FIELDS if k in doc}
            on_insert = {k: v for k, v in doc.items() if k not in managed}
            self.collection.update_one(
                {"node_type": node_def["node_type"], "owner_id": "system"},
                {"$set": managed, "$setOnInsert": on_insert},
                upsert=True,
            )

    def list_all(self, *, owner_id: str | None = None) -> list[dict[str, Any]]:
        query: dict[str, Any] = {"$or": [{"owner_id": "system"}, {"owner_id": owner_id}]}
        if owner_id is None:
            query = {"owner_id": "system"}
        return list(self.collection.find(query).sort("name", 1))

    def get(self, node_id: str) -> dict[str, Any] | None:
        return self.collection.find_one({"_id": node_id})

    def create(
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
        self.collection.insert_one(node)
        return node

    def update(self, node_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        updates.pop("_id", None)
        updates.pop("owner_id", None)
        self.collection.update_one({"_id": node_id}, {"$set": updates})
        return self.get(node_id)

    def delete(self, node_id: str) -> bool:
        return self.collection.delete_one({"_id": node_id}).deleted_count > 0
