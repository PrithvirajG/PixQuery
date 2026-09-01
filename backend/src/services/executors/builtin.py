"""Built-in node executors.

Each executor wraps an existing model wrapper or a small Pillow operation. Model
wrappers load their weights eagerly in ``__init__``, so they are imported lazily
here — constructing an executor is cheap; the model only loads on first ``run``.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from src.errors.executors import NodeExecutionError
from src.services.executors.base import BaseNodeExecutor


class ObjectDetectionExecutor(BaseNodeExecutor):
    node_type = "object_detection"
    model_name = "yolo"
    model_version = "v8n"

    def __init__(self) -> None:
        self._model = None

    def _get_model(self):
        if self._model is None:
            from src.infrastructure.ml.yolo import YoloModel

            self._model = YoloModel()
        return self._model

    def run(self, context: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        detections = self._get_model().detect(image=context["image"], write_image=False)
        return {"detections": detections or []}


class FaceDetectionExecutor(BaseNodeExecutor):
    """Detect faces with OpenCV's Haar cascade (ships with cv2 — no download).

    Emits under the ``detections`` key (label ``"face"``) using the same
    center-based ``[x_c, y_c, w, h]`` absolute-pixel bbox as object detection
    (YOLO ``xywh``), so it persists as an ``detections`` output and the existing
    image-detail overlay renders face boxes with no frontend change. Haar has no
    real confidence, so it's reported as 1.0.
    """

    node_type = "face_detection"
    model_name = "opencv_haar"
    model_version = "frontalface_default"

    def __init__(self) -> None:
        self._cascade = None

    def _get_cascade(self):
        if self._cascade is None:
            import os

            import cv2

            path = os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml")
            self._cascade = cv2.CascadeClassifier(path)
        return self._cascade

    def run(self, context: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        import cv2
        import numpy as np

        gray = cv2.cvtColor(np.array(context["image"]), cv2.COLOR_RGB2GRAY)
        rects = self._get_cascade().detectMultiScale(
            gray,
            scaleFactor=float(config.get("scale_factor", 1.1)),
            minNeighbors=int(config.get("min_neighbors", 5)),
            minSize=(int(config.get("min_size", 30)), int(config.get("min_size", 30))),
        )
        detections = [
            {
                "bbox": [float(x + w / 2), float(y + h / 2), float(w), float(h)],
                "label": "face",
                "confidence": 1.0,
            }
            for (x, y, w, h) in rects
        ]
        return {"detections": detections}


class ClassificationExecutor(BaseNodeExecutor):
    """Whole-image classification with a torchvision MobileNetV3 (ImageNet-1k).

    MobileNetV3-Small is light (~10 MB) and its weights carry the 1000 category
    names, so there's no label mapping to maintain. Weights download once on first
    use, matching how YOLO/BLIP/CLIP already fetch theirs.
    """

    node_type = "classification"
    model_name = "mobilenet_v3_small"
    model_version = "imagenet1k"

    def __init__(self) -> None:
        self._model = None
        self._preprocess = None
        self._categories = None

    def _load(self):
        if self._model is None:
            from torchvision.models import MobileNet_V3_Small_Weights, mobilenet_v3_small

            weights = MobileNet_V3_Small_Weights.DEFAULT
            self._model = mobilenet_v3_small(weights=weights).eval()
            self._preprocess = weights.transforms()
            self._categories = weights.meta["categories"]
        return self._model

    def run(self, context: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        import torch

        model = self._load()
        top_k = int(config.get("top_k", 5))
        batch = self._preprocess(context["image"]).unsqueeze(0)
        with torch.no_grad():
            probs = torch.softmax(model(batch)[0], dim=0)
        top = torch.topk(probs, min(top_k, probs.shape[0]))
        labels = [
            {"label": self._categories[int(idx)], "confidence": float(score)}
            for score, idx in zip(top.values, top.indices)
        ]
        return {"labels": labels}


class CaptioningExecutor(BaseNodeExecutor):
    node_type = "captioning"
    model_name = "blip"
    model_version = "image-captioning-base"

    def __init__(self) -> None:
        self._model = None

    def _get_model(self):
        if self._model is None:
            from src.infrastructure.ml.blip import BlipModel

            self._model = BlipModel()
        return self._model

    def run(self, context: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        return {"caption": self._get_model().describe(context["image"]) or ""}


class EmbeddingExecutor(BaseNodeExecutor):
    node_type = "embedding"
    model_name = "clip"
    model_version = "ViT-B/32"

    def __init__(self) -> None:
        self._model = None

    def _get_model(self):
        if self._model is None:
            from src.infrastructure.ml.clip import ClipModel

            self._model = ClipModel()
        return self._model

    def run(self, context: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        model = self._get_model()
        updates: dict[str, Any] = {"embeddings": model.embed(context["image"])}
        # If a caption is already in context, also embed it so semantic text
        # search has a vector to match against (mirrors the legacy pipeline).
        caption = context.get("caption")
        if caption:
            updates["text_embedding"] = model.embed_text(caption)
        return updates


# ── Pillow-only image operations (no heavy dependencies) ──────────────────────

class ResizeExecutor(BaseNodeExecutor):
    node_type = "resize"

    def run(self, context: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        width = int(config.get("width", 640))
        height = int(config.get("height", 640))
        return {"image": context["image"].resize((width, height))}


class GrayscaleExecutor(BaseNodeExecutor):
    node_type = "grayscale"

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
      - ``directory``: where to save. Absolute paths are used as-is; a relative
        path (the default) is resolved *inside the source image's folder*, so
        outputs stay within the workspace. The reconciler skips the default
        output folder so written images are never re-ingested.
      - ``filename``: template with ``{stem}``, ``{name}``, ``{ext}``, ``{asset}``
        tokens (default ``"{stem}.{ext}"``). Only the basename is used.
      - ``format``: ``jpeg`` | ``png`` | ``webp`` | ``bmp`` | ``tiff`` (default ``jpeg``).
      - ``quality``: 1–100 for lossy formats (default ``90``).
    """

    node_type = "image_write"

    def run(self, context: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        image = context.get("image")
        if image is None:
            raise NodeExecutionError("image_write requires an 'image' in the pipeline context")

        asset = context.get("asset") or {}
        source = Path(str(asset.get("current_path") or "output"))

        fmt = str(config.get("format") or "jpeg").lower()
        pil_format, ext = _IMAGE_FORMATS.get(fmt, ("JPEG", "jpg"))

        from src.config import PIPELINE_OUTPUT_DIRNAME

        directory = str(config.get("directory") or PIPELINE_OUTPUT_DIRNAME)
        dir_path = Path(directory).expanduser()
        if not dir_path.is_absolute():
            # Relative → inside the source image's directory (i.e. the workspace).
            dir_path = source.parent / dir_path
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
    model_name = "tesseract"
    model_version = "pytesseract"

    def run(self, context: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        import pytesseract

        lang = config.get("lang", "eng")
        text = pytesseract.image_to_string(context["image"], lang=lang) or ""
        return {"ocr_text": text.strip()}

