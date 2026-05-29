"""Model wrappers used by processing pipelines."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.pipelines.processing.models.blip import BlipModel
    from src.pipelines.processing.models.clip import ClipModel
    from src.pipelines.processing.models.interface import ModelInterface
    from src.pipelines.processing.models.yolo import YoloModel

__all__ = ["BlipModel", "ClipModel", "ModelInterface", "YoloModel"]


def __getattr__(name):
    if name == "BlipModel":
        from src.pipelines.processing.models.blip import BlipModel

        return BlipModel
    if name == "ClipModel":
        from src.pipelines.processing.models.clip import ClipModel

        return ClipModel
    if name == "ModelInterface":
        from src.pipelines.processing.models.interface import ModelInterface

        return ModelInterface
    if name == "YoloModel":
        from src.pipelines.processing.models.yolo import YoloModel

        return YoloModel
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
