"""CUDA error classification and the one-heavy-model-on-the-GPU residency manager."""
import threading
import unittest
from unittest import mock

from src.infrastructure.ml import gpu
from src.infrastructure.ml.gpu import GpuResidency, is_cuda_fatal, is_cuda_oom


class AcceleratorError(RuntimeError):
    """Same class name as torch.AcceleratorError — the classifier matches on name."""


class OutOfMemoryError(RuntimeError):
    """Same class name as torch.cuda.OutOfMemoryError."""


class ClassifierTests(unittest.TestCase):
    def test_accelerator_error_is_fatal_even_when_it_says_out_of_memory(self):
        # The exact error from the production log.
        exc = AcceleratorError("CUDA error: out of memory")
        self.assertTrue(is_cuda_fatal(exc))
        self.assertFalse(is_cuda_oom(exc))

    def test_plain_cuda_error_message_is_fatal(self):
        self.assertTrue(is_cuda_fatal(RuntimeError("CUDA error: device-side assert triggered")))

    def test_clean_allocation_failure_is_a_recoverable_oom(self):
        exc = OutOfMemoryError("CUDA out of memory. Tried to allocate 20.00 MiB")
        self.assertTrue(is_cuda_oom(exc))
        self.assertFalse(is_cuda_fatal(exc))

    def test_unrelated_errors_are_neither(self):
        exc = ValueError("bad config")
        self.assertFalse(is_cuda_fatal(exc))
        self.assertFalse(is_cuda_oom(exc))

    def test_wrapped_cuda_error_is_found_through_the_cause_chain(self):
        try:
            try:
                raise AcceleratorError("CUDA error: out of memory")
            except AcceleratorError as inner:
                raise RuntimeError("node failed") from inner
        except RuntimeError as outer:
            self.assertTrue(is_cuda_fatal(outer))


class FakeModule:
    def __init__(self, name, log, fail_on=None):
        self.name, self.log, self.fail_on = name, log, fail_on

    def to(self, device):
        self.log.append((self.name, device))
        if device == self.fail_on:
            raise OutOfMemoryError("CUDA out of memory")
        return self


class ResidencyTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(gpu, "release_gpu_memory")
        self.release = patcher.start()
        self.addCleanup(patcher.stop)
        self.log = []
        self.res = GpuResidency()
        self.a = FakeModule("a", self.log)
        self.b = FakeModule("b", self.log)

    def test_first_use_moves_the_model_onto_the_gpu(self):
        with self.res.use("a", self.a, "cuda"):
            self.assertEqual(self.res.resident_key, "a")
        self.assertEqual(self.log, [("a", "cuda")])

    def test_reusing_the_resident_model_does_not_move_it_again(self):
        with self.res.use("a", self.a, "cuda"):
            pass
        with self.res.use("a", self.a, "cuda"):
            pass
        self.assertEqual(self.log, [("a", "cuda")])

    def test_switching_models_parks_the_previous_one_first(self):
        with self.res.use("a", self.a, "cuda"):
            pass
        with self.res.use("b", self.b, "cuda"):
            self.assertEqual(self.res.resident_key, "b")
        self.assertEqual(self.log, [("a", "cuda"), ("a", "cpu"), ("b", "cuda")])
        self.release.assert_called()

    def test_a_cpu_device_is_a_no_op(self):
        with self.res.use("a", self.a, "cpu"):
            pass
        self.assertEqual(self.log, [])
        self.assertIsNone(self.res.resident_key)

    def test_a_failed_move_parks_the_half_moved_model_and_leaves_nothing_resident(self):
        broken = FakeModule("a", self.log, fail_on="cuda")
        with self.assertRaises(OutOfMemoryError):
            with self.res.use("a", broken, "cuda"):
                self.fail("body must not run")
        self.assertEqual(self.log, [("a", "cuda"), ("a", "cpu")])
        self.assertIsNone(self.res.resident_key)

    def test_park_all_empties_the_gpu(self):
        with self.res.use("a", self.a, "cuda"):
            pass
        self.res.park_all()
        self.assertIsNone(self.res.resident_key)
        self.assertEqual(self.log[-1], ("a", "cpu"))

    def test_park_all_with_nothing_resident_is_harmless(self):
        self.res.park_all()
        self.assertEqual(self.log, [])

    def test_inference_is_serialized_so_a_model_is_never_parked_mid_run(self):
        entered, release_a = threading.Event(), threading.Event()
        order = []

        def run_a():
            with self.res.use("a", self.a, "cuda"):
                order.append("a-start")
                entered.set()
                release_a.wait(5)
                order.append("a-end")

        def run_b():
            entered.wait(5)
            with self.res.use("b", self.b, "cuda"):
                order.append("b-start")

        ta, tb = threading.Thread(target=run_a), threading.Thread(target=run_b)
        ta.start()
        tb.start()
        entered.wait(5)
        release_a.set()
        ta.join(5)
        tb.join(5)
        self.assertEqual(order, ["a-start", "a-end", "b-start"])


if __name__ == "__main__":
    unittest.main()
