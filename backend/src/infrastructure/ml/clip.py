import clip
import torch
from PIL import Image
import numpy as np
from functools import lru_cache
from .interface import ModelInterface
from src.logging_config import get_logger


@lru_cache(maxsize=None)
def get_clip_model(model_name: str = 'ViT-B/32') -> 'ClipModel':
    """Return a process-wide shared ClipModel for ``model_name``, loaded once.

    Both image embedding (worker) and text-query embedding (search) must use the
    same CLIP variant for a given vector so their vectors share one space; this
    is the single entry point for that model. Unbounded (not maxsize=1): search
    now maintains one query encoder per text-capable embedding model (e.g.
    ViT-B/32 *and* ViT-L/14), and a single semantic search fans a query out to
    every one of them — a size-1 cache would reload the ~1.7GB ViT-L/14 weights
    on every other call, alternating with ViT-B/32, inside one request.
    """
    return ClipModel(model_name)

class ClipModel(ModelInterface):
    def __init__(self, model_name='ViT-B/32'):
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.model, self.preprocess = clip.load(model_name, device=self.device)
        self.logger = get_logger(__name__)
        self.logger.info("CLIP model has been loaded successfully.")

    # Failures propagate rather than returning None: a swallowed error became a
    # job that read "completed" with no embedding (and so was never retried).
    # Search's ClipQueryEncoder already catches and degrades to keyword search.
    def embed(self, image: Image.Image) -> np.ndarray:
        self.logger.info("Performing CLIP embedding on image ...")
        image = self.preprocess(image).unsqueeze(0).to(self.device)
        with torch.no_grad():
            embedding = self.model.encode_image(image)
        return embedding.cpu().numpy()[0]

    def embed_text(self, text: str):
        self.logger.info("Performing CLIP text embedding ...")
        tokens = clip.tokenize([text]).to(self.device)
        with torch.no_grad():
            return self.model.encode_text(tokens).cpu().numpy().flatten()

    def detect(self, image): raise NotImplementedError
    def describe(self, image): raise NotImplementedError
