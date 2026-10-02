from transformers import BlipProcessor, BlipForConditionalGeneration
from PIL import Image
from .interface import ModelInterface
import numpy as np
from src.logging_config import get_logger

class BlipModel(ModelInterface):
    def __init__(self, model_name='Salesforce/blip-image-captioning-base'):
        self.processor = BlipProcessor.from_pretrained(model_name, use_fast=True)
        self.model = BlipForConditionalGeneration.from_pretrained(model_name)
        self.logger = get_logger(__name__)
        self.logger.info(f"BLIP model has been loaded from path {model_name}")

    def describe(self, image: Image.Image, prompt: str | None = None) -> str:
        # BLIP has no instruction-following ability — it always produces one
        # unconditioned caption. `prompt` is accepted (not required) only so
        # VisionLanguageModelExecutor can call every model through one signature;
        # ModelSpec(supports_prompt=False) is what tells the inspector not to
        # bother showing the Prompt field for this model in the first place.
        # Failures propagate (see Qwen2VLModel.describe) instead of becoming an
        # empty caption on a job that reads "completed".
        self.logger.info("Generating description using BLIP model ...")
        inputs = self.processor(images=image, return_tensors='pt')
        outputs = self.model.generate(**inputs)
        decoded_data = self.processor.decode(outputs[0], skip_special_tokens=True)
        self.logger.info(f"Generated description: {decoded_data}")
        return decoded_data

    def detect(self, image): raise NotImplementedError
    def embed(self, image): raise NotImplementedError
