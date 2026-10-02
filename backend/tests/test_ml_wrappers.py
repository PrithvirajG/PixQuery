"""Model wrappers in infrastructure/ml, with the underlying library stubbed.

These pin the adapter logic each wrapper owns — output shape, threshold handling,
channel order, weight download — without loading any real weights. (The real
models were verified manually against samples/sample-photo.jpg.)
"""
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

import numpy as np
from PIL import Image

from src.infrastructure.ml import face_detectors
from src.infrastructure.ml.face_detectors import (
    FaceBox,
    RetinaFaceDetector,
    ScrfdFaceDetector,
    YuNetFaceDetector,
)


def red_image(size=(8, 6)):
    return Image.new("RGB", size, (255, 0, 0))


class BgrConversionTests(unittest.TestCase):
    def test_rgb_becomes_bgr(self):
        bgr = face_detectors._bgr(red_image())
        self.assertEqual(bgr.shape, (6, 8, 3))
        self.assertEqual(tuple(bgr[0, 0]), (0, 0, 255))

    def test_non_rgb_input_is_converted_first(self):
        self.assertEqual(face_detectors._bgr(Image.new("L", (4, 4))).shape, (4, 4, 3))


class _StubYuNet:
    def __init__(self, faces):
        self.faces = faces
        self.calls = []

    def setInputSize(self, size):
        self.calls.append(("size", size))

    def setScoreThreshold(self, threshold):
        self.calls.append(("threshold", threshold))

    def detect(self, image):
        return 1, self.faces


class YuNetTests(unittest.TestCase):
    def _detector(self, faces):
        det = YuNetFaceDetector.__new__(YuNetFaceDetector)
        det._detector = _StubYuNet(faces)
        return det

    def test_row_is_converted_to_corner_box_with_score(self):
        # YuNet row: x, y, w, h, 5 landmark pairs, score.
        row = np.array([[10, 20, 30, 40] + [0] * 10 + [0.93]], dtype=np.float32)
        (box,) = self._detector(row).detect(red_image(), 0.6)
        self.assertEqual(tuple(box[:4]), (10.0, 20.0, 40.0, 60.0))
        self.assertAlmostEqual(box.score, 0.93, places=5)

    def test_input_size_and_threshold_are_set_per_call(self):
        det = self._detector(None)
        det.detect(red_image((8, 6)), 0.7)
        self.assertEqual(det._detector.calls, [("size", (8, 6)), ("threshold", 0.7)])

    def test_no_faces_is_empty_list(self):
        self.assertEqual(self._detector(None).detect(red_image(), 0.5), [])

    def test_weights_download_once_into_the_cache(self):
        with tempfile.TemporaryDirectory() as cache, \
                mock.patch.object(face_detectors, "MODEL_CACHE_DIR", cache), \
                mock.patch.object(face_detectors.urllib.request, "urlretrieve") as fetch, \
                mock.patch("cv2.FaceDetectorYN.create") as create:
            fetch.side_effect = lambda url, path: open(path, "wb").close()
            YuNetFaceDetector()
            YuNetFaceDetector()
            self.assertEqual(fetch.call_count, 1)
            weights = os.path.join(cache, YuNetFaceDetector.WEIGHTS_FILE)
            self.assertTrue(os.path.exists(weights))
            self.assertEqual(create.call_args[0][0], weights)


class ScrfdTests(unittest.TestCase):
    def test_filters_by_threshold_and_maps_bbox(self):
        faces = [
            SimpleNamespace(bbox=np.array([1, 2, 3, 4]), det_score=0.9),
            SimpleNamespace(bbox=np.array([5, 6, 7, 8]), det_score=0.3),
        ]
        det = ScrfdFaceDetector.__new__(ScrfdFaceDetector)
        det._app = SimpleNamespace(get=lambda bgr: faces)
        self.assertEqual(det.detect(red_image(), 0.5), [FaceBox(1.0, 2.0, 3.0, 4.0, 0.9)])


class RetinaFaceTests(unittest.TestCase):
    def test_passes_bgr_and_threshold_and_maps_dicts(self):
        calls = []

        def model(image, **kwargs):
            calls.append((image, kwargs))
            return [{"box": [1, 2, 3, 4], "kps": None, "score": 0.99}]

        det = RetinaFaceDetector.__new__(RetinaFaceDetector)
        det._model = model
        self.assertEqual(det.detect(red_image(), 0.6), [FaceBox(1.0, 2.0, 3.0, 4.0, 0.99)])
        image, kwargs = calls[0]
        self.assertEqual(tuple(image[0, 0]), (0, 0, 255))  # BGR
        self.assertEqual(kwargs, {"threshold": 0.6, "cv": True, "return_dict": True})


class _EmptyBoxes:
    cls = []
    conf = []

    def __iter__(self):
        return iter([])


class YoloConfidenceTests(unittest.TestCase):
    def _model(self):
        from src.infrastructure.ml.yolo import YoloModel

        calls = []
        result = SimpleNamespace(boxes=_EmptyBoxes(), names={})

        def predict(image, **kwargs):
            calls.append(kwargs)
            return [result]

        yolo = YoloModel.__new__(YoloModel)
        yolo.model = predict
        yolo.logger = mock.Mock()
        return yolo, calls

    def test_conf_is_forwarded_to_ultralytics(self):
        yolo, calls = self._model()
        yolo.detect(red_image(), conf=0.4)
        self.assertEqual(calls, [{"conf": 0.4}])

    def test_no_conf_keeps_ultralytics_default(self):
        yolo, calls = self._model()
        yolo.detect(red_image())
        self.assertEqual(calls, [{}])


class _Recorder:
    """A torch-module stand-in that records the devices it is moved to."""

    def __init__(self, name, log):
        self.name, self.log = name, log

    def to(self, device):
        self.log.append((self.name, device))
        return self


class _Inputs(dict):
    input_ids = [[1, 2]]

    def to(self, device):
        return self


class HeavyVlmsShareTheGpuOneAtATimeTests(unittest.TestCase):
    """Qwen2-VL and Moondream2 must hand the GPU over rather than sit on it together —
    holding both (plus CLIP) is what ran the 4GB card out of memory."""

    def test_running_one_vlm_parks_the_other(self):
        from src.infrastructure.ml import gpu, moondream, qwen_vl

        log = []
        residency = gpu.GpuResidency()

        qwen = qwen_vl.Qwen2VLModel.__new__(qwen_vl.Qwen2VLModel)
        qwen.device, qwen.logger = "cuda", mock.Mock()
        qwen.model = SimpleNamespace(to=_Recorder("qwen", log).to, generate=lambda **kw: [[1, 2, 3]])
        qwen.processor = mock.MagicMock()
        qwen.processor.return_value = _Inputs()
        qwen.processor.batch_decode.return_value = ["a caption"]

        moon = moondream.MoondreamModel.__new__(moondream.MoondreamModel)
        moon.device, moon.logger, moon.tokenizer = "cuda", mock.Mock(), object()
        moon.model = SimpleNamespace(
            to=_Recorder("moondream", log).to,
            encode_image=lambda img: "enc",
            answer_question=lambda enc, prompt, tok: "a sentence",
        )

        with mock.patch.object(gpu, "release_gpu_memory"), \
                mock.patch.object(qwen_vl, "residency", residency), \
                mock.patch.object(moondream, "residency", residency):
            self.assertEqual(qwen.describe(red_image(), prompt="p"), "a caption")
            self.assertEqual(moon.describe(red_image(), prompt="p"), "a sentence")
            self.assertEqual(qwen.describe(red_image(), prompt="p"), "a caption")

        self.assertEqual(
            log,
            [("qwen", "cuda"), ("qwen", "cpu"), ("moondream", "cuda"),
             ("moondream", "cpu"), ("qwen", "cuda")],
        )


class WrappersPropagateFailuresTests(unittest.TestCase):
    """A swallowed model error used to become an empty caption / missing embedding on a
    job that then read "completed" and was never retried. Each wrapper must raise."""

    def _boom(self, *args, **kwargs):
        raise RuntimeError("CUDA error: out of memory")

    def test_clip_embed_raises(self):
        from src.infrastructure.ml.clip import ClipModel

        clip = ClipModel.__new__(ClipModel)
        clip.device, clip.logger, clip.preprocess = "cpu", mock.Mock(), self._boom
        with self.assertRaises(RuntimeError):
            clip.embed(red_image())

    def test_clip_embed_text_raises(self):
        from src.infrastructure.ml.clip import ClipModel

        clip = ClipModel.__new__(ClipModel)
        clip.device, clip.logger = "cpu", mock.Mock()
        with mock.patch("src.infrastructure.ml.clip.clip.tokenize", self._boom):
            with self.assertRaises(RuntimeError):
                clip.embed_text("a cat")

    def test_yolo_detect_raises(self):
        from src.infrastructure.ml.yolo import YoloModel

        yolo = YoloModel.__new__(YoloModel)
        yolo.model, yolo.logger = self._boom, mock.Mock()
        with self.assertRaises(RuntimeError):
            yolo.detect(red_image())

    def test_blip_describe_raises(self):
        from src.infrastructure.ml.blip import BlipModel

        blip = BlipModel.__new__(BlipModel)
        blip.processor, blip.logger = self._boom, mock.Mock()
        with self.assertRaises(RuntimeError):
            blip.describe(red_image())

    def test_qwen_describe_raises(self):
        from src.infrastructure.ml.qwen_vl import Qwen2VLModel

        qwen = Qwen2VLModel.__new__(Qwen2VLModel)
        qwen.device, qwen.logger, qwen.model = "cpu", mock.Mock(), mock.Mock()
        qwen.processor = SimpleNamespace(apply_chat_template=self._boom)
        with self.assertRaises(RuntimeError):
            qwen.describe(red_image(), prompt="p")

    def test_moondream_describe_raises(self):
        from src.infrastructure.ml.moondream import MoondreamModel

        moon = MoondreamModel.__new__(MoondreamModel)
        moon.device, moon.logger = "cpu", mock.Mock()
        moon.model = SimpleNamespace(encode_image=self._boom)
        with self.assertRaises(RuntimeError):
            moon.describe(red_image(), prompt="p")


if __name__ == "__main__":
    unittest.main()
