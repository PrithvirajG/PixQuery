
from .yolo import YoloModel
from .clip import ClipModel
from .blip import BlipModel

class ModelRegistry:
    def __init__(self):
        print("[ModelRegistry] Loading models...")
        self.yolo = YoloModel()
        self.clip = ClipModel()
        self.blip = BlipModel()
        print("[ModelRegistry] All models loaded.")

# Create a singleton-like registry
model_registry = ModelRegistry()