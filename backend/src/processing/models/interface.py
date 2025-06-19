from abc import ABC, abstractmethod
from PIL import Image
import numpy as np

class ModelInterface(ABC):
    @abstractmethod
    def detect(self, image: Image.Image) -> list: pass

    @abstractmethod
    def embed(self, image: Image.Image) -> np.ndarray: pass

    @abstractmethod
    def describe(self, image: Image.Image) -> str: pass
