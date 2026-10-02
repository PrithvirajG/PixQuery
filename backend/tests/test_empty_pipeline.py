"""A pipeline that exists but has no stages has nothing to run.

Regression. The built-in default chain (object detection → vision_language_model → embedding)
exists for the legacy ``default_image_analysis`` id, which never had a stored
definition. But the fallback tested ``not definition.get("nodes")``, so a freshly
created — or emptied — user pipeline attached to a workspace silently ran that
chain too: the reconciler minted jobs for it at the legacy "v1" version and the
worker executed YOLO, BLIP and CLIP that the pipeline never contained.
"""
import tempfile
import unittest
from pathlib import Path

from src.errors.executors import PermanentNodeError
from src.services.pipeline_execution_service import PipelineExecutionService
from src.services.reconciliation_service import ReconciliationService
from tests.repo_factory import new_repos


class FakePublisher:
    def __init__(self):
        self.messages = []

    async def publish(self, message):
        self.messages.append(message)


class ReconcileEmptyPipelineTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        (root / "a.jpg").write_bytes(b"image-a")

        self.r = new_repos()
        self.empty = self.r.pipelines.create(owner_id="o", name="Empty", nodes=[])
        self.publisher = FakePublisher()
        self.reconciler = ReconciliationService(
            assets=self.r.assets, observations=self.r.observations, jobs=self.r.jobs,
            pipelines=self.r.pipelines, publisher=self.publisher,
            workspace_path=str(root), workspace_id="ws1", pipeline_ids=[self.empty["_id"]],
            stable_interval_seconds=0.01, stable_timeout_seconds=1,
        )

    async def test_an_empty_pipeline_gets_no_jobs(self):
        queued = await self.reconciler.reconcile()

        self.assertEqual(queued, [])
        self.assertEqual(self.publisher.messages, [])
        self.assertEqual(self.r.jobs.list_all(), [])
        # The image itself is still ingested — only processing is skipped.
        self.assertEqual(len(self.r.assets.list_all_ids()), 1)

    async def test_adding_stages_later_starts_processing(self):
        await self.reconciler.reconcile()
        self.r.pipelines.update(self.empty["_id"], {"nodes": [
            {"node_id": "n0", "pipeline_node_id": "pn0", "config_overrides": {}},
        ]})

        queued = await self.reconciler.reconcile()

        self.assertEqual(len(queued), 1)
        (job,) = self.r.jobs.list_all()
        self.assertTrue(job["pipeline_version"].startswith("p-"))  # a real version, not legacy "v1"

    async def test_other_attached_pipelines_are_unaffected(self):
        real = self.r.pipelines.create(owner_id="o", name="Real", nodes=[
            {"node_id": "n0", "pipeline_node_id": "pn0", "config_overrides": {}},
        ])
        self.reconciler.pipelines_to_run = [(self.empty["_id"], None), (real["_id"], None)]

        await self.reconciler.reconcile()

        self.assertEqual([j["pipeline_id"] for j in self.r.jobs.list_all()], [real["_id"]])


class RunEmptyPipelineTests(unittest.TestCase):
    def setUp(self):
        self.r = new_repos()
        self.executed = []
        self.service = PipelineExecutionService(
            jobs=self.r.jobs, runs=self.r.runs, outputs=self.r.outputs, assets=self.r.assets,
            pipelines=self.r.pipelines, nodes=self.r.nodes,
            get_executor=self._get_executor,
            image_loader=lambda asset: "FAKE_IMAGE",
        )
        self.asset = self.r.assets.upsert(
            content_sha256="h", mime_type="image/jpeg", size_bytes=1, current_path="/x.jpg",
        )

    def _get_executor(self, node_type):
        self.executed.append(node_type)
        raise AssertionError(f"no executor should run, but {node_type!r} was requested")

    def _job_for(self, pipeline_id):
        job, _ = self.r.jobs.get_or_create(
            asset_id=self.asset["_id"], pipeline_id=pipeline_id, pipeline_version="v1",
        )
        return job

    def test_a_job_for_an_empty_pipeline_fails_clearly_instead_of_running_defaults(self):
        empty = self.r.pipelines.create(owner_id="o", name="Empty", nodes=[])
        job = self._job_for(empty["_id"])

        with self.assertRaises(PermanentNodeError) as ctx:
            self.service.run_job(job["_id"])

        self.assertIn("no stages", str(ctx.exception))
        self.assertEqual(self.executed, [])
        stored = self.r.jobs.get(job["_id"])
        self.assertEqual(stored["status"], "failed")
        self.assertIn("no stages", stored["last_error"]["message"])
        self.assertEqual(self.r.outputs.list_for_asset(self.asset["_id"]), [])

    def test_the_legacy_id_with_no_stored_definition_still_runs_the_default_chain(self):
        job = self._job_for("default_image_analysis")

        with self.assertRaises(AssertionError):  # our executor stub trips on the first default node
            self.service.run_job(job["_id"])

        self.assertEqual(self.executed, ["object_detection"])


if __name__ == "__main__":
    unittest.main()
