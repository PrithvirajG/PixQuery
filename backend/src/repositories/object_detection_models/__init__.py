"""
Object detection model repositories.

This package contains repository implementations for object detection models,
following the same pattern as sqlite/ package for database repositories.
"""

from .yolo_object_detection_model_manager import YOLOObjectDetectionModelManager

__all__ = [
    'YOLOObjectDetectionModelManager',
]