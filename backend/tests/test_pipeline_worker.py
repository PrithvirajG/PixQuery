"""start_pipeline_worker: runs until a fatal CUDA error, then exits non-zero."""
import asyncio
import unittest
from unittest import mock

from src.consumer.processing import worker


class FakeConsumer:
    def __init__(self):
        self.fatal = asyncio.Event()
        self.consuming = self.closed = False

    async def connect(self):
        pass

    async def start_consuming(self):
        self.consuming = True

    async def close(self):
        self.closed = True


class PipelineWorkerTests(unittest.TestCase):
    def test_a_fatal_cuda_error_closes_both_consumers_and_exits_with_code_3(self):
        images, files = FakeConsumer(), FakeConsumer()

        async def go():
            asyncio.get_running_loop().call_later(0.01, images.fatal.set)
            await worker.start_pipeline_worker()

        with mock.patch.object(worker, "ImageProcessorConsumer", lambda: images), \
                mock.patch.object(worker, "FileObservationConsumer", lambda: files):
            with self.assertRaises(SystemExit) as cm:
                asyncio.run(go())

        self.assertEqual(cm.exception.code, 3)
        self.assertTrue(images.consuming and files.consuming)
        self.assertTrue(images.closed and files.closed)


if __name__ == "__main__":
    unittest.main()
