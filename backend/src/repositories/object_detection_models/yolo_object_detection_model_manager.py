import logging
from typing import Any, Dict, List, Optional
from PIL import Image

from src.repositories.i_vision_model import IVisionModel, DetectionResult, BoundingBox, ClassificationResult
from src.repositories.i_model_interface import ModelResponse, ModelConfig
from src.models.model_manager import model_manager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


class YOLOObjectDetectionModelManager(IVisionModel):
    """
    YOLO implementation of the IVisionModel interface.
    Uses the ModelManager and YOLOHandler to perform object detection operations.
    
    This follows the same pattern as SQLiteDatabaseManager:
    - Implements the interface (IVisionModel)
    - Uses the low-level handler (YOLOHandler) through ModelManager
    - Provides business-logic-friendly methods
    """
    
    def __init__(self, model_config: ModelConfig):
        super().__init__(model_config)
        self.logger = logging.getLogger("YOLOObjectDetectionModelManager")
        self.yolo_handler = None
        self._initialize_handler()
        
    def _initialize_handler(self):
        """Initialize the YOLO handler - similar to _initialize_schema in SQLiteDatabaseManager"""
        try:
            model_path = self.config.config.get('model_path')
            device = self.config.config.get('device', 'cpu')
            
            if not model_path:
                self.logger.error("No model_path provided in config")
                return
                
            self.yolo_handler = model_manager.get_yolo_handler(model_path, device)
            if self.yolo_handler:
                self._is_loaded = True
                self.logger.info(f"YOLO handler initialized successfully")
            else:
                self.logger.error("Failed to initialize YOLO handler")
                
        except Exception as e:
            self.logger.exception(f"Exception occurred while initializing YOLO handler: {e}")
            
    def load_model(self) -> bool:
        """Load the model into memory"""
        if self.yolo_handler and self.yolo_handler.is_loaded:
            self._is_loaded = True
            return True
            
        self._initialize_handler()
        return self._is_loaded
        
    def unload_model(self) -> bool:
        """Unload the model from memory"""
        try:
            if self.yolo_handler:
                success = self.yolo_handler.close_model()
                if success:
                    self._is_loaded = False
                return success
            return True
        except Exception as e:
            self.logger.exception(f"Failed to unload YOLO model: {e}")
            return False
            
    def predict(self, input_data: Image.Image, **kwargs) -> ModelResponse:
        """Generic predict method - delegates to detect_objects"""
        return self.detect_objects(
            input_data,
            confidence_threshold=kwargs.get('confidence_threshold', 0.25),
            nms_threshold=kwargs.get('nms_threshold', 0.45)
        )
        
    def classify_image(self, image: Image.Image, top_k: int = 5) -> ModelResponse:
        """
        Classify an image - for YOLO, we use the most confident detection as classification
        """
        try:
            if not self.yolo_handler or not self.yolo_handler.is_loaded:
                return ModelResponse(
                    result=None,
                    error="YOLO model is not loaded"
                )
                
            # Get detections and use most confident as classification
            detections_response = self.detect_objects(image)
            if not detections_response.success:
                return detections_response
                
            detections = detections_response.result
            if not detections:
                return ModelResponse(result=[])
                
            # Sort by confidence and take top_k
            sorted_detections = sorted(detections, key=lambda x: x.confidence, reverse=True)[:top_k]
            
            # Convert to classification results
            classifications = []
            for det in sorted_detections:
                classification = ClassificationResult(
                    class_name=det.class_name,
                    confidence=det.confidence,
                    class_id=det.class_id
                )
                classifications.append(classification)
                
            return ModelResponse(result=classifications)
            
        except Exception as e:
            self.logger.exception(f"Failed to classify image: {e}")
            return ModelResponse(result=None, error=str(e))
            
    def detect_objects(
        self, 
        image: Image.Image, 
        confidence_threshold: float = 0.25,
        nms_threshold: float = 0.45
    ) -> ModelResponse:
        """
        Detect objects in an image.
        """
        try:
            if not self.yolo_handler or not self.yolo_handler.is_loaded:
                return ModelResponse(
                    result=None,
                    error="YOLO model is not loaded"
                )
                
            # Use the low-level handler to perform detection
            raw_detections = self.yolo_handler.detect_objects(
                image, 
                confidence_threshold, 
                nms_threshold
            )
            
            # Convert raw detections to DetectionResult objects
            detection_results = []
            for raw_det in raw_detections:
                bbox = BoundingBox(
                    x=raw_det['bbox']['x'],
                    y=raw_det['bbox']['y'],
                    width=raw_det['bbox']['width'],
                    height=raw_det['bbox']['height'],
                    confidence=raw_det['confidence']
                )
                
                detection = DetectionResult(
                    class_name=raw_det['class_name'],
                    confidence=raw_det['confidence'],
                    bbox=bbox,
                    class_id=raw_det['class_id']
                )
                detection_results.append(detection)
                
            self.logger.debug(f"Detected {len(detection_results)} objects")
            return ModelResponse(result=detection_results)
            
        except Exception as e:
            self.logger.exception(f"Failed to detect objects: {e}")
            return ModelResponse(result=None, error=str(e))
            
    def extract_features(self, image: Image.Image) -> ModelResponse:
        """
        Extract features from an image - not directly supported by YOLO
        """
        return ModelResponse(
            result=None,
            error="Feature extraction not supported by YOLO model"
        )
        
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the model"""
        base_info = {
            'model_name': self.config.model_name,
            'model_type': self.config.model_type.value,
            'capabilities': [cap.value for cap in self.config.capabilities],
            'is_loaded': self._is_loaded
        }
        
        if self.yolo_handler:
            handler_info = self.yolo_handler.get_model_info()
            base_info.update(handler_info)
            
        return base_info
        
    def get_class_names(self) -> List[str]:
        """Get list of class names the model can detect"""
        if self.yolo_handler and self.yolo_handler.is_loaded:
            return self.yolo_handler.get_class_names()
        return []
        
    def validate_input(self, input_data: Any) -> bool:
        """Validate that input is a PIL Image"""
        return isinstance(input_data, Image.Image)