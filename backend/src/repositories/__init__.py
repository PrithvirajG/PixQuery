"""
Repository layer for PixQuery backend.

This module provides abstractions for data access and model interactions,
following the repository pattern to decouple business logic from implementation details.
"""

from .i_database_manager import IDatabaseManager
from .i_image_queue_manager import IImageQueueManager
from .i_model_interface import (
    IModelInterface,
    ModelType,
    ModelCapability,
    ModelConfig,
    ModelResponse
)
from .i_chat_model import IChatModel, ChatMessage, ChatConversation
from .i_vision_model import (
    IVisionModel,
    BoundingBox,
    DetectionResult,
    ClassificationResult
)
from .i_multimodal_model import IMultimodalModel, MultimodalInput
from .i_classical_model import IClassicalModel

# Concrete implementations
from .sqlite.sqlite_database_manager import SQLiteDatabaseManager
from .object_detection_models.yolo_object_detection_model_manager import YOLOObjectDetectionModelManager

__all__ = [
    # Database interfaces
    'IDatabaseManager',
    'IImageQueueManager',

    # Model interfaces
    'IModelInterface',
    'IChatModel',
    'IVisionModel',
    'IMultimodalModel',
    'IClassicalModel',

    # Model types and data classes
    'ModelType',
    'ModelCapability',
    'ModelConfig',
    'ModelResponse',
    'ChatMessage',
    'ChatConversation',
    'BoundingBox',
    'DetectionResult',
    'ClassificationResult',
    'MultimodalInput',

    # Concrete implementations
    'SQLiteDatabaseManager',
    'YOLOObjectDetectionModelManager',
]