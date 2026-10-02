from PIL import Image

from .interface import ModelInterface
from src.logging_config import get_logger


class Dinov2Model(ModelInterface):
    """DINOv2 (facebook/dinov2-base) — a vision-only backbone, 768-d embeddings.

    Loaded via ``transformers`` (already a pinned dependency for BLIP), so no new
    ML framework is introduced. Unlike CLIP, DINOv2 has no text tower: it was
    trained with self-supervised image-only objectives, so there is no
    ``embed_text``. Embedding's config schema (``ModelSpec.supports_text``) is
    what stops the executor from calling it.
    """

    def __init__(self, model_name: str = "facebook/dinov2-base"):
        from transformers import AutoImageProcessor, AutoModel

        self.processor = AutoImageProcessor.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(model_name).eval()
        self.logger = get_logger(__name__)
        self.logger.info("DINOv2 model has been loaded from %s", model_name)

    def embed(self, image: Image.Image):
        import torch

        self.logger.info("Performing DINOv2 embedding on image ...")
        inputs = self.processor(images=image.convert("RGB"), return_tensors="pt")
        with torch.no_grad():
            outputs = self.model(**inputs)
        # The pooled [CLS] token is DINOv2's image-level representation — the
        # same role encode_image() plays for CLIP.
        return outputs.pooler_output[0].numpy()

    def embed_text(self, text):
        raise NotImplementedError("DINOv2 has no text tower")

    def detect(self, image):
        raise NotImplementedError

    def describe(self, image):
        raise NotImplementedError
