"""Per-stage tests for every pipeline node type and its configuration.

One class per node_type. Stages built on Pillow/OpenCV are exercised for real —
pixels in, pixels out. Stages fronting a heavy model (YOLO, BLIP, CLIP,
tesseract) get a stub model so what's under test is the executor's own contract:
which context keys it reads, which it returns, and how it interprets config.

The context contract matters as much as the output: ``run`` must return ONLY the
keys it adds or replaces (``BaseNodeExecutor.run``), because PipelineExecutionService
merges those into the graph context and persists them as model_outputs.
"""
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from src.errors.executors import NodeExecutionError, PermanentNodeError
from src.services.executors import get_executor
from src.services.executors.base import BaseNodeExecutor
from src.services.executors.builtin import (
    ClassificationExecutor,
    EmbeddingExecutor,
    FaceDetectionExecutor,
    GrayscaleExecutor,
    ImageWriteExecutor,
    ObjectDetectionExecutor,
    OcrExecutor,
    ResizeExecutor,
    VisionLanguageModelExecutor,
)


def rgb_image(size=(64, 48), color=(200, 120, 40)):
    return Image.new("RGB", size, color)


# ── resize ────────────────────────────────────────────────────────────────────

class ResizeStageTests(unittest.TestCase):
    def setUp(self):
        self.stage = ResizeExecutor()

    def test_defaults_to_640_square(self):
        out = self.stage.run({"image": rgb_image()}, {})
        self.assertEqual(out["image"].size, (640, 640))

    def test_honors_width_and_height(self):
        out = self.stage.run({"image": rgb_image()}, {"width": 100, "height": 50})
        self.assertEqual(out["image"].size, (100, 50))

    def test_coerces_string_config(self):
        # Config arrives from JSON/form input, so numbers may be strings.
        out = self.stage.run({"image": rgb_image()}, {"width": "32", "height": "16"})
        self.assertEqual(out["image"].size, (32, 16))

    def test_does_not_mutate_the_input_image(self):
        original = rgb_image((64, 48))
        self.stage.run({"image": original}, {"width": 10, "height": 10})
        self.assertEqual(original.size, (64, 48))

    def test_returns_only_the_image_key(self):
        out = self.stage.run({"image": rgb_image(), "caption": "keep me"}, {})
        self.assertEqual(set(out), {"image"})


# ── grayscale ─────────────────────────────────────────────────────────────────

class GrayscaleStageTests(unittest.TestCase):
    def setUp(self):
        self.stage = GrayscaleExecutor()

    def test_pixels_become_gray(self):
        out = self.stage.run({"image": rgb_image(color=(200, 120, 40))}, {})
        r, g, b = out["image"].getpixel((0, 0))
        self.assertEqual((r, g), (g, b))  # all channels equal → gray

    def test_stays_three_channel_rgb_for_downstream_models(self):
        # Deliberate: models expect 3 channels, so "L" is converted back to RGB.
        out = self.stage.run({"image": rgb_image()}, {})
        self.assertEqual(out["image"].mode, "RGB")

    def test_preserves_dimensions(self):
        out = self.stage.run({"image": rgb_image((77, 33))}, {})
        self.assertEqual(out["image"].size, (77, 33))

    def test_returns_only_the_image_key(self):
        self.assertEqual(set(self.stage.run({"image": rgb_image()}, {})), {"image"})


# ── face detection ────────────────────────────────────────────────────────────

class _StubFaceDetector:
    """Stands in for a face_detectors wrapper so bbox math is deterministic."""

    def __init__(self, boxes):
        from src.infrastructure.ml.face_detectors import FaceBox

        self.boxes = [FaceBox(*b) for b in boxes]
        self.thresholds = []

    def detect(self, image, threshold):
        self.thresholds.append(threshold)
        return self.boxes


class FaceDetectionStageTests(unittest.TestCase):
    def setUp(self):
        self.stage = FaceDetectionExecutor()

    def _with_detector(self, boxes, model_id="retinaface_r50"):
        stub = _StubFaceDetector(boxes)
        self.stage._detectors[model_id] = stub
        return stub

    def test_converts_corner_box_to_center_bbox(self):
        # Detectors give (x1, y1, x2, y2); the overlay expects center-based
        # [x_c, y_c, w, h] to match YOLO's xywh.
        self._with_detector([(10, 20, 40, 60, 0.9)])
        out = self.stage.run({"image": rgb_image()}, {})
        self.assertEqual(out["detections"][0]["bbox"], [25.0, 40.0, 30.0, 40.0])

    def test_labels_and_confidence(self):
        self._with_detector([(0, 0, 5, 5, 0.87)])
        det = self.stage.run({"image": rgb_image()}, {})["detections"][0]
        self.assertEqual(det["label"], "face")
        self.assertEqual(det["confidence"], 0.87)

    def test_emits_under_detections_so_the_overlay_renders_it(self):
        self._with_detector([(0, 0, 5, 5, 0.9)])
        self.assertEqual(set(self.stage.run({"image": rgb_image()}, {})), {"detections"})

    def test_no_faces_returns_empty_list_not_none(self):
        self._with_detector([])
        self.assertEqual(self.stage.run({"image": rgb_image()}, {})["detections"], [])

    def test_default_threshold_and_override_reach_the_detector(self):
        stub = self._with_detector([])
        self.stage.run({"image": rgb_image()}, {})
        self.stage.run({"image": rgb_image()}, {"confidence_threshold": "0.8"})
        self.assertEqual(stub.thresholds, [0.5, 0.8])

    def test_defaults_to_retinaface(self):
        self.assertEqual(self.stage.resolve_model({}).id, "retinaface_r50")

    def test_config_model_selects_the_detector(self):
        retina = self._with_detector([(0, 0, 5, 5, 0.9)])
        yunet = self._with_detector([], model_id="yunet")
        self.stage.run({"image": rgb_image()}, {"model": "yunet"})
        self.assertEqual((len(retina.thresholds), len(yunet.thresholds)), (0, 1))

    def test_every_advertised_model_has_a_loader(self):
        # A model in the dropdown with no wrapper behind it would fail every job.
        from src.infrastructure.ml import face_detectors

        for spec in FaceDetectionExecutor.models:
            with self.subTest(model=spec.id):
                loader = {
                    "yunet": face_detectors.YuNetFaceDetector,
                    "scrfd": face_detectors.ScrfdFaceDetector,
                    "retinaface_r50": face_detectors.RetinaFaceDetector,
                }.get(spec.id)
                self.assertIsNotNone(loader)


# ── object detection / classification / captioning (stubbed models) ───────────

class _StubDetector:
    def __init__(self, detections):
        self.detections = detections
        self.calls = []

    def detect(self, image, write_image, conf=None):
        self.calls.append({"image": image, "write_image": write_image, "conf": conf})
        return self.detections


class ObjectDetectionStageTests(unittest.TestCase):
    def setUp(self):
        self.stage = ObjectDetectionExecutor()

    def _with_model(self, detections, model_id="yolov8n"):
        stub = _StubDetector(detections)
        self.stage._models[model_id] = stub
        return stub

    def test_returns_model_detections(self):
        found = [{"label": "cat", "confidence": 0.9, "bbox": [1, 2, 3, 4]}]
        self._with_model(found)
        out = self.stage.run({"image": rgb_image()}, {})
        self.assertEqual(out, {"detections": found})

    def test_none_from_model_becomes_empty_list(self):
        self._with_model(None)
        self.assertEqual(self.stage.run({"image": rgb_image()}, {})["detections"], [])

    def test_never_asks_the_model_to_write_an_image(self):
        # Writing is the image_write stage's job; detection must stay read-only.
        stub = self._with_model([])
        self.stage.run({"image": rgb_image()}, {})
        self.assertFalse(stub.calls[0]["write_image"])

    def test_confidence_reaches_the_model_with_legacy_threshold_alias(self):
        stub = self._with_model([])
        self.stage.run({"image": rgb_image()}, {})
        self.stage.run({"image": rgb_image()}, {"confidence": 0.6})
        self.stage.run({"image": rgb_image()}, {"threshold": 0.7})
        self.assertEqual([c["conf"] for c in stub.calls], [0.25, 0.6, 0.7])

    def test_config_model_selects_the_weights(self):
        small = self._with_model([], model_id="yolov8s")
        self.stage.run({"image": rgb_image()}, {"model": "yolov8s"})
        self.assertEqual(len(small.calls), 1)

    def test_unknown_model_fails_permanently(self):
        with self.assertRaises(PermanentNodeError):
            self.stage.run({"image": rgb_image()}, {"model": "yolov99"})

    def test_provenance_names_the_chosen_model(self):
        self.assertEqual(self.stage.provenance({}), ("yolov8n", "ultralytics-v8"))
        self.assertEqual(self.stage.provenance({"model": "yolov8m"})[0], "yolov8m")


class _StubVlm:
    """Stands in for BlipModel/Qwen2VLModel/MoondreamModel — every one of them
    exposes describe(image, prompt=None), regardless of whether it actually
    honors the prompt."""

    def __init__(self, answer):
        self.answer = answer
        self.calls = []

    def describe(self, image, prompt=None):
        self.calls.append(prompt)
        return self.answer


class VisionLanguageModelStageTests(unittest.TestCase):
    """node_type "vision_language_model" — renamed from "captioning" by migration
    0003 (see migrations/runner.py) when the node widened from BLIP-only
    unconditioned captioning to a configurable prompt + a choice of real
    instruction-following VLMs."""

    def setUp(self):
        self.stage = VisionLanguageModelExecutor()
        self.blip = _StubVlm("a cat")
        self.stage._models["blip"] = self.blip

    def test_returns_caption_text(self):
        self.assertEqual(self.stage.run({"image": rgb_image()}, {}), {"caption": "a cat"})

    def test_empty_caption_is_a_string_not_none(self):
        self.stage._models["blip"] = _StubVlm(None)
        self.assertEqual(self.stage.run({"image": rgb_image()}, {})["caption"], "")

    def test_default_model_is_blip_with_no_prompt_forwarded(self):
        # BLIP (supports_prompt=False) still gets called through describe(..., prompt=...)
        # — one call path for every model — but the prompt it receives is always
        # None, regardless of what's configured, since it can't act on one.
        self.stage.run({"image": rgb_image()}, {"prompt": "What brand is visible?"})
        self.assertEqual(self.blip.calls, [None])

    def test_a_prompt_capable_model_receives_the_configured_prompt(self):
        qwen = _StubVlm("A storefront with a red awning.")
        self.stage._models["qwen2_vl_2b"] = qwen

        out = self.stage.run(
            {"image": rgb_image()},
            {"model": "qwen2_vl_2b", "prompt": "What brand is visible?"},
        )

        self.assertEqual(out["caption"], "A storefront with a red awning.")
        self.assertEqual(qwen.calls, ["What brand is visible?"])

    def test_a_prompt_capable_model_with_no_configured_prompt_gets_none(self):
        # Its own describe() supplies a sensible default (see Qwen2VLModel) —
        # the executor must not invent one on top of that.
        qwen = _StubVlm("x")
        self.stage._models["qwen2_vl_2b"] = qwen
        self.stage.run({"image": rgb_image()}, {"model": "qwen2_vl_2b"})
        self.assertEqual(qwen.calls, [None])

    def test_unknown_model_fails_permanently(self):
        with self.assertRaises(PermanentNodeError):
            self.stage.run({"image": rgb_image()}, {"model": "not-a-real-model"})

    def test_defaults_to_blip(self):
        self.assertEqual(self.stage.resolve_model({}).id, "blip")

    def test_only_blip_lacks_prompt_support(self):
        by_id = {spec.id: spec for spec in VisionLanguageModelExecutor.models}
        self.assertEqual(
            {spec_id for spec_id, spec in by_id.items() if not spec.supports_prompt},
            {"blip"},
        )

    def test_every_advertised_model_has_a_loader(self):
        # Checked statically against the dispatch table, not by calling
        # _get_model() — which would instantiate the real (network-fetching,
        # slow-loading, for the VLMs GPU-hungry) model wrapper.
        loaders = {"blip", "qwen2_vl_2b", "moondream2"}
        for spec in VisionLanguageModelExecutor.models:
            with self.subTest(model=spec.id):
                self.assertIn(spec.id, loaders, f"no loader registered for model '{spec.id}'")


class _StubClassifier:
    """A 'model' returning fixed logits, so top-k ordering is deterministic."""

    def __init__(self, logits):
        import torch

        self.logits = torch.tensor([logits], dtype=torch.float32)

    def __call__(self, batch):
        return self.logits


class ClassificationStageTests(unittest.TestCase):
    def setUp(self):
        self.stage = ClassificationExecutor()

    def _with_model(self, logits, model_id="efficientnet_b0"):
        import torch

        categories = [f"class{i}" for i in range(len(logits))]
        preprocess = lambda image: torch.zeros(3, 4, 4)  # noqa: E731
        self.stage._loaded[model_id] = (_StubClassifier(logits), preprocess, categories)

    def test_returns_top_k_labels_highest_first(self):
        self._with_model([0.0, 3.0, 1.0, 2.0])
        labels = self.stage.run({"image": rgb_image()}, {"top_k": 2})["labels"]
        self.assertEqual([l["label"] for l in labels], ["class1", "class3"])
        self.assertGreater(labels[0]["confidence"], labels[1]["confidence"])

    def test_top_k_is_capped_at_the_number_of_classes(self):
        self._with_model([1.0, 2.0])
        self.assertEqual(len(self.stage.run({"image": rgb_image()}, {"top_k": 10})["labels"]), 2)

    def test_defaults_to_efficientnet(self):
        self.assertEqual(self.stage.resolve_model({}).id, "efficientnet_b0")

    def test_config_model_selects_the_network(self):
        self._with_model([5.0, 0.0], model_id="vit_b_16")
        labels = self.stage.run({"image": rgb_image()}, {"model": "vit_b_16", "top_k": 1})["labels"]
        self.assertEqual(labels[0]["label"], "class0")

    def test_every_advertised_model_maps_to_torchvision(self):
        import torchvision.models as tvm

        from src.services.executors.builtin import _CLASSIFIERS

        for spec in ClassificationExecutor.models:
            with self.subTest(model=spec.id):
                builder, weights = _CLASSIFIERS[spec.id]
                self.assertTrue(callable(getattr(tvm, builder)))
                self.assertTrue(hasattr(getattr(tvm, weights), "DEFAULT"))


# ── embedding ─────────────────────────────────────────────────────────────────

class _StubEmbedder:
    """Stands in for ClipModel/Dinov2Model. `text_capable=False` mimics DINOv2:
    embed_text is not just unused but genuinely absent/raising, so a test that
    accidentally calls it on a text-incapable stub fails loudly."""

    def __init__(self, vector, text_vector=None, *, text_capable=True):
        self.vector = vector
        self.text_vector = text_vector
        self.text_capable = text_capable
        self.embedded_images = []
        self.embedded_texts = []

    def embed(self, image):
        self.embedded_images.append(image)
        return self.vector

    def embed_text(self, text):
        if not self.text_capable:
            raise NotImplementedError("this stub has no text tower")
        self.embedded_texts.append(text)
        return self.text_vector


class EmbeddingStageTests(unittest.TestCase):
    def setUp(self):
        self.stage = EmbeddingExecutor()
        self.clip = _StubEmbedder([0.1, 0.2, 0.3], [0.4, 0.5, 0.6])
        self.stage._models["clip"] = self.clip

    def test_embeds_the_image(self):
        out = self.stage.run({"image": rgb_image()}, {})
        self.assertEqual(out["embeddings"], [0.1, 0.2, 0.3])
        self.assertEqual(len(self.clip.embedded_images), 1)

    def test_reports_which_model_produced_the_vectors(self):
        # Read by PipelineExecutionService._store_embeddings to route storage to
        # this model's own Weaviate class; must never be persisted as an output
        # (see pipeline_execution_service._PERSIST_SKIP_KEYS).
        out = self.stage.run({"image": rgb_image()}, {})
        self.assertEqual(out["embedding_model"], "clip")

    def test_no_caption_means_no_text_embedding(self):
        out = self.stage.run({"image": rgb_image()}, {})
        self.assertNotIn("text_embedding", out)
        self.assertEqual(self.clip.embedded_texts, [])

    def test_caption_in_context_is_also_embedded_for_semantic_search(self):
        out = self.stage.run({"image": rgb_image(), "caption": "a tabby cat"}, {})
        self.assertEqual(out["text_embedding"], [0.4, 0.5, 0.6])
        self.assertEqual(self.clip.embedded_texts, ["a tabby cat"])

    def test_empty_caption_is_not_embedded(self):
        out = self.stage.run({"image": rgb_image(), "caption": ""}, {})
        self.assertNotIn("text_embedding", out)

    def test_provenance_names_the_default_clip_variant(self):
        self.assertEqual(self.stage.provenance({}), ("clip", "ViT-B/32"))

    def test_config_model_selects_the_variant(self):
        vitl14 = _StubEmbedder([0.7, 0.8], [0.9, 1.0])
        self.stage._models["clip_vit_l14"] = vitl14

        out = self.stage.run({"image": rgb_image(), "caption": "x"}, {"model": "clip_vit_l14"})

        self.assertEqual(out["embeddings"], [0.7, 0.8])
        self.assertEqual(out["embedding_model"], "clip_vit_l14")
        self.assertEqual(self.clip.embedded_images, [])  # the default model was never touched
        self.assertEqual(self.stage.provenance({"model": "clip_vit_l14"}), ("clip_vit_l14", "ViT-L/14"))

    def test_a_text_incapable_model_never_gets_embed_text_called_even_with_a_caption(self):
        # DINOv2 in miniature: present, but genuinely has no embed_text to call.
        dino = _StubEmbedder([0.7, 0.8, 0.9], text_capable=False)
        self.stage._models["dinov2"] = dino

        out = self.stage.run({"image": rgb_image(), "caption": "a tabby cat"}, {"model": "dinov2"})

        self.assertEqual(out["embeddings"], [0.7, 0.8, 0.9])
        self.assertNotIn("text_embedding", out)
        self.assertEqual(out["embedding_model"], "dinov2")

    def test_unknown_model_fails_permanently(self):
        with self.assertRaises(PermanentNodeError):
            self.stage.run({"image": rgb_image()}, {"model": "not-a-real-model"})

    def test_every_advertised_model_has_a_loader(self):
        # A model in the dropdown with no wrapper behind it would fail every job.
        # Checked statically against the dispatch table — NOT by calling
        # _get_model(), which would instantiate the real (network-fetching,
        # slow-loading) model wrapper.
        from src.services.executors.builtin import _CLIP_VARIANTS

        for spec in EmbeddingExecutor.models:
            with self.subTest(model=spec.id):
                has_loader = spec.id in _CLIP_VARIANTS or spec.id == "dinov2"
                self.assertTrue(has_loader, f"no loader registered for embedding model '{spec.id}'")

    def test_dinov2_is_the_only_model_without_a_text_tower(self):
        by_id = {spec.id: spec for spec in EmbeddingExecutor.models}
        self.assertEqual(
            {spec_id for spec_id, spec in by_id.items() if not spec.supports_text},
            {"dinov2"},
        )


# ── image write ───────────────────────────────────────────────────────────────

class ImageWriteStageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.source = self.root / "photo.jpg"
        rgb_image((40, 30)).save(self.source)
        self.stage = ImageWriteExecutor()
        self.asset = {"_id": "asset-123", "current_path": str(self.source)}

    def tearDown(self):
        self.tmp.cleanup()

    def _run(self, config, image=None):
        return self.stage.run(
            {"image": image or rgb_image((40, 30)), "asset": self.asset}, config
        )

    def test_reports_path_format_and_size(self):
        out = self._run({"directory": str(self.root / "out")})["written_image"]
        self.assertTrue(Path(out["path"]).exists())
        self.assertEqual((out["width"], out["height"]), (40, 30))
        self.assertEqual(out["format"], "jpeg")

    def test_writes_each_supported_format(self):
        for fmt, ext in (("png", "png"), ("webp", "webp"), ("bmp", "bmp"), ("tiff", "tiff")):
            with self.subTest(fmt=fmt):
                out = self._run({"directory": str(self.root / fmt), "format": fmt})
                path = Path(out["written_image"]["path"])
                self.assertEqual(path.suffix, f".{ext}")
                with Image.open(path) as saved:
                    self.assertEqual(saved.size, (40, 30))

    def test_unknown_format_falls_back_to_jpeg(self):
        out = self._run({"directory": str(self.root / "u"), "format": "heif"})
        self.assertEqual(Path(out["written_image"]["path"]).suffix, ".jpg")

    def test_jpeg_quality_changes_file_size(self):
        low = self._run({"directory": str(self.root / "lo"), "quality": 10})
        high = self._run({"directory": str(self.root / "hi"), "quality": 95})
        self.assertLess(
            Path(low["written_image"]["path"]).stat().st_size,
            Path(high["written_image"]["path"]).stat().st_size,
        )

    def test_rgba_is_converted_for_jpeg(self):
        # JPEG cannot hold an alpha channel — this must not raise.
        out = self._run({"directory": str(self.root / "a")}, image=Image.new("RGBA", (8, 8)))
        self.assertTrue(Path(out["written_image"]["path"]).exists())

    def test_filename_template_tokens(self):
        out = self._run(
            {"directory": str(self.root / "t"), "filename": "{stem}-{asset}.{ext}"}
        )
        self.assertEqual(Path(out["written_image"]["path"]).name, "photo-asset-123.jpg")

    def test_is_a_sink_and_leaves_the_context_image_alone(self):
        # Returns only written_image, so later nodes still see the same image.
        out = self._run({"directory": str(self.root / "s")})
        self.assertEqual(set(out), {"written_image"})

    def test_source_file_is_never_touched(self):
        before = self.source.read_bytes()
        self._run({"directory": str(self.root / "n")})
        self.assertEqual(self.source.read_bytes(), before)

    def test_missing_image_raises_a_node_error(self):
        with self.assertRaises(NodeExecutionError):
            self.stage.run({"asset": self.asset}, {})


# ── ocr ───────────────────────────────────────────────────────────────────────

class OcrStageTests(unittest.TestCase):
    def setUp(self):
        self.stage = OcrExecutor()

    def _patch_tesseract(self, text, recorder=None):
        import sys
        import types

        module = types.ModuleType("pytesseract")

        def image_to_string(image, lang="eng"):
            if recorder is not None:
                recorder.append(lang)
            return text

        module.image_to_string = image_to_string
        self._saved = sys.modules.get("pytesseract")
        sys.modules["pytesseract"] = module
        self.addCleanup(self._restore)

    def _restore(self):
        import sys

        if self._saved is None:
            sys.modules.pop("pytesseract", None)
        else:
            sys.modules["pytesseract"] = self._saved

    def test_returns_stripped_text(self):
        self._patch_tesseract("  INVOICE 42 \n")
        self.assertEqual(
            self.stage.run({"image": rgb_image()}, {}), {"ocr_text": "INVOICE 42"}
        )

    def test_no_text_returns_empty_string(self):
        self._patch_tesseract("")
        self.assertEqual(self.stage.run({"image": rgb_image()}, {})["ocr_text"], "")

    def test_lang_config_is_forwarded(self):
        langs = []
        self._patch_tesseract("x", recorder=langs)
        self.stage.run({"image": rgb_image()}, {"lang": "deu"})
        self.assertEqual(langs, ["deu"])

    def test_lang_defaults_to_eng(self):
        langs = []
        self._patch_tesseract("x", recorder=langs)
        self.stage.run({"image": rgb_image()}, {})
        self.assertEqual(langs, ["eng"])


# ── registry ──────────────────────────────────────────────────────────────────

class RegistryTests(unittest.TestCase):
    ALL_STAGES = [
        "object_detection", "face_detection", "classification", "vision_language_model",
        "embedding", "resize", "grayscale", "image_write", "ocr",
    ]

    def test_every_stage_resolves_to_a_matching_executor(self):
        for node_type in self.ALL_STAGES:
            with self.subTest(node_type=node_type):
                executor = get_executor(node_type)
                self.assertIsInstance(executor, BaseNodeExecutor)
                self.assertEqual(executor.node_type, node_type)

    def test_executors_are_cached_so_models_load_once_per_process(self):
        self.assertIs(get_executor("resize"), get_executor("resize"))

    def test_unknown_stage_fails_permanently_rather_than_retrying(self):
        with self.assertRaises(PermanentNodeError):
            get_executor("does_not_exist")

    def test_every_seeded_system_node_has_an_executor(self):
        # A seeded node with no executor would fail every job that uses it.
        from src.repositories.pipeline_nodes_repository import PipelineNodesRepository

        for spec in PipelineNodesRepository._SYSTEM_NODES:
            with self.subTest(node_type=spec["node_type"]):
                self.assertIsInstance(get_executor(spec["node_type"]), BaseNodeExecutor)

    def test_seeded_output_ports_match_what_executors_emit(self):
        # The regression behind the Face Detection bug: the node advertised a
        # "faces" port while its executor emitted "detections".
        from src.repositories.pipeline_nodes_repository import PipelineNodesRepository

        emitted = {
            "object_detection": ["detections"],
            "face_detection": ["detections"],
            "resize": ["image"],
            "grayscale": ["image"],
            "embedding": ["embeddings"],
            "ocr": ["ocr_text"],
        }
        for spec in PipelineNodesRepository._SYSTEM_NODES:
            expected = emitted.get(spec["node_type"])
            if expected is None:
                continue
            with self.subTest(node_type=spec["node_type"]):
                self.assertEqual(spec["context_outputs"], expected)


if __name__ == "__main__":
    unittest.main()
