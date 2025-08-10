from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union
from enum import Enum
import numpy as np


class ModelType(Enum):
    """Enumeration of different model types."""
    CHAT = "chat"
    VISION = "vision" 
    MULTIMODAL = "multimodal"
    CLASSICAL_ML = "classical_ml"
    EMBEDDING = "embedding"


class ModelCapability(Enum):
    """Enumeration of model capabilities."""
    TEXT_GENERATION = "text_generation"
    IMAGE_CLASSIFICATION = "image_classification"
    OBJECT_DETECTION = "object_detection"
    IMAGE_SEGMENTATION = "image_segmentation"
    EMBEDDING_GENERATION = "embedding_generation"
    IMAGE_CAPTIONING = "image_captioning"
    FEATURE_EXTRACTION = "feature_extraction"
    PREDICTION = "prediction"
    CLUSTERING = "clustering"
    REGRESSION = "regression"


class ModelConfig:
    """Configuration class for model initialization."""
    
    def __init__(
        self,
        model_type: ModelType,
        model_name: str,
        capabilities: List[ModelCapability],
        config: Optional[Dict[str, Any]] = None
    ):
        self.model_type = model_type
        self.model_name = model_name
        self.capabilities = capabilities
        self.config = config or {}
        
    def has_capability(self, capability: ModelCapability) -> bool:
        """Check if model has a specific capability."""
        return capability in self.capabilities


class ModelResponse:
    """Standardized response from model inference."""
    
    def __init__(
        self,
        result: Any,
        confidence: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ):
        self.result = result
        self.confidence = confidence
        self.metadata = metadata or {}
        self.error = error
        self.success = error is None


class IModelInterface(ABC):
    """
    Base interface for all model types in the system.
    Provides a unified abstraction layer for different AI/ML models.
    """
    
    def __init__(self, config: ModelConfig):
        self.config = config
        self._is_loaded = False
        
    @abstractmethod
    def load_model(self) -> bool:
        """
        Load the model into memory.
        
        Returns:
            bool: True if model loaded successfully, False otherwise
        """
        pass
        
    @abstractmethod
    def unload_model(self) -> bool:
        """
        Unload the model from memory.
        
        Returns:
            bool: True if model unloaded successfully, False otherwise
        """
        pass
        
    @abstractmethod
    def predict(self, input_data: Any, **kwargs) -> ModelResponse:
        """
        Run inference on input data.
        
        Args:
            input_data: Input data for the model (format depends on model type)
            **kwargs: Additional parameters for inference
            
        Returns:
            ModelResponse: Standardized response with results and metadata
        """
        pass
        
    @abstractmethod
    def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about the model.
        
        Returns:
            Dict containing model metadata, version, capabilities, etc.
        """
        pass
        
    def is_loaded(self) -> bool:
        """Check if model is currently loaded in memory."""
        return self._is_loaded
        
    def get_capabilities(self) -> List[ModelCapability]:
        """Get list of model capabilities."""
        return self.config.capabilities
        
    def supports_capability(self, capability: ModelCapability) -> bool:
        """Check if model supports a specific capability."""
        return self.config.has_capability(capability)
        
    def get_model_type(self) -> ModelType:
        """Get the model type."""
        return self.config.model_type
        
    def validate_input(self, input_data: Any) -> bool:
        """
        Validate input data format for this model.
        
        Args:
            input_data: Input data to validate
            
        Returns:
            bool: True if input is valid, False otherwise
        """
        return True  # Default implementation, should be overridden