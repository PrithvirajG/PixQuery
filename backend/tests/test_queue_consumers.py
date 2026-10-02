"""on_message behaviour of the two work-queue consumers.

Both consumers' __init__ open a real Mongo connection, so instances are
built with __new__ and given only the attributes on_message reads.
"""
import asyncio
import contextlib
import json
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest import mock

from src.consumer.processing.file_observation_consumer import FileObservationConsumer
from src.consumer.processing.image_task_consumer import ImageProcessorConsumer
from src.errors.files import FileNotStableError
from src.logging_config import get_logger, get_request_id


class FakeMessage:
    def __init__(self, body, correlation_id="trace-1"):
        self.body = body.encode()
        self.correlation_id = correlation_id
        self.process_kwargs = None

    def process(self, **kwargs):
        self.process_kwargs = kwargs

        @contextlib.asynccontextmanager
        async def ctx():
            yield

        return ctx()


class FakeJobs:
    def __init__(self, job=None):
        self.job = job

    def get(self, job_id):
        return self.job


class RecordingPipeline:
    def __init__(self, error=None):
        self.calls = []
        self.error = error

    def run_job(self, job_id):
        self.calls.append((job_id, get_request_id()))
        if self.error:
            raise self.error


def image_consumer(pipeline, job=None):
    c = ImageProcessorConsumer.__new__(ImageProcessorConsumer)
    c.logger = get_logger("tests.image_consumer")
    c.pipeline = pipeline
    c.jobs = FakeJobs(job)
    c.queue_name = "image_task"
    c.fatal = asyncio.Event()
    return c


class AcceleratorError(RuntimeError):
    """Same class name as torch.AcceleratorError, which the classifier matches on."""


class OutOfMemoryError(RuntimeError):
    """Same class name as torch.cuda.OutOfMemoryError."""


class ImageProcessorConsumerTests(unittest.TestCase):
    def test_runs_the_job_under_the_message_correlation_id(self):
        pipeline = RecordingPipeline()
        msg = FakeMessage("  job-1 \n", correlation_id="trace-9")
        asyncio.run(image_consumer(pipeline).on_message(msg))
        self.assertEqual(pipeline.calls, [("job-1", "trace-9")])
        self.assertEqual(msg.process_kwargs, {"requeue": False})

    def test_failed_job_still_queued_is_republished_after_backoff(self):
        when = datetime.now(timezone.utc) + timedelta(seconds=30)
        consumer = image_consumer(RecordingPipeline(RuntimeError("boom")), job={"status": "queued", "next_attempt_at": when})
        consumer._republish_after_backoff = mock.AsyncMock()

        async def go():
            await consumer.on_message(FakeMessage("job-1"))
            await asyncio.sleep(0)  # let the created task start

        asyncio.run(go())
        consumer._republish_after_backoff.assert_awaited_once_with("job-1", when)

    def test_permanently_failed_job_is_not_republished(self):
        consumer = image_consumer(RecordingPipeline(RuntimeError("boom")), job={"status": "failed"})
        consumer._republish_after_backoff = mock.AsyncMock()
        asyncio.run(consumer.on_message(FakeMessage("job-1")))
        consumer._republish_after_backoff.assert_not_called()

    def test_fatal_cuda_error_requeues_immediately_and_stops_the_worker(self):
        error = AcceleratorError("CUDA error: out of memory")
        consumer = image_consumer(RecordingPipeline(error), job={"status": "queued", "next_attempt_at": None})
        consumer._republish_after_backoff = mock.AsyncMock()
        with mock.patch("src.consumer.processing.image_task_consumer.residency") as residency:
            asyncio.run(consumer.on_message(FakeMessage("job-1")))
        consumer._republish_after_backoff.assert_awaited_once_with("job-1", None)
        self.assertTrue(consumer.fatal.is_set())
        residency.park_all.assert_not_called()  # a broken context can't be cleaned up in-process

    def test_fatal_cuda_error_on_a_permanently_failed_job_still_stops_without_requeue(self):
        consumer = image_consumer(RecordingPipeline(AcceleratorError("CUDA error: x")), job={"status": "failed"})
        consumer._republish_after_backoff = mock.AsyncMock()
        asyncio.run(consumer.on_message(FakeMessage("job-1")))
        consumer._republish_after_backoff.assert_not_called()
        self.assertTrue(consumer.fatal.is_set())

    def test_recoverable_oom_parks_models_and_retries_with_backoff(self):
        when = datetime.now(timezone.utc) + timedelta(seconds=30)
        consumer = image_consumer(
            RecordingPipeline(OutOfMemoryError("CUDA out of memory. Tried to allocate 20 MiB")),
            job={"status": "queued", "next_attempt_at": when},
        )
        consumer._republish_after_backoff = mock.AsyncMock()

        async def go():
            await consumer.on_message(FakeMessage("job-1"))
            await asyncio.sleep(0)

        with mock.patch("src.consumer.processing.image_task_consumer.residency") as residency:
            asyncio.run(go())
        residency.park_all.assert_called_once()
        consumer._republish_after_backoff.assert_awaited_once_with("job-1", when)
        self.assertFalse(consumer.fatal.is_set())

    def test_ordinary_failure_neither_parks_models_nor_stops_the_worker(self):
        consumer = image_consumer(RecordingPipeline(RuntimeError("boom")), job={"status": "failed"})
        with mock.patch("src.consumer.processing.image_task_consumer.residency") as residency:
            asyncio.run(consumer.on_message(FakeMessage("job-1")))
        residency.park_all.assert_not_called()
        self.assertFalse(consumer.fatal.is_set())

    def _republish(self, next_attempt_at):
        consumer = image_consumer(RecordingPipeline())
        published = []

        async def publish(message, routing_key):
            published.append((message.body, routing_key))

        consumer.channel = SimpleNamespace(default_exchange=SimpleNamespace(publish=publish))
        with mock.patch("src.consumer.processing.image_task_consumer.asyncio.sleep", mock.AsyncMock()) as sleep:
            asyncio.run(consumer._republish_after_backoff("job-1", next_attempt_at))
        return published, sleep

    def test_republish_in_the_past_does_not_wait(self):
        published, sleep = self._republish(datetime.now(timezone.utc) - timedelta(seconds=5))
        self.assertEqual(published, [(b"job-1", "image_task")])
        sleep.assert_not_called()

    def test_republish_waits_until_next_attempt(self):
        _, sleep = self._republish(datetime.now(timezone.utc) + timedelta(seconds=30))
        self.assertAlmostEqual(sleep.call_args[0][0], 30, delta=2)

    def test_republish_accepts_naive_utc_datetimes(self):
        naive = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=10)
        _, sleep = self._republish(naive)
        self.assertAlmostEqual(sleep.call_args[0][0], 10, delta=2)

    def test_republish_without_a_time_publishes_immediately(self):
        published, sleep = self._republish(None)
        self.assertEqual(len(published), 1)
        sleep.assert_not_called()


class FakeWorkspaces:
    def __init__(self, workspace=None):
        self.workspace = workspace

    def get(self, workspace_id):
        return self.workspace


class RecordingReconciler:
    def __init__(self, error=None, queued=("job-1",)):
        self.error = error
        self.queued = list(queued)
        self.calls = []

    async def observe_file(self, path, *, redispatch_failed=False):
        self.calls.append((path, redispatch_failed, get_request_id()))
        if self.error:
            raise self.error
        return self.queued


def file_observation_consumer(workspace=None):
    c = FileObservationConsumer.__new__(FileObservationConsumer)
    c.logger = get_logger("tests.file_observation_consumer")
    c.workspaces = FakeWorkspaces(workspace)
    c.assets = c.observations = c.jobs = c.pipelines = None
    c.image_task_publisher = None
    c.event_sink = None
    c.queue_name = "file_observations"
    return c


_WORKSPACE = {"_id": "ws-1", "workspace_path": "/w", "pipeline_ids": ["p1"], "extensions": [".jpg"]}


class FileObservationConsumerTests(unittest.TestCase):
    def _patched(self, workspace=_WORKSPACE, **reconciler_kwargs):
        reconciler = RecordingReconciler(**reconciler_kwargs)
        patcher = mock.patch(
            "src.consumer.processing.file_observation_consumer.ReconciliationService",
            return_value=reconciler,
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        return file_observation_consumer(workspace), reconciler

    def test_observes_the_file_under_the_message_correlation_id(self):
        consumer, reconciler = self._patched()
        msg = FakeMessage(
            json.dumps({"workspace_id": "ws-1", "path": "/w/a.jpg", "redispatch_failed": True}),
            correlation_id="trace-7",
        )
        asyncio.run(consumer.on_message(msg))
        self.assertEqual(reconciler.calls, [("/w/a.jpg", True, "trace-7")])

    def test_redispatch_failed_defaults_to_false(self):
        consumer, reconciler = self._patched()
        msg = FakeMessage(json.dumps({"workspace_id": "ws-1", "path": "/w/a.jpg"}))
        asyncio.run(consumer.on_message(msg))
        self.assertEqual(reconciler.calls[0][1], False)

    def test_unknown_workspace_is_dropped_without_building_a_reconciler(self):
        with mock.patch(
            "src.consumer.processing.file_observation_consumer.ReconciliationService"
        ) as rs:
            consumer = file_observation_consumer(workspace=None)
            msg = FakeMessage(json.dumps({"workspace_id": "ws-x", "path": "/w/a.jpg"}))
            asyncio.run(consumer.on_message(msg))
            rs.assert_not_called()

    def test_unstable_file_is_postponed_without_raising(self):
        consumer, _ = self._patched(error=FileNotStableError("still copying"))
        msg = FakeMessage(json.dumps({"workspace_id": "ws-1", "path": "/w/a.jpg"}))
        asyncio.run(consumer.on_message(msg))  # must not raise

    def test_other_errors_are_swallowed(self):
        consumer, _ = self._patched(error=RuntimeError("boom"))
        msg = FakeMessage(json.dumps({"workspace_id": "ws-1", "path": "/w/a.jpg"}))
        asyncio.run(consumer.on_message(msg))  # must not raise


if __name__ == "__main__":
    unittest.main()
