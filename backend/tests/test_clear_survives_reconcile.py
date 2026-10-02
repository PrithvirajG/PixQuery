"""Clearing a pipeline's outputs must stick: the reconciler may not quietly rebuild them.

Regression. Clearing used to delete the (asset, pipeline) pair's *job rows* along
with its runs and outputs. The reconciler treats "no job for this asset+pipeline+
version" as "never processed", so the very next pass — the file-watcher's periodic
reconcile runs about once a minute, and the live watcher fires on file events —
created and dispatched fresh jobs and regenerated everything that had just been
cleared. To the user, "Clear outputs" simply didn't work.

The job row is what records that a pair was already handled, so clearing keeps it
(a ``completed`` job with no outputs already reads as NOT_STARTED in the UI, and a
manual per-image reprocess reuses it). Only a pipeline *edit* — a new version, so a
new job — or an explicit reprocess brings outputs back.
"""
import asyncio
import tempfile
import unittest
from pathlib import Path

from src.services.job_service import JobService
from src.services.reconciliation_service import ReconciliationService
from src.services.workspace_service import WorkspaceService
from tests.repo_factory import new_repos


class FakePublisher:
    """Stands in for RabbitPublisher on both the reconciler and JobService side."""

    def __init__(self):
        self.messages = []

    async def connect(self):
        return None

    async def publish(self, message):
        self.messages.append(message)

    async def close(self):
        return None


class ClearSurvivesReconcileTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        (root / "a.jpg").write_bytes(b"image-a")
        (root / "b.jpg").write_bytes(b"image-b")

        self.r = new_repos()
        self.pipeline = self.r.pipelines.create(
            owner_id="owner-1", name="P",
            nodes=[{"node_id": "n0", "pipeline_node_id": "pn0", "config_overrides": {}}],
        )
        self.pid = self.pipeline["_id"]
        self.ws = self.r.workspaces.create(
            owner_id="owner-1", name="W", workspace_path=str(root), pipeline_ids=[self.pid],
        )
        self.wid = self.ws["_id"]
        self.publisher = FakePublisher()
        self.reconciler = ReconciliationService(
            assets=self.r.assets, observations=self.r.observations, jobs=self.r.jobs,
            pipelines=self.r.pipelines, publisher=self.publisher,
            workspace_path=str(root), workspace_id=self.wid, pipeline_ids=[self.pid],
            stable_interval_seconds=0.01, stable_timeout_seconds=1,
        )
        self.service = WorkspaceService(
            workspaces=self.r.workspaces, users=self.r.users, assets=self.r.assets,
            observations=self.r.observations, jobs=self.r.jobs, runs=self.r.runs,
            outputs=self.r.outputs,
        )

        # First scan creates one job per image; "process" each the way the worker does.
        await self.reconciler.reconcile()
        self.jobs = self.r.jobs.list_all()
        self.assertEqual(len(self.jobs), 2)
        for job in self.jobs:
            self.r.jobs.start(job["_id"])
            run = self.r.runs.create(
                job_id=job["_id"], asset_id=job["asset_id"], pipeline_id=self.pid,
                pipeline_version=job["pipeline_version"],
            )
            self.r.outputs.add(
                asset_id=job["asset_id"], pipeline_run_id=run["_id"], model_name="m",
                model_version="v", output_type="detections", payload={},
                workspace_id=self.wid, pipeline_id=self.pid,
                pipeline_version=job["pipeline_version"],
            )
            self.r.jobs.complete(job["_id"])
        self.publisher.messages.clear()

    def _outputs(self):
        return list(self.r.outputs.collection.find({}))

    async def test_workspace_clear_is_not_undone_by_the_next_reconcile(self):
        self.service.clear_pipeline_outputs(self.wid, self.pid, owner_id="owner-1")
        self.assertEqual(self._outputs(), [])

        # The periodic pass (and the live watcher) both go through reconcile().
        queued = await self.reconciler.reconcile()

        self.assertEqual(queued, [])
        self.assertEqual(self.publisher.messages, [])
        self.assertEqual(self._outputs(), [])
        self.assertEqual(len(self.r.jobs.list_all()), 2)  # no replacement jobs were minted

    async def test_per_image_clear_is_not_undone_by_the_next_reconcile(self):
        target = self.jobs[0]
        self.service.clear_asset_pipeline_outputs(target["asset_id"], self.pid, owner_id="owner-1")

        queued = await self.reconciler.reconcile()

        self.assertEqual(queued, [])
        self.assertEqual(self.publisher.messages, [])
        remaining = self._outputs()
        self.assertEqual([o["asset_id"] for o in remaining], [self.jobs[1]["asset_id"]])

    async def test_cleared_pair_can_still_be_reprocessed_manually(self):
        target = self.jobs[0]
        self.service.clear_pipeline_outputs(self.wid, self.pid, owner_id="owner-1")

        manual = FakePublisher()
        jobs = JobService(
            jobs=self.r.jobs, assets=self.r.assets, workspaces=self.r.workspaces,
            pipelines=self.r.pipelines, publisher_factory=lambda: manual,
        )
        job = await jobs.retrigger_pipeline(target["asset_id"], self.pid, user_id="owner-1")

        self.assertEqual(job["_id"], target["_id"])  # reused the pair's job, not a new one
        self.assertEqual(manual.messages, [target["_id"]])
        self.assertEqual(self.r.jobs.get(target["_id"])["status"], "queued")

    async def test_editing_the_pipeline_still_reprocesses(self):
        """A new version is a new job: clearing must not freeze the pipeline forever."""
        self.service.clear_pipeline_outputs(self.wid, self.pid, owner_id="owner-1")
        self.r.pipelines.update(self.pid, {"nodes": [
            {"node_id": "n0", "pipeline_node_id": "pn0", "config_overrides": {"confidence": 0.9}},
        ]})

        queued = await self.reconciler.reconcile()

        self.assertEqual(len(queued), 2)
        self.assertEqual(sorted(self.publisher.messages), sorted(queued))


if __name__ == "__main__":
    unittest.main()
