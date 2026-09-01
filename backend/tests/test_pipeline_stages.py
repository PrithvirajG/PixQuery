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
    CaptioningExecutor,
    ClassificationExecutor,
    EmbeddingExecutor,
    FaceDetectionExecutor,
    GrayscaleExecutor,
    ImageWriteExecutor,
    ObjectDetectionExecutor,
    OcrExecutor,
    ResizeExecutor,
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

class _StubCascade:
    """Stands in for cv2's CascadeClassifier so bbox math is deterministic."""

    def __init__(self, rects):
        self.rects = rects
        self.calls = []

    def detectMultiScale(self, gray, scaleFactor, minNeighbors, minSize):
        self.calls.append(
            {"scaleFactor": scaleFactor, "minNeighbors": minNeighbors, "minSize": minSize}
        )
        return self.rects


class FaceDetectionStageTests(unittest.TestCase):
    def setUp(self):
        self.stage = FaceDetectionExecutor()

    def _with_cascade(self, rects):
        self.stage._cascade = _StubCascade(rects)
        return self.stage._cascade

    def test_converts_corner_rect_to_center_bbox(self):
        # OpenCV gives (x, y, w, h) from the top-left; the overlay expects
        # center-based [x_c, y_c, w, h] to match YOLO's xywh.
        self._with_cascade([(10, 20, 30, 40)])
        out = self.stage.run({"image": rgb_image()}, {})
        self.assertEqual(out["detections"][0]["bbox"], [25.0, 40.0, 30.0, 40.0])

    def test_labels_and_confidence(self):
        self._with_cascade([(0, 0, 5, 5)])
        det = self.stage.run({"image": rgb_image()}, {})["detections"][0]
        self.assertEqual(det["label"], "face")
        self.assertEqual(det["confidence"], 1.0)  # Haar has no real score

    def test_emits_under_detections_so_the_overlay_renders_it(self):
        self._with_cascade([(0, 0, 5, 5)])
        self.assertEqual(set(self.stage.run({"image": rgb_image()}, {})), {"detections"})

    def test_no_faces_returns_empty_list_not_none(self):
        self._with_cascade([])
        self.assertEqual(self.stage.run({"image": rgb_image()}, {})["detections"], [])

    def test_default_tuning_is_passed_to_opencv(self):
        cascade = self._with_cascade([])
        self.stage.run({"image": rgb_image()}, {})
        self.assertEqual(
            cascade.calls[0],
            {"scaleFactor": 1.1, "minNeighbors": 5, "minSize": (30, 30)},
        )

    def test_config_overrides_reach_opencv(self):
        # The knobs the node advertises must actually change detection behavior.
        cascade = self._with_cascade([])
        self.stage.run(
            {"image": rgb_image()},
            {"scale_factor": 1.05, "min_neighbors": 3, "min_size": 20},
        )
        self.assertEqual(
            cascade.calls[0],
            {"scaleFactor": 1.05, "minNeighbors": 3, "minSize": (20, 20)},
        )

    def test_real_cascade_loads_from_opencv_data(self):
        # Guards the shipped-with-cv2 path; no download required.
        self.assertFalse(FaceDetectionExecutor()._get_cascade().empty())

    def test_runs_end_to_end_on_a_real_image(self):
        # A blank image has no faces, but this proves the RGB→gray conversion and
        # the real cascade call work together without raising.
        out = FaceDetectionExecutor().run({"image": rgb_image((200, 200))}, {})
        self.assertEqual(out["detections"], [])


# ── object detection / classification / captioning (stubbed models) ───────────

class _StubDetector:
    def __init__(self, detections):
        self.detections = detections
        self.calls = []

    def detect(self, image, write_image):
        self.calls.append({"image": image, "write_image": write_image})
        return self.detections


class ObjectDetectionStageTests(unittest.TestCase):
    def setUp(self):
        self.stage = ObjectDetectionExecutor()

    def test_returns_model_detections(self):
        found = [{"label": "cat", "confidence": 0.9, "bbox": [1, 2, 3, 4]}]
        self.stage._model = _StubDetector(found)
        out = self.stage.run({"image": rgb_image()}, {})
        self.assertEqual(out, {"detections": found})

    def test_none_from_model_becomes_empty_list(self):
        self.stage._model = _StubDetector(None)
        self.assertEqual(self.stage.run({"image": rgb_image()}, {})["detections"], [])

    def test_never_asks_the_model_to_write_an_image(self):
        # Writing is the image_write stage's job; detection must stay read-only.
        stub = _StubDetector([])
        self.stage._model = stub
        self.stage.run({"image": rgb_image()}, {})
        self.assertFalse(stub.calls[0]["write_image"])

    def test_provenance_identifies_the_model(self):
        self.assertEqual(self.stage.node_type, "object_detection")
        self.assertTrue(self.stage.model_name)


class CaptioningStageTests(unittest.TestCase):
    def test_returns_caption_text(self):
        stage = CaptioningExecutor()
        stage._model = type("M", (), {"describe": staticmethod(lambda image: "a cat")})()
        self.assertEqual(stage.run({"image": rgb_image()}, {}), {"caption": "a cat"})

    def test_empty_caption_is_a_string_not_none(self):
        stage = CaptioningExecutor()
        stage._model = type("M", (), {"describe": staticmethod(lambda image: None)})()
        self.assertEqual(stage.run({"image": rgb_image()}, {})["caption"], "")


class ClassificationStageTests(unittest.TestCase):
    def test_registered_with_provenance(self):
        stage = ClassificationExecutor()
        self.assertEqual(stage.node_type, "classification")
        self.assertIsInstance(stage, BaseNodeExecutor)


# ── embedding ─────────────────────────────────────────────────────────────────

class _StubClip:
    def __init__(self):
        self.embedded_images = []
        self.embedded_texts = []

    def embed(self, image):
        self.embedded_images.append(image)
        return [0.1, 0.2, 0.3]

    def embed_text(self, text):
        self.embedded_texts.append(text)
        return [0.4, 0.5, 0.6]


class EmbeddingStageTests(unittest.TestCase):
    def setUp(self):
        self.stage = EmbeddingExecutor()
        self.clip = _StubClip()
        self.stage._model = self.clip

    def test_embeds_the_image(self):
        out = self.stage.run({"image": rgb_image()}, {})
        self.assertEqual(out["embeddings"], [0.1, 0.2, 0.3])
        self.assertEqual(len(self.clip.embedded_images), 1)

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

    def test_provenance_names_the_clip_variant(self):
        self.assertEqual(self.stage.model_name, "clip")
        self.assertEqual(self.stage.model_version, "ViT-B/32")


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
        "object_detection", "face_detection", "classification", "captioning",
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
