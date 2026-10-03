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


class _FakeHfModel:
    """Records what a wrapper does to a freshly loaded model."""

    def __init__(self):
        self.moves, self.eval_called = [], False

    def eval(self):
        self.eval_called = True
        return self

    def to(self, device):
        self.moves.append(device)
        return self


class VlmConstructorsKeepWeightsInHostMemoryTests(unittest.TestCase):
    """Heavy VLMs load into host RAM and are moved to the GPU only inside
    residency.use() — a constructor that did `.to("cuda")` would put two big models
    on the card at load time, which is what ran the 4GB GPU out of memory."""

    def _construct(self, cuda, patches, build):
        model = _FakeHfModel()
        loaders = {name: mock.Mock(return_value=model if name.endswith("model") else mock.Mock())
                   for name in patches}
        stack = [mock.patch("torch.cuda.is_available", return_value=cuda)]
        stack += [mock.patch(target, loaders[name]) for name, target in patches.items()]
        for ctx in stack:
            ctx.start()
            self.addCleanup(ctx.stop)
        return build(), model, loaders

    def test_qwen(self):
        import torch

        from src.infrastructure.ml.qwen_vl import Qwen2VLModel

        for cuda, dtype in ((True, torch.float16), (False, torch.float32)):
            with self.subTest(cuda=cuda):
                wrapper, model, loaders = self._construct(
                    cuda,
                    {"processor": "transformers.AutoProcessor.from_pretrained",
                     "model": "transformers.Qwen2VLForConditionalGeneration.from_pretrained"},
                    Qwen2VLModel,
                )
                self.assertEqual(wrapper.device, "cuda" if cuda else "cpu")
                self.assertEqual(model.moves, [])
                self.assertTrue(model.eval_called)
                self.assertEqual(loaders["model"].call_args.kwargs["torch_dtype"], dtype)

    def test_moondream(self):
        import torch

        from src.infrastructure.ml.moondream import MoondreamModel

        for cuda, dtype in ((True, torch.float16), (False, torch.float32)):
            with self.subTest(cuda=cuda):
                wrapper, model, loaders = self._construct(
                    cuda,
                    {"model": "transformers.AutoModelForCausalLM.from_pretrained",
                     "tokenizer": "transformers.AutoTokenizer.from_pretrained"},
                    MoondreamModel,
                )
                self.assertEqual(wrapper.device, "cuda" if cuda else "cpu")
                self.assertEqual(model.moves, [])
                self.assertTrue(loaders["model"].call_args.kwargs["trust_remote_code"])
                self.assertEqual(loaders["model"].call_args.kwargs["torch_dtype"], dtype)

    def test_blip(self):
        import torch

        from src.infrastructure.ml.blip import BlipModel

        for cuda, dtype in ((True, torch.float16), (False, torch.float32)):
            with self.subTest(cuda=cuda):
                wrapper, model, loaders = self._construct(
                    cuda,
                    {"processor": "src.infrastructure.ml.blip.BlipProcessor.from_pretrained",
                     "model": "src.infrastructure.ml.blip.BlipForConditionalGeneration.from_pretrained"},
                    BlipModel,
                )
                self.assertEqual((wrapper.device, wrapper.dtype), ("cuda" if cuda else "cpu", dtype))
                self.assertEqual(model.moves, [])
                self.assertEqual(loaders["model"].call_args.kwargs["torch_dtype"], dtype)

    def test_dinov2_is_small_so_it_goes_straight_to_the_device(self):
        from src.infrastructure.ml.dinov2 import Dinov2Model

        wrapper, model, _ = self._construct(
            True,
            {"processor": "transformers.AutoImageProcessor.from_pretrained",
             "model": "transformers.AutoModel.from_pretrained"},
            Dinov2Model,
        )
        self.assertEqual((wrapper.device, model.moves, model.eval_called), ("cuda", ["cuda"], True))


class YoloAndClipSetupTests(unittest.TestCase):
    def test_yolo_loads_the_given_weights(self):
        from src.infrastructure.ml import yolo

        with mock.patch.object(yolo, "YOLO") as ultralytics:
            model = yolo.YoloModel(model_path="w.pt")
        ultralytics.assert_called_once_with("w.pt")
        self.assertIs(model.model, ultralytics.return_value)

    def test_yolo_writes_an_annotated_copy_of_the_image(self):
        from src.infrastructure.ml.yolo import YoloModel

        yolo_model = YoloModel.__new__(YoloModel)
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "out.png")
            yolo_model.write_image_with_detections(
                red_image((40, 40)), [{"label": "cat", "confidence": 0.9, "bbox": [20, 20, 10, 10]}], out
            )
            self.assertTrue(os.path.getsize(out) > 0)

    def test_clip_loads_on_cuda_when_available(self):
        from src.infrastructure.ml import clip as clip_module

        with mock.patch("torch.cuda.is_available", return_value=True), \
                mock.patch.object(clip_module.clip, "load", return_value=("model", "pre")) as load:
            model = clip_module.ClipModel("ViT-B/32")
        load.assert_called_once_with("ViT-B/32", device="cuda")
        self.assertEqual((model.device, model.model, model.preprocess), ("cuda", "model", "pre"))

    def test_get_clip_model_loads_each_variant_once(self):
        from src.infrastructure.ml import clip as clip_module

        clip_module.get_clip_model.cache_clear()
        self.addCleanup(clip_module.get_clip_model.cache_clear)
        with mock.patch.object(clip_module, "ClipModel") as cls:
            first = clip_module.get_clip_model("ViT-B/32")
            again = clip_module.get_clip_model("ViT-B/32")
            clip_module.get_clip_model("ViT-L/14")
        self.assertIs(first, again)
        self.assertEqual(cls.call_count, 2)


class LazyExportsTests(unittest.TestCase):
    def test_package_level_exports_resolve_lazily_and_unknown_names_raise(self):
        import importlib

        expected = {
            "src.infrastructure.ml": ["BlipModel", "ClipModel", "YoloModel", "ModelInterface"],
            "src.consumer.processing": ["ImageProcessorConsumer", "FileObservationConsumer", "start_pipeline_worker"],
            "src.consumer.ingestion": ["ImageEventHandler", "WorkspaceWatcher", "start_file_watcher"],
            "src.consumer.events": ["EventConsumer"],
        }
        for module_name, names in expected.items():
            module = importlib.import_module(module_name)
            for name in names:
                with self.subTest(module=module_name, name=name):
                    self.assertIsNotNone(getattr(module, name))
            with self.subTest(module=module_name, name="missing"):
                with self.assertRaises(AttributeError):
                    getattr(module, "definitely_not_exported")


class DefaultDeviceTests(unittest.TestCase):
    def test_cuda_when_available_cpu_only_without_a_gpu(self):
        from src.infrastructure.ml.gpu import default_device

        with mock.patch("torch.cuda.is_available", return_value=True):
            self.assertEqual(default_device(), "cuda")
        with mock.patch("torch.cuda.is_available", return_value=False):
            self.assertEqual(default_device(), "cpu")


class ClassificationUsesTheGpuTests(unittest.TestCase):
    def _executor(self, device):
        from src.services.executors.builtin import ClassificationExecutor

        stage = ClassificationExecutor()
        stage._device = device
        return stage

    def test_model_is_moved_to_the_device_when_loaded(self):
        import torchvision.models as tvm

        log = []

        class FakeNet:
            def eval(self):
                return self

            def to(self, device):
                log.append(device)
                return self

        weights = SimpleNamespace(
            DEFAULT=SimpleNamespace(transforms=lambda: "preprocess", meta={"categories": ["a", "b"]})
        )
        stage = self._executor("cuda")
        with mock.patch.object(tvm, "efficientnet_b0", lambda weights: FakeNet()), \
                mock.patch.object(tvm, "EfficientNet_B0_Weights", weights):
            model, preprocess, categories = stage._load("efficientnet_b0")
            stage._load("efficientnet_b0")  # cached — must not move/build again

        self.assertEqual(log, ["cuda"])
        self.assertEqual((preprocess, categories), ("preprocess", ["a", "b"]))

    def test_input_batch_is_sent_to_the_model_device(self):
        import torch

        seen = {}

        class Net:
            def __call__(self, batch):
                seen["device"] = batch.device.type
                return torch.tensor([[0.0, 2.0]])

        stage = self._executor("cpu")
        stage._loaded["efficientnet_b0"] = (Net(), lambda image: torch.zeros(3, 4, 4), ["a", "b"])
        out = stage.run({"image": red_image()}, {"top_k": 1})
        self.assertEqual(seen["device"], "cpu")
        self.assertEqual(out["labels"][0]["label"], "b")

    def test_device_is_resolved_lazily_from_default_device(self):
        from src.services.executors.builtin import ClassificationExecutor

        with mock.patch("src.infrastructure.ml.gpu.default_device", return_value="cuda") as dd:
            stage = ClassificationExecutor()
            self.assertEqual((stage.device, stage.device), ("cuda", "cuda"))
        dd.assert_called_once()


class Dinov2UsesTheGpuTests(unittest.TestCase):
    def test_inputs_go_to_the_device_and_the_vector_comes_back_as_numpy(self):
        import torch

        from src.infrastructure.ml.dinov2 import Dinov2Model

        sent = {}

        class Inputs(dict):
            def to(self, device):
                sent["device"] = device
                return self

        dino = Dinov2Model.__new__(Dinov2Model)
        dino.device, dino.logger = "cpu", mock.Mock()
        dino.processor = lambda images, return_tensors: Inputs(pixel_values=torch.zeros(1))
        dino.model = lambda **kw: SimpleNamespace(pooler_output=torch.ones(1, 768))
        vec = dino.embed(red_image())
        self.assertEqual(sent["device"], "cpu")
        self.assertEqual(vec.shape, (768,))
        self.assertIsInstance(vec, np.ndarray)

    def test_text_embedding_is_not_supported(self):
        from src.infrastructure.ml.dinov2 import Dinov2Model

        with self.assertRaises(NotImplementedError):
            Dinov2Model.__new__(Dinov2Model).embed_text("x")


class ScrfdProviderGuardTests(unittest.TestCase):
    """A GPU machine with only the CPU onnxruntime must not silently run on the CPU."""

    def _build(self, providers, cuda):
        import onnxruntime

        fake_app = mock.MagicMock()
        with mock.patch.object(onnxruntime, "get_available_providers", return_value=providers), \
                mock.patch("src.infrastructure.ml.face_detectors._cuda_available", return_value=cuda), \
                mock.patch("insightface.app.FaceAnalysis", fake_app):
            ScrfdFaceDetector()
        return fake_app

    def test_gpu_present_but_cpu_only_onnxruntime_fails_permanently(self):
        from src.errors.executors import PermanentNodeError

        with self.assertRaises(PermanentNodeError) as cm:
            self._build(["CPUExecutionProvider"], cuda=True)
        self.assertIn("onnxruntime-gpu", str(cm.exception))

    def test_cuda_provider_is_preferred_when_available(self):
        app = self._build(["CUDAExecutionProvider", "CPUExecutionProvider"], cuda=True)
        self.assertEqual(
            app.call_args.kwargs["providers"], ["CUDAExecutionProvider", "CPUExecutionProvider"]
        )

    def test_a_machine_with_no_gpu_still_runs_on_the_cpu(self):
        app = self._build(["CPUExecutionProvider"], cuda=False)
        self.assertEqual(app.call_args.kwargs["providers"], ["CPUExecutionProvider"])


class BlipUsesTheGpuTests(unittest.TestCase):
    def test_describe_moves_blip_to_the_gpu_and_sends_inputs_there_in_its_dtype(self):
        from src.infrastructure.ml import blip as blip_module, gpu

        log, sent = [], {}
        inputs = _Inputs()
        inputs.to = lambda device, dtype=None: sent.update(device=device, dtype=dtype) or inputs

        blip = blip_module.BlipModel.__new__(blip_module.BlipModel)
        blip.device, blip.dtype, blip.logger = "cuda", "fp16-marker", mock.Mock()
        blip.model = SimpleNamespace(to=_Recorder("blip", log).to, generate=lambda **kw: [[1, 2]])
        blip.processor = mock.MagicMock()
        blip.processor.return_value = inputs
        blip.processor.decode.return_value = "a cat"

        with mock.patch.object(gpu, "release_gpu_memory"), \
                mock.patch.object(blip_module, "residency", gpu.GpuResidency()):
            self.assertEqual(blip.describe(red_image()), "a cat")

        self.assertEqual(log, [("blip", "cuda")])
        self.assertEqual(sent, {"device": "cuda", "dtype": "fp16-marker"})


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
        blip.device, blip.dtype, blip.model = "cpu", None, mock.Mock()
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
