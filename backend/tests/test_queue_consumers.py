"""on_message behaviour of the two work-queue consumers.

ImageProcessorConsumer.__init__ opens a real Mongo connection, so instances are
built with __new__ and given only the attributes on_message reads.
"""
import asyncio
import contextlib
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest import mock

from src.consumer.ingestion.scan_command_consumer import ScanCommandConsumer
from src.consumer.processing.image_task_consumer import ImageProcessorConsumer
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
    return c


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


class ScanCommandConsumerTests(unittest.TestCase):
    def test_manual_scan_redispatches_failed_jobs_under_the_request_id(self):
        seen = []

        class Watcher:
            async def reconcile_workspace(self, workspace_id, *, redispatch_failed=False):
                seen.append((workspace_id, redispatch_failed, get_request_id()))

        consumer = ScanCommandConsumer(Watcher(), queue_name="scan", rabbitmq_url="amqp://x")
        asyncio.run(consumer.on_message(FakeMessage(" ws-1 ", correlation_id="trace-scan")))
        self.assertEqual(seen, [("ws-1", True, "trace-scan")])


if __name__ == "__main__":
    unittest.main()
