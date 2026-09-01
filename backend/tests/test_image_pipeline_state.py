"""Per-(image, pipeline) lifecycle state exposed by the image detail endpoint.

The detail view drives its pipeline sections off the workspace's attached
pipelines — not off which outputs happen to exist — so a pipeline that has never
run still gets a section (and a Process button). These cover that mapping plus
the NOT_STARTED / QUEUED / PROCESSING / COMPLETED / FAILED derivation.
"""
import unittest

from src.services.image_service import ImageService
from src.services.workspace_service import WorkspaceService
from tests.repo_factory import new_repos


class PipelineStateTests(unittest.TestCase):
    def setUp(self):
        self.r = new_repos()
        self.service = ImageService(
            assets=self.r.assets, observations=self.r.observations, workspaces=self.r.workspaces,
            pipelines=self.r.pipelines, jobs=self.r.jobs, runs=self.r.runs, outputs=self.r.outputs,
        )
        self.workspace_service = WorkspaceService(
            workspaces=self.r.workspaces, users=self.r.users, assets=self.r.assets,
            observations=self.r.observations, jobs=self.r.jobs, runs=self.r.runs, outputs=self.r.outputs,
        )
        self.pipeline = self.r.pipelines.create(owner_id="o", name="P1", nodes=[])
        self.other = self.r.pipelines.create(owner_id="o", name="P2", nodes=[])
        self.ws = self.r.workspaces.create(
            owner_id="o", name="W", workspace_path="/w",
            pipeline_ids=[self.pipeline["_id"]],
        )
        self.asset = self.r.assets.upsert(
            content_sha256="h", mime_type="image/jpeg", size_bytes=1,
            current_path="/w/a.jpg", workspace_id=self.ws["_id"],
        )

    def _states(self):
        detail = self.service.get_image_detail(self.asset["_id"])
        return {p["pipeline_id"]: p["state"] for p in detail["provenance"]["pipelines"]}

    def _job(self):
        return self.r.jobs.get_or_create(
            asset_id=self.asset["_id"], pipeline_id=self.pipeline["_id"],
            pipeline_version="v1", workspace_id=self.ws["_id"],
        )[0]

    def test_attached_pipeline_with_no_job_is_not_started(self):
        # The whole point: a section exists even with zero outputs and zero jobs.
        self.assertEqual(self._states(), {self.pipeline["_id"]: "not_started"})

    def test_unattached_pipeline_is_not_listed(self):
        self.assertNotIn(self.other["_id"], self._states())

    def test_queued_job_reports_queued(self):
        self._job()
        self.assertEqual(self._states()[self.pipeline["_id"]], "queued")

    def test_started_job_reports_processing(self):
        job = self._job()
        self.r.jobs.start(job["_id"])
        self.assertEqual(self._states()[self.pipeline["_id"]], "processing")

    def test_completed_job_with_outputs_reports_completed(self):
        job = self._job()
        self.r.jobs.start(job["_id"])
        run = self.r.runs.create(
            job_id=job["_id"], asset_id=self.asset["_id"],
            pipeline_id=self.pipeline["_id"], pipeline_version="v1",
        )
        self.r.outputs.add(
            asset_id=self.asset["_id"], pipeline_run_id=run["_id"],
            model_name="m", model_version="v", output_type="detections",
            payload={"detections": []}, workspace_id=self.ws["_id"],
            pipeline_id=self.pipeline["_id"], pipeline_version="v1",
        )
        self.r.jobs.complete(job["_id"])
        self.assertEqual(self._states()[self.pipeline["_id"]], "completed")

    def test_completed_job_whose_outputs_were_cleared_is_not_started(self):
        job = self._job()
        self.r.jobs.start(job["_id"])
        run = self.r.runs.create(
            job_id=job["_id"], asset_id=self.asset["_id"],
            pipeline_id=self.pipeline["_id"], pipeline_version="v1",
        )
        self.r.outputs.add(
            asset_id=self.asset["_id"], pipeline_run_id=run["_id"],
            model_name="m", model_version="v", output_type="detections",
            payload={"detections": []}, workspace_id=self.ws["_id"],
            pipeline_id=self.pipeline["_id"], pipeline_version="v1",
        )
        self.r.jobs.complete(job["_id"])

        self.workspace_service.clear_pipeline_outputs(self.ws["_id"], self.pipeline["_id"], owner_id="o")

        states = self._states()
        self.assertEqual(states[self.pipeline["_id"]], "not_started")
        # Section survives the clear — otherwise there'd be no way to re-run it.
        self.assertIn(self.pipeline["_id"], states)

    def test_failed_job_reports_failed(self):
        job = self._job()
        self.r.jobs.start(job["_id"])
        self.r.jobs.fail(job["_id"], final_status="failed", next_attempt_at=None, error={"message": "boom"})
        self.assertEqual(self._states()[self.pipeline["_id"]], "failed")


if __name__ == "__main__":
    unittest.main()
