from transformers import BlipProcessor, BlipForConditionalGeneration
from PIL import Image
from .gpu import residency
from .interface import ModelInterface
import numpy as np
from src.logging_config import get_logger

class BlipModel(ModelInterface):
    """BLIP image captioner. Runs on the GPU (fp16) when CUDA is available — never
    silently on the CPU — and shares the GPU with the other heavy models through
    ``residency`` (see ``describe``)."""

    def __init__(self, model_name='Salesforce/blip-image-captioning-base'):
        import torch

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.dtype = torch.float16 if self.device == "cuda" else torch.float32
        self.processor = BlipProcessor.from_pretrained(model_name, use_fast=True)
        # Loaded into host memory; ``residency.use`` moves it onto the GPU for each
        # call (and parks it when another heavy model needs the card).
        self.model = BlipForConditionalGeneration.from_pretrained(
            model_name, torch_dtype=self.dtype
        ).eval()
        self.logger = get_logger(__name__)
        self.logger.info("BLIP model loaded from %s (runs on %s)", model_name, self.device)

    def describe(self, image: Image.Image, prompt: str | None = None) -> str:
        # BLIP has no instruction-following ability — it always produces one
        # unconditioned caption. `prompt` is accepted (not required) only so
        # VisionLanguageModelExecutor can call every model through one signature;
        # ModelSpec(supports_prompt=False) is what tells the inspector not to
        # bother showing the Prompt field for this model in the first place.
        # Failures propagate (see Qwen2VLModel.describe) instead of becoming an
        # empty caption on a job that reads "completed".
        import torch

        with residency.use("blip", self.model, self.device):
            self.logger.info("Generating description using BLIP model ...")
            # .to(device, dtype) moves every tensor and casts only the floating
            # ones (pixel_values) to the model's dtype, leaving integer ids alone.
            inputs = self.processor(images=image, return_tensors='pt').to(self.device, self.dtype)
            with torch.no_grad():
                outputs = self.model.generate(**inputs)
            decoded_data = self.processor.decode(outputs[0], skip_special_tokens=True)
            self.logger.info(f"Generated description: {decoded_data}")
            return decoded_data

    def detect(self, image): raise NotImplementedError
    def embed(self, image): raise NotImplementedError
