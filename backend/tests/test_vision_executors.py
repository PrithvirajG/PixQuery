"""Smoke tests for the OpenCV/torchvision executors that back the previously
unimplemented face_detection and classification nodes.

Face detection is fast and downloads nothing (Haar cascade ships with cv2), so we
run it. Classification pulls model weights on first use, so we only assert wiring.
"""
import unittest

from PIL import Image

from src.services.executors import get_executor
from src.services.executors.builtin import FaceDetectionExecutor


class FaceDetectionExecutorTests(unittest.TestCase):
    def test_registered(self):
        self.assertIsInstance(get_executor("face_detection"), FaceDetectionExecutor)

    def test_runs_and_returns_detections(self):
        # A blank image has no faces — the point is it runs end-to-end and emits
        # under "detections" (same key/shape as object detection) so the existing
        # overlay renders faces with no frontend change.
        out = FaceDetectionExecutor().run({"image": Image.new("RGB", (80, 80), "white")}, {})
        self.assertIn("detections", out)
        self.assertIsInstance(out["detections"], list)
        self.assertEqual(out["detections"], [])


class ClassificationExecutorTests(unittest.TestCase):
    def test_registered(self):
        # Construction is lazy (no weights downloaded until run), so this is cheap.
        self.assertEqual(get_executor("classification").node_type, "classification")


if __name__ == "__main__":
    unittest.main()
