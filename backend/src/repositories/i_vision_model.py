from abc import abstractmethod
from typing import List, Dict, Any, Optional, Tuple
from PIL import Image
import numpy as np
from .i_model_interface import IModelInterface, ModelResponse


class BoundingBox:
    """Represents a bounding box for object detection."""
    
    def __init__(self, x: float, y: float, width: float, height: float, confidence: float = 1.0):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.confidence = confidence
        
    def to_dict(self) -> Dict[str, float]:
        """Convert bounding box to dictionary."""
        return {
            'x': self.x,
            'y': self.y,
            'width': self.width,
            'height': self.height,
            'confidence': self.confidence
        }


class DetectionResult:
    """Represents an object detection result."""
    
    def __init__(
        self, 
        class_name: str, 
        confidence: float, 
        bbox: BoundingBox,
        class_id: Optional[int] = None
    ):
        self.class_name = class_name
        self.confidence = confidence
        self.bbox = bbox
        self.class_id = class_id
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert detection result to dictionary."""
        return {
            'class_name': self.class_name,
            'confidence': self.confidence,
            'bbox': self.bbox.to_dict(),
            'class_id': self.class_id
        }


class ClassificationResult:
    """Represents an image classification result."""
    
    def __init__(self, class_name: str, confidence: float, class_id: Optional[int] = None):
        self.class_name = class_name
        self.confidence = confidence
        self.class_id = class_id
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert classification result to dictionary."""
        return {
            'class_name': self.class_name,
            'confidence': self.confidence,
            'class_id': self.class_id
        }


class IVisionModel(IModelInterface):
    """
    Interface for computer vision models (YOLO, CNN, ResNet, etc.).
    """
    
    @abstractmethod
    def classify_image(self, image: Image.Image, top_k: int = 5) -> ModelResponse:
        """
        Classify an image into categories.
        
        Args:
            image: PIL Image to classify
            top_k: Number of top predictions to return
            
        Returns:
            ModelResponse: List of ClassificationResult objects
        """
        pass
        
    @abstractmethod
    def detect_objects(
        self, 
        image: Image.Image, 
        confidence_threshold: float = 0.5,
        nms_threshold: float = 0.4
    ) -> ModelResponse:
        """
        Detect objects in an image.
        
        Args:
            image: PIL Image to analyze
            confidence_threshold: Minimum confidence score for detections
            nms_threshold: Non-maximum suppression threshold
            
        Returns:
            ModelResponse: List of DetectionResult objects
        """
        pass
        
    @abstractmethod
    def extract_features(self, image: Image.Image) -> ModelResponse:
        """
        Extract feature vector from an image.
        
        Args:
            image: PIL Image to extract features from
            
        Returns:
            ModelResponse: Feature vector as numpy array
        """
        pass
        
    def segment_image(self, image: Image.Image) -> ModelResponse:
        """
        Perform image segmentation (optional capability).
        
        Args:
            image: PIL Image to segment
            
        Returns:
            ModelResponse: Segmentation mask or error if not supported
        """
        return ModelResponse(
            result=None,
            error="Segmentation not supported by this model"
        )
        
    def get_class_names(self) -> List[str]:
        """
        Get list of class names the model can detect/classify.
        
        Returns:
            List of class names
        """
        return self.config.config.get('class_names', [])
        
    def get_input_size(self) -> Tuple[int, int]:
        """
        Get the expected input image size for the model.
        
        Returns:
            Tuple of (width, height)
        """
        return self.config.config.get('input_size', (640, 640))
        
    def preprocess_image(self, image: Image.Image) -> np.ndarray:
        """
        Preprocess image for model input.
        
        Args:
            image: PIL Image to preprocess
            
        Returns:
            Preprocessed image as numpy array
        """
        # Default preprocessing - resize to input size
        input_size = self.get_input_size()
        image = image.resize(input_size)
        return np.array(image)