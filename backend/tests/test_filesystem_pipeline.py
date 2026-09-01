import asyncio
import tempfile
import unittest
from pathlib import Path

from src.infrastructure.messaging import EventSink
from src.services.reconciliation_service import ReconciliationService
from src.utils.files import wait_for_stable_file
from tests.repo_factory import new_repos


class FakePublisher:
    def __init__(self):
        self.messages = []

    async def publish(self, message):
        self.messages.append(message)


def _reconciler(r, **overrides):
    kwargs = dict(
        assets=r.assets, observations=r.observations, jobs=r.jobs, pipelines=r.pipelines,
    )
    kwargs.update(overrides)
    return ReconciliationService(**kwargs)


class FilesystemPipelineTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.r = new_repos()
        self.publisher = FakePublisher()
        self.reconciler = _reconciler(
            self.r,
            publisher=self.publisher,
            workspace_path=str(self.root),
            workspace_id="test-root",
            pipeline_id="test-pipeline",
            pipeline_version="v1",
            stable_interval_seconds=0.01,
            stable_timeout_seconds=1,
        )

    async def asyncTearDown(self):
        self.tmp.cleanup()

    async def test_stable_file_detection_waits_for_partially_copied_file(self):
        image = self.root / "partial.jpg"
        image.write_bytes(b"first")

        async def finish_copy():
            await asyncio.sleep(0.015)
            image.write_bytes(b"first-second")

        writer = asyncio.create_task(finish_copy())
        await wait_for_stable_file(
            image,
            checks_required=2,
            interval_seconds=0.01,
            timeout_seconds=1,
        )
        await writer
        self.assertEqual(image.read_bytes(), b"first-second")

    async def test_same_image_copied_twice_creates_one_asset_and_two_observations(self):
        (self.root / "a.jpg").write_bytes(b"same-image")
        (self.root / "nested").mkdir()
        (self.root / "nested" / "b.jpg").write_bytes(b"same-image")

        await self.reconciler.reconcile()

        self.assertEqual(len(self.r.assets.collection.docs), 1)
        self.assertEqual(len(self.r.observations.collection.docs), 2)
        self.assertEqual(len(self.r.jobs.collection.docs), 1)

    async def test_rename_keeps_same_asset_by_hash(self):
        original = self.root / "old.jpg"
        original.write_bytes(b"rename-me")
        await self.reconciler.reconcile()
        asset_id = self.r.assets.collection.docs[0]["_id"]

        original.rename(self.root / "new.jpg")
        await self.reconciler.reconcile()

        self.assertEqual(len(self.r.assets.collection.docs), 1)
        self.assertEqual(self.r.assets.collection.docs[0]["_id"], asset_id)
        statuses = {obs["relative_path"]: obs["status"] for obs in self.r.observations.collection.docs}
        self.assertEqual(statuses["old.jpg"], "missing")
        self.assertEqual(statuses["new.jpg"], "active")

    async def test_delete_marks_observation_missing_and_hides_asset(self):
        image = self.root / "delete.jpg"
        image.write_bytes(b"delete-me")
        await self.reconciler.reconcile()

        image.unlink()
        await self.reconciler.reconcile()

        self.assertEqual(self.r.observations.collection.docs[0]["status"], "missing")
        self.assertFalse(self.r.assets.collection.docs[0]["active"])
        self.assertEqual(self.r.assets.list_all(active_only=True), [])

    async def test_duplicate_observations_do_not_create_duplicate_processing_jobs(self):
        image = self.root / "one.jpg"
        image.write_bytes(b"queue-once")

        await self.reconciler.observe_file(image)
        await self.reconciler.observe_file(image)

        self.assertEqual(len(self.r.jobs.collection.docs), 1)
        self.assertEqual(len(self.publisher.messages), 1)

    async def test_completed_pipeline_version_is_not_rerun_until_version_changes(self):
        image = self.root / "versioned.jpg"
        image.write_bytes(b"versioned")
        await self.reconciler.observe_file(image)

        job = self.r.jobs.collection.docs[0]
        self.r.jobs.collection.docs[0]["status"] = "completed"
        await self.reconciler.observe_file(image)
        self.assertEqual(len(self.r.jobs.collection.docs), 1)

        next_reconciler = _reconciler(
            self.r,
            publisher=self.publisher,
            workspace_path=str(self.root),
            workspace_id="test-root",
            pipeline_id="test-pipeline",
            pipeline_version="v2",
            stable_interval_seconds=0.01,
            stable_timeout_seconds=1,
        )
        await next_reconciler.observe_file(image)
        self.assertEqual(len(self.r.jobs.collection.docs), 2)
        self.assertEqual(self.r.jobs.collection.docs[0]["_id"], job["_id"])

    async def test_automatic_observe_leaves_a_failed_job_failed(self):
        # The live filesystem watcher and the periodic full-workspace reconcile
        # both call observe_file with no override — a deterministic failure
        # (e.g. a bug that fails identically every time) must not get an
        # unattended, unlimited supply of fresh retry budgets.
        image = self.root / "flaky.jpg"
        image.write_bytes(b"flaky")
        await self.reconciler.observe_file(image)
        self.r.jobs.collection.docs[0]["status"] = "failed"

        await self.reconciler.observe_file(image)

        self.assertEqual(self.r.jobs.collection.docs[0]["status"], "failed")
        self.assertEqual(len(self.publisher.messages), 1)  # only the original dispatch

    async def test_manual_rescan_redispatches_a_failed_job(self):
        # A human explicitly hitting the workspace's "Scan" button opts in to
        # retrying jobs that previously failed.
        image = self.root / "flaky.jpg"
        image.write_bytes(b"flaky")
        await self.reconciler.observe_file(image)
        self.r.jobs.collection.docs[0]["status"] = "failed"

        await self.reconciler.observe_file(image, redispatch_failed=True)

        self.assertEqual(self.r.jobs.collection.docs[0]["status"], "queued")
        self.assertEqual(len(self.publisher.messages), 2)

    async def test_no_pipelines_assigned_ingests_files_without_creating_jobs(self):
        image = self.root / "orphan.jpg"
        image.write_bytes(b"no-pipeline")
        reconciler = _reconciler(
            self.r,
            publisher=self.publisher,
            workspace_path=str(self.root),
            workspace_id="test-root",
            stable_interval_seconds=0.01,
            stable_timeout_seconds=1,
        )

        await reconciler.reconcile()

        self.assertEqual(len(self.r.assets.collection.docs), 1)
        self.assertEqual(len(self.r.observations.collection.docs), 1)
        self.assertEqual(len(self.r.jobs.collection.docs), 0)
        self.assertEqual(self.publisher.messages, [])


class ReconciliationEventTests(unittest.IsolatedAsyncioTestCase):
    """A newly-discovered image's job announces itself as 'queued' immediately —
    previously an implicit side effect of the god-repository's own
    ensure_processing_job/requeue_job, now explicit emission by the service."""

    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.r = new_repos()
        self.publisher = FakePublisher()
        self.events = []
        sink = EventSink()
        sink.set(self.events.append)
        self.reconciler = _reconciler(
            self.r,
            publisher=self.publisher,
            workspace_path=str(self.root),
            workspace_id="test-root",
            pipeline_id="test-pipeline",
            pipeline_version="v1",
            stable_interval_seconds=0.01,
            stable_timeout_seconds=1,
            event_sink=sink,
        )

    async def asyncTearDown(self):
        self.tmp.cleanup()

    def _queued_events(self):
        return [e for e in self.events if e.data.get("state") == "queued"]

    async def test_newly_discovered_image_announces_queued(self):
        image = self.root / "new.jpg"
        image.write_bytes(b"new-image")

        await self.reconciler.observe_file(image)

        queued = self._queued_events()
        self.assertEqual(len(queued), 1)
        self.assertEqual(queued[0].pipeline_id, "test-pipeline")
        self.assertIsNotNone(queued[0].asset_id)

    async def test_rescanning_an_untouched_job_emits_nothing(self):
        image = self.root / "seen.jpg"
        image.write_bytes(b"seen-image")
        await self.reconciler.observe_file(image)
        self.events.clear()

        await self.reconciler.observe_file(image)  # no change: same job, not failed

        self.assertEqual(self._queued_events(), [])

    async def test_manual_redispatch_of_a_failed_job_announces_queued_again(self):
        image = self.root / "flaky.jpg"
        image.write_bytes(b"flaky")
        await self.reconciler.observe_file(image)
        self.r.jobs.collection.docs[0]["status"] = "failed"
        self.events.clear()

        await self.reconciler.observe_file(image, redispatch_failed=True)

        self.assertEqual(len(self._queued_events()), 1)

    async def test_automatic_rescan_of_a_failed_job_emits_nothing(self):
        image = self.root / "flaky.jpg"
        image.write_bytes(b"flaky")
        await self.reconciler.observe_file(image)
        self.r.jobs.collection.docs[0]["status"] = "failed"
        self.events.clear()

        await self.reconciler.observe_file(image)  # no redispatch_failed

        self.assertEqual(self._queued_events(), [])


if __name__ == "__main__":
    unittest.main()
