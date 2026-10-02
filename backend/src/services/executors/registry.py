"""Registry mapping ``node_type`` to a node executor.

Executors are instantiated lazily and cached, so each model loads at most once
per worker process. An unknown or not-yet-built node type raises a clear
:class:`PermanentNodeError` so the job fails immediately instead of retrying.
"""
from __future__ import annotations

from src.errors.executors import PermanentNodeError
from src.services.executors import builtin
from src.services.executors.base import BaseNodeExecutor

_EXECUTOR_CLASSES: dict[str, type[BaseNodeExecutor]] = {
    "object_detection": builtin.ObjectDetectionExecutor,
    "face_detection": builtin.FaceDetectionExecutor,
    "classification": builtin.ClassificationExecutor,
    "vision_language_model": builtin.VisionLanguageModelExecutor,
    "embedding": builtin.EmbeddingExecutor,
    "resize": builtin.ResizeExecutor,
    "grayscale": builtin.GrayscaleExecutor,
    "image_write": builtin.ImageWriteExecutor,
    "ocr": builtin.OcrExecutor,
}

# Seeded system node types that have no executor implementation yet. Empty now —
# kept so a future seeded-but-unbuilt node fails clearly (and permanently).
_UNIMPLEMENTED: dict[str, str] = {}

_INSTANCES: dict[str, BaseNodeExecutor] = {}


def describe_node_type(node_type: str) -> dict | None:
    """Editor-facing description of a node type (kind, executor, models), or None.

    Reads class attributes only — no executor is instantiated and no model loads,
    so the API process can call this freely.
    """
    executor_cls = _EXECUTOR_CLASSES.get(node_type)
    return executor_cls.describe() if executor_cls is not None else None


def embedding_model_specs() -> tuple:
    """The Embedding node's model catalog (id, label, version, supports_text).

    The one place other layers reach for "which embedding models exist and
    which of them can encode a text query" — ``SearchService`` uses it to build
    one query encoder per text-capable model, so it knows every Weaviate class a
    semantic search must fan out to without hardcoding the model list itself.
    """
    return _EXECUTOR_CLASSES["embedding"].models


def supported_model_ids(node_type: str) -> set[str]:
    """Model ids ``node_type`` can run; empty for unknown or model-less types."""
    executor_cls = _EXECUTOR_CLASSES.get(node_type)
    return {m.id for m in executor_cls.models} if executor_cls is not None else set()


def get_executor(node_type: str) -> BaseNodeExecutor:
    """Return the cached executor for ``node_type``.

    An unknown or not-yet-built node type raises :class:`PermanentNodeError` so the
    worker fails the job immediately rather than retrying something that can't work.
    """
    executor_cls = _EXECUTOR_CLASSES.get(node_type)
    if executor_cls is not None:
        if node_type not in _INSTANCES:
            _INSTANCES[node_type] = executor_cls()
        return _INSTANCES[node_type]
    if node_type in _UNIMPLEMENTED:
        raise PermanentNodeError(_UNIMPLEMENTED[node_type])
    raise PermanentNodeError(f"No executor registered for node type '{node_type}'")
