"""Process entry points and consumer lifecycles: wiring, not behaviour.

Real Mongo / RabbitMQ / model weights are never touched — each external is replaced
by a recorder, so what's asserted is which pieces get built, connected, armed and
torn down (and, for the watcher, which pieces deliberately do NOT exist anymore).
"""
import asyncio
import contextlib
import io
import unittest
from types import SimpleNamespace
from unittest import mock

from src.consumer.ingestion import worker as watcher_worker
from src.consumer.processing import file_observation_consumer as foc
from src.consumer.processing import image_task_consumer as itc
from src.infrastructure.ml import gpu
from src.infrastructure.messaging import EventSink
from src.migrations import __main__ as migrations_cli


class Recorder:
    """Async-capable stand-in: records calls, optionally raises on connect."""

    def __init__(self, *args, fail_connect=False, **kwargs):
        self.args, self.kwargs, self.fail_connect = args, kwargs, fail_connect
        self.calls = []

    async def connect(self):
        self.calls.append("connect")
        if self.fail_connect:
            raise ConnectionError("broker down")

    async def close(self):
        self.calls.append("close")

    def emit(self, event):
        self.calls.append(("emit", event))

    def close_sync(self):
        self.calls.append("close")


class MigrationsCliTests(unittest.TestCase):
    def _run(self, argv, applied=("0001_a",), ran=()):
        migrations = [
            SimpleNamespace(id="0001_a", description="first"),
            SimpleNamespace(id="0002_b", description="second"),
        ]
        out = io.StringIO()
        with mock.patch("pymongo.MongoClient"), \
                mock.patch.object(migrations_cli, "configure_logging"), \
                mock.patch.object(migrations_cli, "MIGRATIONS", migrations), \
                mock.patch.object(migrations_cli, "applied_migration_ids", return_value=set(applied)), \
                mock.patch.object(migrations_cli, "run_migrations", return_value=list(ran)) as run, \
                contextlib.redirect_stdout(out):
            code = migrations_cli.main(argv)
        return code, out.getvalue(), run

    def test_status_lists_applied_and_pending_without_running_anything(self):
        code, out, run = self._run(["--status"])
        self.assertEqual(code, 0)
        self.assertIn("applied] 0001_a", out)
        self.assertIn("pending] 0002_b", out)
        run.assert_not_called()

    def test_default_runs_pending_migrations_and_reports_the_count(self):
        code, out, run = self._run([], ran=["0002_b"])
        self.assertEqual(code, 0)
        self.assertIn("Applied 1 migration(s).", out)
        run.assert_called_once()


class FileWatcherBootstrapTests(unittest.TestCase):
    """The watcher is a pure detector now: no jobs/pipelines repos, no event bus,
    no scan consumer."""

    def test_builds_only_the_detector_pieces_runs_the_loop_and_cleans_up(self):
        publisher = Recorder()
        watcher = mock.MagicMock()
        watcher.sync = mock.AsyncMock()
        watcher.reconcile_all = mock.AsyncMock()
        watcher_cls = mock.MagicMock(return_value=watcher)
        sleeps = []

        async def fake_sleep(seconds):
            sleeps.append(seconds)
            if len(sleeps) == 2:
                raise asyncio.CancelledError  # end the otherwise endless loop

        with mock.patch("pymongo.MongoClient"), \
                mock.patch.object(watcher_worker, "ensure_schema") as ensure, \
                mock.patch.object(watcher_worker, "WorkspaceDefinitionsRepository"), \
                mock.patch.object(watcher_worker, "ImageAssetsRepository"), \
                mock.patch.object(watcher_worker, "FileObservationsRepository"), \
                mock.patch.object(watcher_worker, "RabbitPublisher", return_value=publisher), \
                mock.patch.object(watcher_worker, "WorkspaceWatcher", watcher_cls), \
                mock.patch.object(watcher_worker.asyncio, "sleep", fake_sleep):
            with self.assertRaises(asyncio.CancelledError):
                asyncio.run(watcher_worker.start_file_watcher())

        ensure.assert_called_once()
        self.assertEqual(
            set(watcher_cls.call_args.kwargs),
            {"workspaces", "assets", "observations", "publisher", "loop"},
        )
        self.assertEqual(watcher.sync.await_count, 2)  # initial + one refresh
        watcher.reconcile_all.assert_awaited_once()
        watcher.stop_all.assert_called_once()
        self.assertEqual(publisher.calls, ["connect", "close"])


def _patched_consumer_env(module, **extra):
    """Patch every external the consumer constructors reach for."""
    stack = contextlib.ExitStack()
    stack.enter_context(mock.patch("pymongo.MongoClient"))
    stack.enter_context(mock.patch.object(module, "ensure_schema"))
    for name in (
        "WorkspaceDefinitionsRepository", "ImageAssetsRepository", "FileObservationsRepository",
        "ProcessingJobsRepository", "PipelineDefinitionsRepository", "PipelineRunsRepository",
        "ModelOutputsRepository", "PipelineNodesRepository",
    ):
        if hasattr(module, name):
            stack.enter_context(mock.patch.object(module, name))
    for name, value in extra.items():
        stack.enter_context(mock.patch.object(module, name, value))
    return stack


class FileObservationConsumerLifecycleTests(unittest.TestCase):
    def _consumer(self, bus_factory, events_enabled=True):
        stack = _patched_consumer_env(
            foc, RabbitPublisher=lambda: Recorder(), EventPublisher=bus_factory,
            EVENTS_ENABLED=events_enabled,
        )
        stack.enter_context(mock.patch.object(foc.RabbitConsumer, "connect", mock.AsyncMock()))
        stack.enter_context(mock.patch.object(foc.RabbitConsumer, "close", mock.AsyncMock()))
        self.addCleanup(stack.close)
        return foc.FileObservationConsumer()

    def test_init_listens_on_the_file_observations_queue_with_its_own_publisher(self):
        consumer = self._consumer(lambda: Recorder())
        self.assertEqual(consumer.queue_name, foc.FILE_OBSERVATION_QUEUE)
        self.assertIsNone(consumer.event_bus)
        self.assertIsInstance(consumer.event_sink, EventSink)

    def test_connect_arms_the_event_sink_when_events_are_enabled(self):
        bus = Recorder()
        consumer = self._consumer(lambda: bus)
        asyncio.run(consumer.connect())
        self.assertIs(consumer.event_bus, bus)
        self.assertEqual(bus.calls, ["connect"])
        self.assertEqual(consumer.image_task_publisher.calls, ["connect"])
        consumer.event_sink.emit("hello")
        self.assertIn(("emit", "hello"), bus.calls)

    def test_connect_skips_the_event_bus_when_events_are_disabled(self):
        consumer = self._consumer(lambda: self.fail("must not build a bus"), events_enabled=False)
        asyncio.run(consumer.connect())
        self.assertIsNone(consumer.event_bus)
        self.assertEqual(consumer.image_task_publisher.calls, ["connect"])

    def test_a_broken_event_bus_degrades_instead_of_failing_the_worker(self):
        consumer = self._consumer(lambda: Recorder(fail_connect=True))
        asyncio.run(consumer.connect())
        self.assertIsNone(consumer.event_bus)

    def test_close_closes_the_publisher_and_the_event_bus(self):
        bus = Recorder()
        consumer = self._consumer(lambda: bus)

        async def go():
            await consumer.connect()
            await consumer.close()

        asyncio.run(go())
        self.assertEqual(consumer.image_task_publisher.calls, ["connect", "close"])
        self.assertEqual(bus.calls, ["connect", "close"])


class ImageProcessorConsumerLifecycleTests(unittest.TestCase):
    def _consumer(self, bus_factory, events_enabled=True):
        store = Recorder()
        store.close = store.close_sync  # WeaviateEmbeddingStore.close is synchronous
        stack = _patched_consumer_env(
            itc, WeaviateEmbeddingStore=lambda: store, PipelineExecutionService=mock.MagicMock(),
            EventPublisher=bus_factory, EVENTS_ENABLED=events_enabled,
        )
        stack.enter_context(mock.patch.object(itc.RabbitConsumer, "connect", mock.AsyncMock()))
        stack.enter_context(mock.patch.object(itc.RabbitConsumer, "close", mock.AsyncMock()))
        self.addCleanup(stack.close)
        consumer = itc.ImageProcessorConsumer()
        consumer._store = store
        return consumer

    def test_init_builds_the_pipeline_service_and_an_unset_fatal_flag(self):
        consumer = self._consumer(lambda: Recorder())
        self.assertFalse(consumer.fatal.is_set())
        self.assertIsNone(consumer.event_bus)

    def test_connect_arms_events_and_a_failing_bus_only_degrades(self):
        bus = Recorder()
        good = self._consumer(lambda: bus)
        asyncio.run(good.connect())
        self.assertIs(good.event_bus, bus)

        bad = self._consumer(lambda: Recorder(fail_connect=True))
        asyncio.run(bad.connect())
        self.assertIsNone(bad.event_bus)

        off = self._consumer(lambda: self.fail("no bus when disabled"), events_enabled=False)
        asyncio.run(off.connect())
        self.assertIsNone(off.event_bus)

    def test_close_closes_the_bus_and_the_embedding_store(self):
        bus = Recorder()
        consumer = self._consumer(lambda: bus)

        async def go():
            await consumer.connect()
            await consumer.close()

        asyncio.run(go())
        self.assertEqual(bus.calls, ["connect", "close"])
        self.assertEqual(consumer._store.calls, ["close"])


class ReleaseGpuMemoryTests(unittest.TestCase):
    def test_empties_the_cuda_cache_when_a_gpu_is_present(self):
        with mock.patch("torch.cuda.is_available", return_value=True), \
                mock.patch("torch.cuda.empty_cache") as empty:
            gpu.release_gpu_memory()
        empty.assert_called_once()

    def test_does_nothing_without_a_gpu(self):
        with mock.patch("torch.cuda.is_available", return_value=False), \
                mock.patch("torch.cuda.empty_cache") as empty:
            gpu.release_gpu_memory()
        empty.assert_not_called()

    def test_a_failing_cache_release_is_logged_not_raised(self):
        # On a poisoned CUDA context even empty_cache() can throw; that must never
        # mask the real error being handled.
        with mock.patch("torch.cuda.is_available", return_value=True), \
                mock.patch("torch.cuda.empty_cache", side_effect=RuntimeError("CUDA error")):
            gpu.release_gpu_memory()


if __name__ == "__main__":
    unittest.main()
