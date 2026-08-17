import asyncio
import tempfile
import unittest
from pathlib import Path

from src.pipelines.ingestion import FilesystemReconciler, wait_for_stable_file
from src.repositories import InMemoryPipelineRepository


class FakePublisher:
    def __init__(self):
        self.messages = []

    async def publish(self, message):
        self.messages.append(message)


class FilesystemPipelineTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.repository = InMemoryPipelineRepository()
        self.publisher = FakePublisher()
        self.reconciler = FilesystemReconciler(
            repository=self.repository,
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

        self.assertEqual(len(self.repository.image_assets.docs), 1)
        self.assertEqual(len(self.repository.file_observations.docs), 2)
        self.assertEqual(len(self.repository.processing_jobs.docs), 1)

    async def test_rename_keeps_same_asset_by_hash(self):
        original = self.root / "old.jpg"
        original.write_bytes(b"rename-me")
        await self.reconciler.reconcile()
        asset_id = self.repository.image_assets.docs[0]["_id"]

        original.rename(self.root / "new.jpg")
        await self.reconciler.reconcile()

        self.assertEqual(len(self.repository.image_assets.docs), 1)
        self.assertEqual(self.repository.image_assets.docs[0]["_id"], asset_id)
        statuses = {obs["relative_path"]: obs["status"] for obs in self.repository.file_observations.docs}
        self.assertEqual(statuses["old.jpg"], "missing")
        self.assertEqual(statuses["new.jpg"], "active")

    async def test_delete_marks_observation_missing_and_hides_asset(self):
        image = self.root / "delete.jpg"
        image.write_bytes(b"delete-me")
        await self.reconciler.reconcile()

        image.unlink()
        await self.reconciler.reconcile()

        self.assertEqual(self.repository.file_observations.docs[0]["status"], "missing")
        self.assertFalse(self.repository.image_assets.docs[0]["active"])
        self.assertEqual(self.repository.list_active_assets(), [])

    async def test_duplicate_observations_do_not_create_duplicate_processing_jobs(self):
        image = self.root / "one.jpg"
        image.write_bytes(b"queue-once")

        await self.reconciler.observe_file(image)
        await self.reconciler.observe_file(image)

        self.assertEqual(len(self.repository.processing_jobs.docs), 1)
        self.assertEqual(len(self.publisher.messages), 1)

    async def test_completed_pipeline_version_is_not_rerun_until_version_changes(self):
        image = self.root / "versioned.jpg"
        image.write_bytes(b"versioned")
        await self.reconciler.observe_file(image)

        job = self.repository.processing_jobs.docs[0]
        self.repository.processing_jobs.docs[0]["status"] = "completed"
        await self.reconciler.observe_file(image)
        self.assertEqual(len(self.repository.processing_jobs.docs), 1)

        next_reconciler = FilesystemReconciler(
            repository=self.repository,
            publisher=self.publisher,
            workspace_path=str(self.root),
            workspace_id="test-root",
            pipeline_id="test-pipeline",
            pipeline_version="v2",
            stable_interval_seconds=0.01,
            stable_timeout_seconds=1,
        )
        await next_reconciler.observe_file(image)
        self.assertEqual(len(self.repository.processing_jobs.docs), 2)
        self.assertEqual(self.repository.processing_jobs.docs[0]["_id"], job["_id"])

    async def test_no_pipelines_assigned_ingests_files_without_creating_jobs(self):
        image = self.root / "orphan.jpg"
        image.write_bytes(b"no-pipeline")
        reconciler = FilesystemReconciler(
            repository=self.repository,
            publisher=self.publisher,
            workspace_path=str(self.root),
            workspace_id="test-root",
            stable_interval_seconds=0.01,
            stable_timeout_seconds=1,
        )

        await reconciler.reconcile()

        self.assertEqual(len(self.repository.image_assets.docs), 1)
        self.assertEqual(len(self.repository.file_observations.docs), 1)
        self.assertEqual(len(self.repository.processing_jobs.docs), 0)
        self.assertEqual(self.publisher.messages, [])


class ProcessingRetryTests(unittest.TestCase):
    def test_failed_processing_retries_three_times_then_marks_failed(self):
        repository = InMemoryPipelineRepository()
        asset = repository.upsert_asset(
            content_sha256="abc",
            mime_type="image/jpeg",
            size_bytes=3,
            current_path="/missing.jpg",
        )
        job, _ = repository.ensure_processing_job(
            asset_id=asset["_id"],
            pipeline_id="default_image_analysis",
            pipeline_version="v1",
        )

        statuses = []
        for _ in range(3):
            started = repository.start_job(job["_id"])
            statuses.append(
                repository.fail_job(
                    job["_id"],
                    started["pipeline_run_id"],
                    {"class": "RuntimeError", "message": "boom"},
                )
            )

        self.assertEqual(statuses, ["queued", "queued", "failed"])
        self.assertEqual(repository.get_job(job["_id"])["status"], "failed")


if __name__ == "__main__":
    unittest.main()
