from PIL import Image

from .gpu import residency
from .interface import ModelInterface
from src.logging_config import get_logger


class Qwen2VLModel(ModelInterface):
    """Qwen2-VL-2B-Instruct — a real instruction-following vision-language model.

    Unlike BLIP, this follows an arbitrary text prompt about the image ("what
    brand is visible", "is there a person", not just "caption this") — verified
    directly against this repo's sample photo. Runs on GPU when available (fp16);
    confirmed on a 4GB card it's tight (~5GB peak, spills into slow shared-memory
    paging — several minutes per prompt instead of a few seconds), so this is the
    heavier of the two prompt-capable models on offer. CPU fp32 works but is slow;
    never silently prefer it when CUDA exists — see ``self.device``.
    """

    def __init__(self, model_name: str = "Qwen/Qwen2-VL-2B-Instruct"):
        import torch
        from transformers import AutoProcessor, Qwen2VLForConditionalGeneration

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.processor = AutoProcessor.from_pretrained(model_name)
        # Loaded into host memory; ``residency.use`` moves it onto the GPU for
        # each generation (and parks it again when another heavy model needs the
        # card), so it is never silently left on the CPU — see describe().
        self.model = Qwen2VLForConditionalGeneration.from_pretrained(
            model_name, torch_dtype=torch.float16 if self.device == "cuda" else torch.float32
        ).eval()
        self.logger = get_logger(__name__)
        self.logger.info("Qwen2-VL model loaded from %s (runs on %s)", model_name, self.device)

    def describe(self, image: Image.Image, prompt: str | None = None) -> str:
        """Failures propagate: a swallowed error here used to turn into an empty
        caption on a job that then read "completed" (and so was never retried)."""
        import torch

        prompt = prompt or "Describe this image in one concise sentence."
        with residency.use("qwen2_vl_2b", self.model, self.device):
            self.logger.info("Running Qwen2-VL on prompt: %r", prompt)
            messages = [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": prompt}]}]
            text = self.processor.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
            inputs = self.processor(text=[text], images=[image], return_tensors="pt").to(self.device)
            with torch.no_grad():
                output_ids = self.model.generate(**inputs, max_new_tokens=80)
            # generate() returns the prompt tokens followed by the new ones — trim
            # each row back to just what was generated before decoding.
            trimmed = [out[len(inp):] for inp, out in zip(inputs.input_ids, output_ids)]
            answer = self.processor.batch_decode(trimmed, skip_special_tokens=True)[0]
            self.logger.info("Qwen2-VL answer: %r", answer)
            return answer

    def detect(self, image):
        raise NotImplementedError

    def embed(self, image):
        raise NotImplementedError
