"""Per-(image, pipeline) lifecycle state exposed by the image detail endpoint.

The detail view drives its pipeline sections off the workspace's attached
pipelines — not off which outputs happen to exist — so a pipeline that has never
run still gets a section (and a Process button). These cover that mapping plus
the NOT_STARTED / QUEUED / PROCESSING / COMPLETED / FAILED derivation.
"""
import unittest

from src.repositories import InMemoryPipelineRepository
from src.services.image_service import ImageService


class PipelineStateTests(unittest.TestCase):
    def setUp(self):
        self.repo = InMemoryPipelineRepository()
        self.service = ImageService(self.repo)
        self.pipeline = self.repo.create_pipeline(owner_id="o", name="P1", nodes=[])
        self.other = self.repo.create_pipeline(owner_id="o", name="P2", nodes=[])
        self.ws = self.repo.create_workspace(
            owner_id="o", name="W", workspace_path="/w",
            pipeline_ids=[self.pipeline["_id"]],
        )
        self.asset = self.repo.upsert_asset(
            content_sha256="h", mime_type="image/jpeg", size_bytes=1,
            current_path="/w/a.jpg", workspace_id=self.ws["_id"],
        )

    def _states(self):
        detail = self.service.get_image_detail(self.asset["_id"])
        return {p["pipeline_id"]: p["state"] for p in detail["provenance"]["pipelines"]}

    def _job(self):
        return self.repo.ensure_processing_job(
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
        self.repo.start_job(job["_id"])
        self.assertEqual(self._states()[self.pipeline["_id"]], "processing")

    def test_completed_job_with_outputs_reports_completed(self):
        job = self._job()
        run = self.repo.start_job(job["_id"])
        self.repo.add_model_output(
            asset_id=self.asset["_id"], pipeline_run_id=run["pipeline_run_id"],
            model_name="m", model_version="v", output_type="detections",
            payload={"detections": []}, workspace_id=self.ws["_id"],
            pipeline_id=self.pipeline["_id"], pipeline_version="v1",
        )
        self.repo.complete_job(job["_id"], run["pipeline_run_id"])
        self.assertEqual(self._states()[self.pipeline["_id"]], "completed")

    def test_completed_job_whose_outputs_were_cleared_is_not_started(self):
        job = self._job()
        run = self.repo.start_job(job["_id"])
        self.repo.add_model_output(
            asset_id=self.asset["_id"], pipeline_run_id=run["pipeline_run_id"],
            model_name="m", model_version="v", output_type="detections",
            payload={"detections": []}, workspace_id=self.ws["_id"],
            pipeline_id=self.pipeline["_id"], pipeline_version="v1",
        )
        self.repo.complete_job(job["_id"], run["pipeline_run_id"])

        self.repo.clear_pipeline_outputs(self.ws["_id"], self.pipeline["_id"])

        states = self._states()
        self.assertEqual(states[self.pipeline["_id"]], "not_started")
        # Section survives the clear — otherwise there'd be no way to re-run it.
        self.assertIn(self.pipeline["_id"], states)

    def test_failed_job_reports_failed(self):
        job = self._job()
        run = self.repo.start_job(job["_id"])
        self.repo.fail_job(
            job["_id"], run["pipeline_run_id"], {"message": "boom"}, permanent=True
        )
        self.assertEqual(self._states()[self.pipeline["_id"]], "failed")


if __name__ == "__main__":
    unittest.main()
