"""Built-in node executors.

Each executor wraps an existing model wrapper or a small Pillow operation. Model
wrappers load their weights eagerly in ``__init__``, so they are imported lazily
here — constructing an executor is cheap; the model only loads on first ``run``.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from src.errors.executors import NodeExecutionError
from src.services.executors.base import BaseNodeExecutor, ModelSpec


class ObjectDetectionExecutor(BaseNodeExecutor):
    """YOLOv8 object detection (ultralytics). Weights download on first use.

    Config: ``confidence`` — minimum detection score (default 0.25, YOLO's own
    default). ``threshold`` is accepted as a legacy alias.
    """

    node_type = "object_detection"
    kind = "model"
    outputs_label = "bounding boxes + labels"
    models = (
        ModelSpec("yolov8n", "YOLOv8n", "ultralytics-v8"),
        ModelSpec("yolov8s", "YOLOv8s", "ultralytics-v8"),
        ModelSpec("yolov8m", "YOLOv8m", "ultralytics-v8"),
    )
    default_model = "yolov8n"

    def __init__(self) -> None:
        self._models: dict[str, Any] = {}

    def _get_model(self, model_id: str):
        if model_id not in self._models:
            import os

            from src.config import MODEL_CACHE_DIR
            from src.infrastructure.ml.yolo import YoloModel

            # A full path makes ultralytics download missing weights there rather
            # than into the process's working directory.
            os.makedirs(MODEL_CACHE_DIR, exist_ok=True)
            weights = os.path.join(MODEL_CACHE_DIR, f"{model_id}.pt")
            self._models[model_id] = YoloModel(model_path=weights)
        return self._models[model_id]

    def run(self, context: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        model = self._get_model(self.resolve_model(config).id)
        conf = float(config.get("confidence", config.get("threshold", 0.25)))
        detections = model.detect(image=context["image"], write_image=False, conf=conf)
        return {"detections": detections or []}


class FaceDetectionExecutor(BaseNodeExecutor):
    """Detect faces with a choice of detector (YuNet, SCRFD, RetinaFace-R50).

    Emits under the ``detections`` key (label ``"face"``) using the same
    center-based ``[x_c, y_c, w, h]`` absolute-pixel bbox as object detection
    (YOLO ``xywh``), so it persists as a ``detections`` output and the existing
    image-detail overlay renders face boxes with no frontend change.

    Config: ``confidence_threshold`` — minimum face score (default 0.5).
    """

    node_type = "face_detection"
    kind = "model"
    outputs_label = "bounding boxes"
    models = (
        ModelSpec("yunet", "YuNet", "2023mar"),
        ModelSpec("scrfd", "SCRFD", "10g-buffalo_l"),
        ModelSpec("retinaface_r50", "RetinaFace-R50", "batch-face"),
    )
    default_model = "retinaface_r50"

    def __init__(self) -> None:
        self._detectors: dict[str, Any] = {}

    def _get_detector(self, model_id: str):
        if model_id not in self._detectors:
            from src.infrastructure.ml import face_detectors

            cls = {
                "yunet": face_detectors.YuNetFaceDetector,
                "scrfd": face_detectors.ScrfdFaceDetector,
                "retinaface_r50": face_detectors.RetinaFaceDetector,
            }[model_id]
            self._detectors[model_id] = cls()
        return self._detectors[model_id]

    def run(self, context: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        detector = self._get_detector(self.resolve_model(config).id)
        threshold = float(config.get("confidence_threshold", 0.5))
        detections = [
            {
                "bbox": [
                    (box.x1 + box.x2) / 2,
                    (box.y1 + box.y2) / 2,
                    box.x2 - box.x1,
                    box.y2 - box.y1,
                ],
                "label": "face",
                "confidence": box.score,
            }
            for box in detector.detect(context["image"], threshold)
        ]
        return {"detections": detections}


# model id → (torchvision builder, weights enum) — both ImageNet-1k, so every
# choice carries its own 1000 category names and there's no label map to keep.
_CLASSIFIERS = {
    "resnet50": ("resnet50", "ResNet50_Weights"),
    "efficientnet_b0": ("efficientnet_b0", "EfficientNet_B0_Weights"),
    "vit_b_16": ("vit_b_16", "ViT_B_16_Weights"),
}


class ClassificationExecutor(BaseNodeExecutor):
    """Whole-image ImageNet-1k classification with a torchvision model.

    Weights download once on first use, matching how YOLO/BLIP/CLIP fetch theirs.

    Config: ``top_k`` — how many labels to return (default 5).
    """

    node_type = "classification"
    kind = "model"
    outputs_label = "labels + confidence scores"
    models = (
        ModelSpec("resnet50", "ResNet-50", "imagenet1k"),
        ModelSpec("efficientnet_b0", "EfficientNet-B0", "imagenet1k"),
        ModelSpec("vit_b_16", "ViT-B/16", "imagenet1k"),
    )
    default_model = "efficientnet_b0"

    def __init__(self) -> None:
        # model id → (model, preprocess transform, category names)
        self._loaded: dict[str, tuple[Any, Any, list[str]]] = {}

    def _load(self, model_id: str):
        if model_id not in self._loaded:
            import torchvision.models as tvm

            builder_name, weights_name = _CLASSIFIERS[model_id]
            weights = getattr(tvm, weights_name).DEFAULT
            model = getattr(tvm, builder_name)(weights=weights).eval()
            self._loaded[model_id] = (model, weights.transforms(), weights.meta["categories"])
        return self._loaded[model_id]

    def run(self, context: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        import torch

        model, preprocess, categories = self._load(self.resolve_model(config).id)
        top_k = int(config.get("top_k", 5))
        batch = preprocess(context["image"].convert("RGB")).unsqueeze(0)
        with torch.no_grad():
            probs = torch.softmax(model(batch)[0], dim=0)
        top = torch.topk(probs, min(top_k, probs.shape[0]))
        labels = [
            {"label": categories[int(idx)], "confidence": float(score)}
            for score, idx in zip(top.values, top.indices)
        ]
        return {"labels": labels}


# OCR runs a single model today (more are planned), so it lists just that one.
# Its id matches its historical provenance name so existing model_outputs rows
# stay consistent.

class VisionLanguageModelExecutor(BaseNodeExecutor):
    """Produces a text caption from the image — via a fixed-task captioner
    (BLIP) or a real instruction-following vision-language model that answers
    the node's configured ``prompt`` (Qwen2-VL-2B-Instruct, Moondream2).

    Was "Captioning" / node_type "captioning" (renamed by migration
    0003_rename_captioning_to_vision_language_model, same _id — see its
    docstring for why existing pipelines keep working transparently). The
    output context key stays ``caption`` regardless of model or prompt — search
    indexes it under that key (``SearchService._captions_map``) and Embedding
    auto-embeds it as text (``EmbeddingExecutor`` reading ``context["caption"]``)
    — so whatever a custom prompt actually asks ("what brand is visible",
    "transcribe the sign"), the answer becomes searchable the same way a caption
    would.

    ``ModelSpec.supports_prompt`` is what distinguishes the two kinds: False for
    BLIP (no instruction-following — the prompt field does nothing and the
    inspector shouldn't show it), True for a real VLM (the prompt drives what
    question gets asked). The node's ``prompt`` config is passed to every
    model's ``describe()`` either way, via one call path; a model that ignores
    it (BLIP) and one that uses it are not special-cased here.
    """

    node_type = "vision_language_model"
    kind = "model"
    outputs_label = "text caption"
    # Qwen2-VL-2B-Instruct and Moondream2 both follow a custom prompt correctly
    # (verified) but both measured ~5GB peak VRAM in fp16 — over a 4GB card's
    # limit, so a small GPU pages into slow shared memory (~115s/prompt rather
    # than a few seconds). Shipped as-is (correct, just GPU-hungry) rather than
    # block the feature on this; a lighter/quantized option is future work, not
    # done — see "Vision Language Model — GPU Memory Fit (Parked)" in the
    # Obsidian vault before re-evaluating which models belong here.
    models = (
        ModelSpec("blip", "BLIP", "image-captioning-base"),
        ModelSpec(
            "qwen2_vl_2b", "Qwen2-VL-2B-Instruct", "Qwen/Qwen2-VL-2B-Instruct",
            supports_prompt=True,
        ),
        ModelSpec(
            "moondream2", "Moondream2", "vikhyatk/moondream2",
            supports_prompt=True,
        ),
    )
    default_model = "blip"

    def __init__(self) -> None:
        self._models: dict[str, Any] = {}

    def _get_model(self, model_id: str):
        if model_id not in self._models:
            if model_id == "blip":
                from src.infrastructure.ml.blip import BlipModel

                self._models[model_id] = BlipModel()
            elif model_id == "qwen2_vl_2b":
                from src.infrastructure.ml.qwen_vl import Qwen2VLModel

                self._models[model_id] = Qwen2VLModel()
            elif model_id == "moondream2":
                from src.infrastructure.ml.moondream import MoondreamModel

                self._models[model_id] = MoondreamModel()
            else:
                raise PermanentNodeError(f"No loader for vision-language model '{model_id}'")
        return self._models[model_id]

    def run(self, context: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        spec = self.resolve_model(config)
        model = self._get_model(spec.id)
        prompt = config.get("prompt") if spec.supports_prompt else None
        return {"caption": model.describe(context["image"], prompt=prompt) or ""}


# model id -> the CLIP variant name clip.load() expects. Both CLIP models share
# one wrapper class; only the loaded weights differ.
_CLIP_VARIANTS = {"clip": "ViT-B/32", "clip_vit_l14": "ViT-L/14"}


class EmbeddingExecutor(BaseNodeExecutor):
    """Produces an image (and, when a caption is present, a text) embedding.

    Model choice matters more here than for the other AI nodes: each model's
    vectors live in their own Weaviate class (see
    ``infrastructure/vector_store/weaviate.py``'s ``image_class_name``/
    ``text_class_name``), because Weaviate's HNSW index requires every vector in
    a class to share one length, and CLIP ViT-B/32 (512-d), CLIP ViT-L/14 (768-d)
    and DINOv2 (768-d, a different space despite the matching length) are not
    interchangeable. ``run`` reports which model produced the vectors
    (``embedding_model``) so the caller can route storage/search to the right
    space; DINOv2 has no text tower (``supports_text=False``), so no
    ``text_embedding`` is ever produced for it, regardless of whether a caption
    is present — that asset simply isn't reachable by a text query, only by
    keyword/OCR, same as an asset with no caption at all.
    """

    node_type = "embedding"
    kind = "model"
    outputs_label = "vector embedding"
    models = (
        ModelSpec("clip", "CLIP ViT-B/32", "ViT-B/32"),
        ModelSpec("clip_vit_l14", "CLIP ViT-L/14", "ViT-L/14"),
        ModelSpec("dinov2", "DINOv2", "facebook/dinov2-base", supports_text=False),
    )
    default_model = "clip"

    def __init__(self) -> None:
        self._models: dict[str, Any] = {}

    def _get_model(self, model_id: str):
        if model_id not in self._models:
            if model_id in _CLIP_VARIANTS:
                from src.infrastructure.ml.clip import ClipModel

                self._models[model_id] = ClipModel(model_name=_CLIP_VARIANTS[model_id])
            elif model_id == "dinov2":
                from src.infrastructure.ml.dinov2 import Dinov2Model

                self._models[model_id] = Dinov2Model()
            else:
                raise PermanentNodeError(f"No loader for embedding model '{model_id}'")
        return self._models[model_id]

    def run(self, context: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        spec = self.resolve_model(config)
        model = self._get_model(spec.id)
        updates: dict[str, Any] = {
            "embeddings": model.embed(context["image"]),
            # Working state, not a model_output row (_PERSIST_SKIP_KEYS) — read by
            # PipelineExecutionService._store_embeddings to pick the matching
            # Weaviate class for this run's vectors.
            "embedding_model": spec.id,
        }
        # If a caption is already in context, also embed it so semantic text
        # search has a vector to match against (mirrors the legacy pipeline) —
        # but only for a model that actually has a text tower.
        caption = context.get("caption")
        if caption and spec.supports_text:
            updates["text_embedding"] = model.embed_text(caption)
        return updates


# ── Pillow-only image operations (no heavy dependencies) ──────────────────────

class ResizeExecutor(BaseNodeExecutor):
    node_type = "resize"
    outputs_label = "image"

    def run(self, context: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        width = int(config.get("width", 640))
        height = int(config.get("height", 640))
        return {"image": context["image"].resize((width, height))}


class GrayscaleExecutor(BaseNodeExecutor):
    node_type = "grayscale"
    outputs_label = "image"

    def run(self, context: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        # Convert to grayscale but keep 3 channels so downstream models still work.
        return {"image": context["image"].convert("L").convert("RGB")}


# PIL uses "JPEG" (not "JPG"); map friendly format names to (PIL format, extension).
_IMAGE_FORMATS = {
    "jpeg": ("JPEG", "jpg"),
    "jpg": ("JPEG", "jpg"),
    "png": ("PNG", "png"),
    "webp": ("WEBP", "webp"),
    "bmp": ("BMP", "bmp"),
    "tiff": ("TIFF", "tiff"),
}


class ImageWriteExecutor(BaseNodeExecutor):
    """Persist the current pipeline image to disk.

    This is a *sink*: it never mutates ``context["image"]``, so the source file on
    disk is never touched. It writes whatever image the preceding nodes produced
    (e.g. a resized / boxed copy). Multiple ``image_write`` nodes are allowed — put
    one after each transform whose result you want to keep.

    Config:
      - ``directory``: where to save, *within* the managed output folder. Absolute
        paths are used as-is (an explicit escape hatch — the caller owns keeping
        those out of any watched workspace). A relative path (the default: none,
        i.e. the output folder itself) is resolved as a subfolder *under*
        ``<workspace_root>/pixquery_output/`` — never under the source image's own
        folder, so a nested source (already inside a subfolder, or itself a
        previous node's output) doesn't shift where outputs land. This is what
        keeps the managed folder a single flat root the reconciler can reliably
        skip, instead of re-nesting one level deeper on every run.
      - ``filename``: template with ``{stem}``, ``{name}``, ``{ext}``, ``{asset}``
        tokens (default ``"{stem}.{ext}"``). Only the basename is used.
      - ``format``: ``jpeg`` | ``png`` | ``webp`` | ``bmp`` | ``tiff`` (default ``jpeg``).
      - ``quality``: 1–100 for lossy formats (default ``90``).
    """

    node_type = "image_write"
    outputs_label = "file path"

    def run(self, context: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        image = context.get("image")
        if image is None:
            raise NodeExecutionError("image_write requires an 'image' in the pipeline context")

        asset = context.get("asset") or {}
        source = Path(str(asset.get("current_path") or "output"))

        fmt = str(config.get("format") or "jpeg").lower()
        pil_format, ext = _IMAGE_FORMATS.get(fmt, ("JPEG", "jpg"))

        from src.config import PIPELINE_OUTPUT_DIRNAME

        subdir = config.get("directory")
        sub_path = Path(str(subdir)).expanduser() if subdir else None
        if sub_path is not None and sub_path.is_absolute():
            dir_path = sub_path
        else:
            workspace_root = context.get("workspace_root")
            if not workspace_root:
                raise NodeExecutionError(
                    "image_write has no workspace root to anchor its output directory in "
                    "(and no absolute 'directory' override was given)"
                )
            dir_path = Path(str(workspace_root)) / PIPELINE_OUTPUT_DIRNAME
            if sub_path is not None:
                dir_path = dir_path / sub_path
        dir_path = dir_path.resolve()

        template = str(config.get("filename") or "{stem}.{ext}")
        filename = template.format(
            stem=source.stem or "image",
            name=source.name or "image",
            ext=ext,
            asset=str(asset.get("_id") or "asset"),
        )
        # Guard against a template injecting path separators / traversal.
        out_path = dir_path / Path(filename).name

        save_image = image
        if pil_format == "JPEG" and image.mode not in ("RGB", "L"):
            save_image = image.convert("RGB")  # JPEG can't hold an alpha channel.

        save_kwargs: dict[str, Any] = {}
        if fmt in ("jpeg", "jpg", "webp"):
            save_kwargs["quality"] = int(config.get("quality", 90))

        try:
            dir_path.mkdir(parents=True, exist_ok=True)
            save_image.save(out_path, format=pil_format, **save_kwargs)
        except OSError as exc:
            raise NodeExecutionError(f"Could not write image to {out_path}: {exc}") from exc

        width, height = image.size
        # Recorded in model_outputs so the UI/user can find the written file. The
        # image itself stays in context unchanged for any later node.
        return {
            "written_image": {
                "path": str(out_path),
                "format": fmt,
                "width": width,
                "height": height,
            }
        }


class OcrExecutor(BaseNodeExecutor):
    node_type = "ocr"
    kind = "model"
    outputs_label = "text"
    models = (ModelSpec("tesseract", "Tesseract", "pytesseract"),)
    default_model = "tesseract"

    def run(self, context: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        import pytesseract

        lang = config.get("lang", "eng")
        text = pytesseract.image_to_string(context["image"], lang=lang) or ""
        return {"ocr_text": text.strip()}

