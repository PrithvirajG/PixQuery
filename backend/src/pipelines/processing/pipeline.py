from __future__ import annotations

import traceback
from pathlib import Path

import numpy as np
from PIL import Image

from src.config import DEFAULT_PIPELINE_ID, DEFAULT_PIPELINE_VERSION
from src.pipelines.ingestion.reconciler import sha256_file
from src.pipelines.processing.models.blip import BlipModel
from src.pipelines.processing.models.clip import ClipModel
from src.pipelines.processing.models.yolo import YoloModel


class DefaultImageAnalysisPipeline:
    pipeline_id = DEFAULT_PIPELINE_ID
    pipeline_version = DEFAULT_PIPELINE_VERSION

    def __init__(self, embedding_store=None):
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
                    vector=image_embedding.tolist(),
                    properties=base_props,
                )
                if text_embedding is not None:
                    self.embedding_store.upsert_text_embedding(
                        vector=text_embedding.tolist(),
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


def _normalize(vector):
    if vector is None:
        return None
    norm = np.linalg.norm(vector)
    if norm == 0:
        return vector
    return vector / norm
