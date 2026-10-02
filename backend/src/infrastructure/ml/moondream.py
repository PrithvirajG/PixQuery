from PIL import Image

from .gpu import residency
from .interface import ModelInterface
from src.logging_config import get_logger


class MoondreamModel(ModelInterface):
    """Moondream2 — a second instruction-following vision-language model.

    Loaded at the latest ("main") revision deliberately, not pinned: the
    ``2024-08-26`` revision's bundled modeling code crashes under
    ``transformers>=4.50`` (``PhiForCausalLM`` no longer auto-inherits
    ``GenerationMixin`` — confirmed directly, a real ``AttributeError`` on
    ``.generate()``), and the maintainer's later revision fixes it. Don't pin
    an older revision without re-verifying it still loads.

    Despite the "lightweight" reputation, measured no better than Qwen2-VL on a
    4GB GPU — see VisionLanguageModelExecutor's models comment and the Obsidian
    note it points at. Runs on GPU when available (fp16).
    """

    def __init__(self, model_name: str = "vikhyatk/moondream2"):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        # Loaded into host memory; ``residency.use`` moves it onto the GPU for
        # each call (and parks it again when another heavy model needs the card).
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name,
            trust_remote_code=True,
            torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
        ).eval()
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.logger = get_logger(__name__)
        self.logger.info("Moondream2 model loaded from %s (runs on %s)", model_name, self.device)

    def describe(self, image: Image.Image, prompt: str | None = None) -> str:
        """Failures propagate (see ``Qwen2VLModel.describe``)."""
        prompt = prompt or "Describe this image in one concise sentence."
        with residency.use("moondream2", self.model, self.device):
            self.logger.info("Running Moondream2 on prompt: %r", prompt)
            encoded = self.model.encode_image(image.convert("RGB"))
            answer = self.model.answer_question(encoded, prompt, self.tokenizer)
            self.logger.info("Moondream2 answer: %r", answer)
            return answer

    def detect(self, image):
        raise NotImplementedError

    def embed(self, image):
        raise NotImplementedError
