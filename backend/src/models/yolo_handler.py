import os
import logging
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from PIL import Image

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


class YOLOHandler:
    """
    Low-level YOLO model handler.
    Similar to SQLiteHandler - handles direct model operations.
    """
    
    def __init__(self, model_path: Optional[str] = None, device: str = 'cpu'):
        self.model_path = model_path
        self.device = device
        self.logger = logging.getLogger("YOLOHandler")
        self.model = None
        self.is_loaded = False
        
    def initialize_model(self, model_path: str = None) -> bool:
        """Initialize the YOLO model - similar to initialize_connection in SQLiteHandler"""
        try:
            self.logger.info("Initializing YOLO model...")
            
            if model_path:
                self.model_path = model_path
                
            if not self.model_path:
                self.logger.error("No model path provided")
                return False
                
            if not os.path.exists(self.model_path):
                self.logger.error(f"Model file not found: {self.model_path}")
                return False
                
            # Lazy import to avoid loading YOLO if not needed
            try:
                from ultralytics import YOLO
            except ImportError:
                self.logger.error("ultralytics not installed. Install with: pip install ultralytics")
                return False
                
            self.model = YOLO(self.model_path)
            self.model.to(self.device)
            self.is_loaded = True
            self.logger.info(f"YOLO model loaded successfully from {self.model_path}")
            return True
            
        except Exception as e:
            self.logger.exception(f"Exception occurred while initializing YOLO model: {e}")
            return False
            
    def detect_objects(
        self, 
        image: Image.Image, 
        confidence: float = 0.25, 
        iou_threshold: float = 0.45
    ) -> List[Dict[str, Any]]:
        """
        Detect objects in image - core low-level operation
        """
        try:
            if not self.is_loaded or self.model is None:
                self.logger.error("YOLO model is not loaded")
                return []
                
            # Convert PIL to numpy array
            img_array = np.array(image)
            
            # Run inference
            results = self.model(
                img_array,
                conf=confidence,
                iou=iou_threshold,
                verbose=False
            )
            
            detections = []
            for result in results:
                boxes = result.boxes
                if boxes is not None:
                    for box in boxes:
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                        conf = box.conf[0].cpu().numpy()
                        cls_id = int(box.cls[0].cpu().numpy())
                        
                        detection = {
                            'bbox': {
                                'x': float(x1),
                                'y': float(y1),
                                'width': float(x2 - x1),
                                'height': float(y2 - y1)
                            },
                            'confidence': float(conf),
                            'class_id': cls_id,
                            'class_name': self.model.names[cls_id] if self.model.names else f"class_{cls_id}"
                        }
                        detections.append(detection)
                        
            return detections
            
        except Exception as e:
            self.logger.exception(f"Exception occurred during object detection: {e}")
            return []
            
    def get_class_names(self) -> List[str]:
        """Get list of class names the model can detect"""
        if not self.is_loaded or self.model is None:
            return []
        return list(self.model.names.values()) if self.model.names else []
        
    def get_model_info(self) -> Dict[str, Any]:
        """Get model information"""
        info = {
            'model_path': self.model_path,
            'device': self.device,
            'is_loaded': self.is_loaded,
            'model_type': 'YOLO'
        }
        
        if self.is_loaded and self.model:
            info.update({
                'num_classes': len(self.model.names) if self.model.names else 0,
                'class_names': self.get_class_names(),
                'input_size': getattr(self.model, 'imgsz', 640)
            })
            
        return info
        
    def preprocess_image(self, image: Image.Image, target_size: int = 640) -> np.ndarray:
        """Preprocess image for YOLO input"""
        # Resize maintaining aspect ratio
        image = image.resize((target_size, target_size))
        return np.array(image)
        
    def close_model(self) -> bool:
        """Unload model from memory - similar to close_connection"""
        try:
            if self.model is not None:
                del self.model
                self.model = None
            self.is_loaded = False
            self.logger.info("YOLO model unloaded successfully")
            return True
        except Exception as e:
            self.logger.exception(f"Exception occurred while closing YOLO model: {e}")
            return False


# Singleton per worker - similar to sqlite_manager
yolo_handler = YOLOHandler()