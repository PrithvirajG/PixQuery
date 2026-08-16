from transformers import BlipProcessor, BlipForConditionalGeneration
from PIL import Image
from .interface import ModelInterface
import numpy as np
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

class BlipModel(ModelInterface):
    def __init__(self, model_name='Salesforce/blip-image-captioning-base'):
        self.processor = BlipProcessor.from_pretrained(model_name, use_fast=True)
        self.model = BlipForConditionalGeneration.from_pretrained(model_name)
        self.logger = logging.getLogger("BlipModel")
        self.logger.info(f"BLIP model has been loaded from path {model_name}")

    def describe(self, image: Image.Image) -> str | None:
        try:
            self.logger.info("Generating description using BLIP model ...")
            inputs = self.processor(images=image, return_tensors='pt')
            outputs = self.model.generate(**inputs)
            decoded_data = self.processor.decode(outputs[0], skip_special_tokens=True)
            self.logger.info(f"Generated description: {decoded_data}")
            return decoded_data
        except Exception as e:
            self.logger.exception(f"Exception during BLIP description generation. Reason: {str(e)}")
            return None

    def detect(self, image): raise NotImplementedError
    def embed(self, image): raise NotImplementedError
