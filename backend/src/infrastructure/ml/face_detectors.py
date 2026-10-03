"""Face detector wrappers behind one tiny contract.

Each wrapper loads its weights in ``__init__`` and exposes
``detect(image, threshold) -> list[FaceBox]`` — corner-based ``(x1, y1, x2, y2)``
absolute pixels plus a confidence score. The executor (``FaceDetectionExecutor``)
owns converting that into the pipeline's shared ``detections`` shape, so every
backend here stays a thin adapter over its library. Heavy imports are deferred to
``__init__`` so importing this module costs nothing until a model is chosen.
"""
from __future__ import annotations

import os
import urllib.request
from typing import NamedTuple

import numpy as np
from PIL import Image

from src.config import MODEL_CACHE_DIR
from src.errors.executors import PermanentNodeError
from src.logging_config import get_logger

logger = get_logger(__name__)


class FaceBox(NamedTuple):
    x1: float
    y1: float
    x2: float
    y2: float
    score: float


def _bgr(image: Image.Image) -> np.ndarray:
    return np.ascontiguousarray(np.array(image.convert("RGB"))[:, :, ::-1])


def _cuda_available() -> bool:
    try:
        import torch

        return torch.cuda.is_available()
    except ImportError:
        return False


class YuNetFaceDetector:
    """OpenCV's built-in YuNet (``cv2.FaceDetectorYN``) — tiny and CPU-fast.

    OpenCV ships the runtime but not the ~230 KB ONNX weights, so they're
    downloaded once into ``MODEL_CACHE_DIR``.
    """

    WEIGHTS_URL = (
        "https://github.com/opencv/opencv_zoo/raw/main/models/"
        "face_detection_yunet/face_detection_yunet_2023mar.onnx"
    )
    WEIGHTS_FILE = "face_detection_yunet_2023mar.onnx"

    def __init__(self) -> None:
        import cv2

        path = os.path.join(MODEL_CACHE_DIR, self.WEIGHTS_FILE)
        if not os.path.exists(path):
            os.makedirs(MODEL_CACHE_DIR, exist_ok=True)
            logger.info("Downloading YuNet weights to %s", path)
            tmp = path + ".part"
            urllib.request.urlretrieve(self.WEIGHTS_URL, tmp)
            os.replace(tmp, path)
        # Input size is reset per image in detect(); (320, 320) is a placeholder.
        self._detector = cv2.FaceDetectorYN.create(path, "", (320, 320), 0.5, 0.3, 5000)
        logger.info("YuNet face detector loaded from %s", path)

    def detect(self, image: Image.Image, threshold: float) -> list[FaceBox]:
        bgr = _bgr(image)
        height, width = bgr.shape[:2]
        self._detector.setInputSize((width, height))
        self._detector.setScoreThreshold(float(threshold))
        _, faces = self._detector.detect(bgr)
        if faces is None:
            return []
        # Row layout: x, y, w, h, 5 landmark pairs, score.
        return [
            FaceBox(float(f[0]), float(f[1]), float(f[0] + f[2]), float(f[1] + f[3]), float(f[14]))
            for f in faces
        ]


class ScrfdFaceDetector:
    """InsightFace's SCRFD-10GF (the detector from the ``buffalo_l`` model pack).

    InsightFace downloads the pack into ``~/.insightface`` on first use; only its
    detection model is loaded (``allowed_modules=["detection"]``).
    """

    PACK = "buffalo_l"

    def __init__(self) -> None:
        from insightface.app import FaceAnalysis

        providers = ["CPUExecutionProvider"]
        try:
            import onnxruntime

            if "CUDAExecutionProvider" in onnxruntime.get_available_providers():
                providers.insert(0, "CUDAExecutionProvider")
            elif _cuda_available():
                # A GPU exists but this is the CPU-only onnxruntime build: running
                # anyway would silently put the model on the CPU. Fail loudly instead.
                raise PermanentNodeError(
                    "SCRFD needs the GPU build of ONNX Runtime but only the CPU build is "
                    "installed (providers: %s). Install onnxruntime-gpu in place of "
                    "onnxruntime, or pick another face-detection model."
                    % onnxruntime.get_available_providers()
                )
        except ImportError:
            pass
        self._app = FaceAnalysis(name=self.PACK, allowed_modules=["detection"], providers=providers)
        # det_thresh here is only a floor; detect() filters by the node's threshold.
        self._app.prepare(ctx_id=0, det_size=(640, 640), det_thresh=0.05)
        logger.info("SCRFD face detector loaded (%s, providers=%s)", self.PACK, providers)

    def detect(self, image: Image.Image, threshold: float) -> list[FaceBox]:
        faces = self._app.get(_bgr(image))
        return [
            FaceBox(*(float(v) for v in face.bbox[:4]), float(face.det_score))
            for face in faces
            if float(face.det_score) >= threshold
        ]


class RetinaFaceDetector:
    """RetinaFace with a ResNet-50 backbone, via the ``batch-face`` package.

    Weights (~105 MB) download into torch's hub cache on first use. Runs on the
    GPU when CUDA is available.
    """

    def __init__(self) -> None:
        from batch_face import RetinaFace

        gpu_id = 0 if _cuda_available() else -1
        self._model = RetinaFace(gpu_id=gpu_id, network="resnet50")
        logger.info("RetinaFace-R50 face detector loaded (gpu_id=%d)", gpu_id)

    def detect(self, image: Image.Image, threshold: float) -> list[FaceBox]:
        faces = self._model(_bgr(image), threshold=float(threshold), cv=True, return_dict=True)
        return [FaceBox(*(float(v) for v in face["box"][:4]), float(face["score"])) for face in faces]
