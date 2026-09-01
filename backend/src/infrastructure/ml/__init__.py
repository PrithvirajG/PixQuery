"""Model wrappers used by processing pipelines."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.infrastructure.ml.blip import BlipModel
    from src.infrastructure.ml.clip import ClipModel
    from src.infrastructure.ml.interface import ModelInterface
    from src.infrastructure.ml.yolo import YoloModel

__all__ = ["BlipModel", "ClipModel", "ModelInterface", "YoloModel"]


def __getattr__(name):
    if name == "BlipModel":
        from src.infrastructure.ml.blip import BlipModel

        return BlipModel
    if name == "ClipModel":
        from src.infrastructure.ml.clip import ClipModel

        return ClipModel
    if name == "ModelInterface":
        from src.infrastructure.ml.interface import ModelInterface

        return ModelInterface
    if name == "YoloModel":
        from src.infrastructure.ml.yolo import YoloModel

        return YoloModel
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
