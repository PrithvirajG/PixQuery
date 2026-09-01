"""Tests that ingestion stamps jobs with the workspace's assigned pipelines."""
import tempfile
import unittest
from pathlib import Path

from src.consumer.ingestion import pipeline_version_hash
from src.services.reconciliation_service import ReconciliationService
from tests.repo_factory import new_repos


class FakePublisher:
    def __init__(self):
        self.messages = []

    async def publish(self, message):
        self.messages.append(message)


class PipelineLinkageTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "a.jpg").write_bytes(b"image-bytes")
        self.r = new_repos()
        self.publisher = FakePublisher()
        self.node_ids = {
            n["node_type"]: n["_id"]
            for n in self.r.nodes.list_all(owner_id="owner-1")
        }

    async def asyncTearDown(self):
        self.tmp.cleanup()

    def _make_pipeline(self, name, overrides=None):
        nodes = [
            {
                "node_id": "n0",
                "pipeline_node_id": self.node_ids["captioning"],
                "order": 0,
                "config_overrides": overrides or {},
            }
        ]
        return self.r.pipelines.create(owner_id="owner-1", name=name, nodes=nodes)

    def _reconciler(self, pipeline_ids):
        return ReconciliationService(
            assets=self.r.assets, observations=self.r.observations, jobs=self.r.jobs, pipelines=self.r.pipelines,
            publisher=self.publisher,
            workspace_path=str(self.root),
            workspace_id="ws-1",
            pipeline_ids=pipeline_ids,
            stable_interval_seconds=0.01,
            stable_timeout_seconds=1,
        )

    async def test_one_job_per_assigned_pipeline(self):
        p1 = self._make_pipeline("p1")
        p2 = self._make_pipeline("p2", overrides={"model": "blip-large"})

        await self._reconciler([p1["_id"], p2["_id"]]).reconcile()

        jobs = self.r.jobs.list_all()
        self.assertEqual(len(jobs), 2)
        self.assertEqual({j["pipeline_id"] for j in jobs}, {p1["_id"], p2["_id"]})
        self.assertEqual(len(self.publisher.messages), 2)

    async def test_job_version_tracks_pipeline_definition(self):
        pipeline = self._make_pipeline("p1")
        await self._reconciler([pipeline["_id"]]).reconcile()

        job = self.r.jobs.list_all()[0]
        defn = self.r.pipelines.get(pipeline["_id"])
        expected = pipeline_version_hash(defn["nodes"], defn.get("edges", []))
        self.assertEqual(job["pipeline_version"], expected)

    async def test_editing_pipeline_config_triggers_reprocess(self):
        pipeline = self._make_pipeline("p1")
        await self._reconciler([pipeline["_id"]]).reconcile()
        self.assertEqual(len(self.r.jobs.list_all()), 1)

        # Editing the pipeline changes its version hash → a new job is created.
        from src.services.pipeline_service import _build_graph

        updated_nodes, updated_edges = _build_graph([
            {"pipeline_node_id": self.node_ids["captioning"], "config_overrides": {"model": "blip-large"}}
        ])
        self.r.pipelines.update(
            pipeline["_id"], {"nodes": updated_nodes, "edges": updated_edges}
        )

        await self._reconciler([pipeline["_id"]]).reconcile()
        jobs = self.r.jobs.list_all()
        self.assertEqual(len(jobs), 2)
        self.assertEqual(len({j["pipeline_version"] for j in jobs}), 2)

    async def test_manual_rescan_redispatches_failed_job(self):
        # `redispatch_failed=True` is what a manual "Scan" API call opts into
        # (see consume_scan_commands) — a human explicitly asking to re-check
        # the workspace is exactly when retrying a failed job makes sense.
        pipeline = self._make_pipeline("p1")
        await self._reconciler([pipeline["_id"]]).reconcile()
        job = self.r.jobs.list_all()[0]

        # Job fails permanently (e.g. an executor error), then gets retried.
        self.r.jobs.fail(job["_id"], final_status="failed", next_attempt_at=None, error={"class": "X", "message": "boom"})
        self.assertEqual(self.r.jobs.get(job["_id"])["status"], "failed")
        self.publisher.messages.clear()

        await self._reconciler([pipeline["_id"]]).reconcile(redispatch_failed=True)

        requeued = self.r.jobs.get(job["_id"])
        self.assertEqual(requeued["status"], "queued")
        self.assertEqual(requeued["attempt_count"], 0)  # fresh retry budget
        self.assertEqual(len(self.r.jobs.list_all()), 1)  # requeued, not duplicated
        self.assertIn(job["_id"], self.publisher.messages)  # re-dispatched

    async def test_automatic_rescan_leaves_failed_job_failed(self):
        # The periodic full-workspace reconcile and the live filesystem watcher
        # both call reconcile()/observe_file() with no override — an automatic,
        # unattended pass must never resurrect a job that's already failed, or
        # a deterministic bug retries forever with nobody watching.
        pipeline = self._make_pipeline("p1")
        await self._reconciler([pipeline["_id"]]).reconcile()
        job = self.r.jobs.list_all()[0]

        self.r.jobs.fail(job["_id"], final_status="failed", next_attempt_at=None, error={"class": "X", "message": "boom"})
        self.publisher.messages.clear()

        await self._reconciler([pipeline["_id"]]).reconcile()

        self.assertEqual(self.r.jobs.get(job["_id"])["status"], "failed")
        self.assertEqual(self.publisher.messages, [])

    async def test_rescan_leaves_completed_job_alone(self):
        pipeline = self._make_pipeline("p1")
        await self._reconciler([pipeline["_id"]]).reconcile()
        job = self.r.jobs.list_all()[0]
        self.r.jobs.start(job["_id"])
        self.r.jobs.complete(job["_id"])
        self.publisher.messages.clear()

        await self._reconciler([pipeline["_id"]]).reconcile()

        self.assertEqual(self.r.jobs.get(job["_id"])["status"], "completed")
        self.assertEqual(self.publisher.messages, [])  # not re-dispatched

    async def test_no_assigned_pipeline_creates_no_jobs(self):
        await self._reconciler(None).reconcile()

        # Files are still ingested, but nothing is dispatched — there is no
        # implicit default pipeline anymore.
        self.assertEqual(self.r.jobs.list_all(), [])
        self.assertEqual(len(self.r.assets.collection.docs), 1)


if __name__ == "__main__":
    unittest.main()
