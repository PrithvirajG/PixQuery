"""Image processing pipeline."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.consumer.processing.image_task_consumer import ImageProcessorConsumer
    from src.consumer.processing.worker import start_pipeline_worker

__all__ = [
    "ImageProcessorConsumer",
    "start_pipeline_worker",
]


def __getattr__(name):
    if name == "ImageProcessorConsumer":
        from src.consumer.processing.image_task_consumer import ImageProcessorConsumer

        return ImageProcessorConsumer
    if name == "start_pipeline_worker":
        from src.consumer.processing.worker import start_pipeline_worker

        return start_pipeline_worker
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
