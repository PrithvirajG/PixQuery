"""Image processing pipeline."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.pipelines.processing.pipeline import (
        DefaultImageAnalysisPipeline,
        DynamicPipeline,
    )
    from src.pipelines.processing.rmq_processor import ImageProcessorConsumer
    from src.pipelines.processing.worker import start_worker

__all__ = [
    "DefaultImageAnalysisPipeline",
    "DynamicPipeline",
    "ImageProcessorConsumer",
    "start_worker",
]


def __getattr__(name):
    if name == "DefaultImageAnalysisPipeline":
        from src.pipelines.processing.pipeline import DefaultImageAnalysisPipeline

        return DefaultImageAnalysisPipeline
    if name == "DynamicPipeline":
        from src.pipelines.processing.pipeline import DynamicPipeline

        return DynamicPipeline
    if name == "ImageProcessorConsumer":
        from src.pipelines.processing.rmq_processor import ImageProcessorConsumer

        return ImageProcessorConsumer
    if name == "start_worker":
        from src.pipelines.processing.worker import start_worker

        return start_worker
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
