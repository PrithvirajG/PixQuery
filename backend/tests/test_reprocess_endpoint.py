"""Manual per-image reprocess (JobService.retrigger_pipeline).

Covers the guards that stop a click from doing something wrong: role checks,
double-dispatch of an in-flight job, and pipelines not attached to the image's
workspace.
"""
import asyncio
import unittest

from src.errors.jobs import JobConflictError
from src.errors.workspaces import WorkspaceAccessError
from src.services.job_service import JobService
from tests.repo_factory import new_repos


class _FakePublisher:
    """Records what got published instead of touching RabbitMQ."""

    published: list = []

    def __init__(self):
        type(self).instances.append(self)

    instances: list = []

    async def connect(self):
        return None

    async def publish(self, job_id):
        type(self).published.append(job_id)

    async def close(self):
        return None


def _run(coro):
    return asyncio.run(coro)


class RetriggerPipelineTests(unittest.TestCase):
    def setUp(self):
        _FakePublisher.published = []
        _FakePublisher.instances = []
        self.r = new_repos()
        self.service = JobService(
            jobs=self.r.jobs, assets=self.r.assets, workspaces=self.r.workspaces, pipelines=self.r.pipelines,
            publisher_factory=_FakePublisher,
        )

        self.pipeline = self.r.pipelines.create(
            owner_id="owner-1", name="P",
            nodes=[{"node_id": "n0", "pipeline_node_id": "pn0", "config_overrides": {}}],
        )
        self.unattached = self.r.pipelines.create(owner_id="owner-1", name="Other", nodes=[])
        self.ws = self.r.workspaces.create(
            owner_id="owner-1", name="W", workspace_path="/w",
            pipeline_ids=[self.pipeline["_id"]],
        )
        self.asset = self.r.assets.upsert(
            content_sha256="h", mime_type="image/jpeg", size_bytes=1,
            current_path="/w/a.jpg", workspace_id=self.ws["_id"],
        )

    def _retrigger(self, pipeline_id=None, user_id="owner-1"):
        return _run(
            self.service.retrigger_pipeline(
                self.asset["_id"], pipeline_id or self.pipeline["_id"], user_id=user_id
            )
        )

    def test_creates_and_publishes_a_job(self):
        job = self._retrigger()
        self.assertIsNotNone(job)
        self.assertEqual(job["status"], "queued")
        self.assertEqual(_FakePublisher.published, [job["_id"]])

    def test_editor_is_allowed(self):
        self.r.workspaces.update(
            self.ws["_id"], {"members": [{"user_id": "editor-1", "role": "editor"}]}
        )
        self.assertIsNotNone(self._retrigger(user_id="editor-1"))

    def test_viewer_is_denied(self):
        self.r.workspaces.update(
            self.ws["_id"], {"members": [{"user_id": "viewer-1", "role": "viewer"}]}
        )
        with self.assertRaises(WorkspaceAccessError):
            self._retrigger(user_id="viewer-1")
        self.assertEqual(_FakePublisher.published, [])

    def test_stranger_is_denied(self):
        with self.assertRaises(WorkspaceAccessError):
            self._retrigger(user_id="nobody")

    def test_pipeline_not_attached_to_workspace_is_rejected(self):
        with self.assertRaises(JobConflictError):
            self._retrigger(pipeline_id=self.unattached["_id"])
        self.assertEqual(_FakePublisher.published, [])

    def test_second_click_while_queued_is_rejected(self):
        self._retrigger()
        _FakePublisher.published = []
        # Job is now queued — dispatching again would run it twice.
        with self.assertRaises(JobConflictError):
            self._retrigger()
        self.assertEqual(_FakePublisher.published, [])

    def test_click_while_processing_is_rejected(self):
        job = self._retrigger()
        self.r.jobs.start(job["_id"])  # worker picked it up
        with self.assertRaises(JobConflictError):
            self._retrigger()

    def test_completed_job_can_be_retriggered(self):
        job = self._retrigger()
        self.r.jobs.start(job["_id"])
        self.r.jobs.complete(job["_id"])
        _FakePublisher.published = []

        again = self._retrigger()
        self.assertEqual(again["status"], "queued")
        self.assertEqual(_FakePublisher.published, [job["_id"]])

    def test_missing_asset_returns_none(self):
        result = _run(
            self.service.retrigger_pipeline("nope", self.pipeline["_id"], user_id="owner-1")
        )
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
