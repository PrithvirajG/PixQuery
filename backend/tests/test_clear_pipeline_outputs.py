"""Tests for bulk-clearing one pipeline's outputs within one workspace."""
import unittest

from src.repositories import InMemoryPipelineRepository
from src.services.workspace_service import WorkspaceAccessError, WorkspaceService


class ClearPipelineOutputsRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.repo = InMemoryPipelineRepository()
        self.asset = self.repo.upsert_asset(
            content_sha256="h1", mime_type="image/jpeg", size_bytes=5,
            current_path="/photos/a.jpg", workspace_id="ws-a",
        )
        self.job_a_p1 = self.repo.ensure_processing_job(
            asset_id=self.asset["_id"], pipeline_id="p1", pipeline_version="v1", workspace_id="ws-a",
        )[0]
        self.job_a_p2 = self.repo.ensure_processing_job(
            asset_id=self.asset["_id"], pipeline_id="p2", pipeline_version="v1", workspace_id="ws-a",
        )[0]
        for job, pid in ((self.job_a_p1, "p1"), (self.job_a_p2, "p2")):
            run = self.repo.start_job(job["_id"])
            self.repo.add_model_output(
                asset_id=self.asset["_id"],
                pipeline_run_id=run["pipeline_run_id"],
                model_name="m", model_version="v", output_type="detections",
                payload={}, workspace_id="ws-a", pipeline_id=pid, pipeline_version="v1",
            )
            self.repo.complete_job(job["_id"], run["pipeline_run_id"])

    def test_clears_only_the_targeted_pipeline(self):
        result = self.repo.clear_pipeline_outputs("ws-a", "p1")
        self.assertEqual(result, {"outputs_deleted": 1, "runs_deleted": 1, "jobs_deleted": 1})

        remaining = list(self.repo.model_outputs.find({"asset_id": self.asset["_id"]}))
        self.assertEqual([o["pipeline_id"] for o in remaining], ["p2"])

        remaining_runs = list(self.repo.pipeline_runs.find({"job_id": self.job_a_p1["_id"]}))
        self.assertEqual(remaining_runs, [])

    def test_deletes_job_so_pair_returns_to_not_started(self):
        self.repo.clear_pipeline_outputs("ws-a", "p1")
        # No job row left — _pipeline_state reads that as NOT_STARTED.
        self.assertIsNone(self.repo.get_job(self.job_a_p1["_id"]))
        # untouched pipeline's job keeps its completed status
        other_job = self.repo.get_job(self.job_a_p2["_id"])
        self.assertEqual(other_job["status"], "completed")

    def test_does_not_touch_other_workspaces(self):
        other_asset = self.repo.upsert_asset(
            content_sha256="h2", mime_type="image/jpeg", size_bytes=5,
            current_path="/photos/b.jpg", workspace_id="ws-b",
        )
        job = self.repo.ensure_processing_job(
            asset_id=other_asset["_id"], pipeline_id="p1", pipeline_version="v1", workspace_id="ws-b",
        )[0]
        run = self.repo.start_job(job["_id"])
        self.repo.add_model_output(
            asset_id=other_asset["_id"], pipeline_run_id=run["pipeline_run_id"],
            model_name="m", model_version="v", output_type="detections",
            payload={}, workspace_id="ws-b", pipeline_id="p1", pipeline_version="v1",
        )
        self.repo.complete_job(job["_id"], run["pipeline_run_id"])

        self.repo.clear_pipeline_outputs("ws-a", "p1")

        remaining = list(self.repo.model_outputs.find({"asset_id": other_asset["_id"]}))
        self.assertEqual(len(remaining), 1)
        self.assertEqual(self.repo.get_job(job["_id"])["status"], "completed")


class ClearPipelineOutputsPermissionTests(unittest.TestCase):
    def setUp(self):
        self.repo = InMemoryPipelineRepository()
        self.service = WorkspaceService(self.repo)
        self.ws = self.repo.create_workspace(owner_id="owner-1", name="A", workspace_path="/a")

    def test_owner_can_clear(self):
        result = self.service.clear_pipeline_outputs(self.ws["_id"], "p1", owner_id="owner-1")
        self.assertEqual(result, {"outputs_deleted": 0, "runs_deleted": 0, "jobs_deleted": 0})

    def test_viewer_denied(self):
        self.repo.update_workspace(
            self.ws["_id"], {"members": [{"user_id": "viewer-1", "role": "viewer"}]}
        )
        with self.assertRaises(WorkspaceAccessError):
            self.service.clear_pipeline_outputs(self.ws["_id"], "p1", owner_id="viewer-1")

    def test_stranger_with_no_access_gets_none(self):
        self.assertIsNone(
            self.service.clear_pipeline_outputs(self.ws["_id"], "p1", owner_id="stranger")
        )

    def test_unknown_workspace_returns_none(self):
        self.assertIsNone(
            self.service.clear_pipeline_outputs("missing-ws", "p1", owner_id="owner-1")
        )


if __name__ == "__main__":
    unittest.main()
