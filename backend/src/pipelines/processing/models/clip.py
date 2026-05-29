import clip
import torch
from PIL import Image
import numpy as np
from .interface import ModelInterface
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

class ClipModel(ModelInterface):
    def __init__(self, model_name='ViT-B/32'):
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.model, self.preprocess = clip.load(model_name, device=self.device)
        self.logger = logging.getLogger("ClipModel")
        self.logger.info("CLIP model has been loaded successfully.")

    def embed(self, image: Image.Image) -> np.ndarray | None:
        try:
            self.logger.info("Performing CLIP embedding on image ...")
            image = self.preprocess(image).unsqueeze(0).to(self.device)
            with torch.no_grad():
                embedding = self.model.encode_image(image)
            return embedding.cpu().numpy()[0]
        except Exception as e:
            self.logger.exception(f"Exception during CLIP image embedding. Reason: {str(e)}")
            return None

    def embed_text(self, text: str):
        try:
            self.logger.info("Performing CLIP text embedding ...")
            tokens = clip.tokenize([text]).to(self.device)
            with torch.no_grad():
                return self.model.encode_text(tokens).cpu().numpy().flatten()
        except Exception as e:
            self.logger.exception(f"Exception during CLIP text embedding. Reason: {str(e)}")
            return None

    def detect(self, image): raise NotImplementedError
    def describe(self, image): raise NotImplementedError
