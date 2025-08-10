import logging
from typing import Dict, Any, Optional
from .yolo_handler import YOLOHandler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


class ModelManager:
    """
    Central model manager for handling different model types.
    Similar to how SQLiteHandler manages database operations,
    this manages model operations at the storage/handler level.
    """
    
    def __init__(self):
        self.logger = logging.getLogger("ModelManager")
        self._handlers: Dict[str, Any] = {}
        
    def get_yolo_handler(self, model_path: str, device: str = 'cpu') -> YOLOHandler:
        """
        Get or create YOLO handler instance.
        Similar to how database manager gets connections.
        """
        handler_key = f"yolo_{model_path}_{device}"
        
        if handler_key not in self._handlers:
            handler = YOLOHandler(model_path, device)
            success = handler.initialize_model()
            if success:
                self._handlers[handler_key] = handler
                self.logger.info(f"Created YOLO handler for {model_path}")
            else:
                self.logger.error(f"Failed to create YOLO handler for {model_path}")
                return None
        
        return self._handlers[handler_key]
        
    def remove_handler(self, handler_key: str) -> bool:
        """Remove and cleanup a handler"""
        if handler_key in self._handlers:
            handler = self._handlers[handler_key]
            if hasattr(handler, 'close_model'):
                handler.close_model()
            del self._handlers[handler_key]
            self.logger.info(f"Removed handler: {handler_key}")
            return True
        return False
        
    def cleanup_all_handlers(self) -> bool:
        """Cleanup all handlers"""
        success = True
        for handler_key in list(self._handlers.keys()):
            if not self.remove_handler(handler_key):
                success = False
        return success
        
    def get_handler_info(self) -> Dict[str, Any]:
        """Get information about loaded handlers"""
        info = {
            'total_handlers': len(self._handlers),
            'handlers': {}
        }
        
        for key, handler in self._handlers.items():
            if hasattr(handler, 'get_model_info'):
                info['handlers'][key] = handler.get_model_info()
            else:
                info['handlers'][key] = {'type': type(handler).__name__}
                
        return info


# Singleton instance
model_manager = ModelManager()