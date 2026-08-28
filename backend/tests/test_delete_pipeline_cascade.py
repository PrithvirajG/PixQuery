"""Deleting a pipeline must take everything downstream of it with it.

Mirrors ``delete_workspace``'s cascade: runs, jobs and model outputs go, and the
id is pulled from any workspace referencing it (a dangling id would otherwise
make the reconciler keep minting jobs for a pipeline that no longer exists).
Assets and the shared node library survive — images outlive any one pipeline.
"""
import unittest

from src.repositories import InMemoryPipelineRepository
from src.services.image_service import ImageService


class DeletePipelineCascadeTests(unittest.TestCase):
    def setUp(self):
        self.repo = InMemoryPipelineRepository()
        self.doomed = self.repo.create_pipeline(owner_id="o", name="Doomed", nodes=[])
        self.keeper = self.repo.create_pipeline(owner_id="o", name="Keeper", nodes=[])
        self.ws = self.repo.create_workspace(
            owner_id="o", name="W", workspace_path="/w",
            pipeline_ids=[self.doomed["_id"], self.keeper["_id"]],
        )
        self.asset = self.repo.upsert_asset(
            content_sha256="h", mime_type="image/jpeg", size_bytes=1,
            current_path="/w/a.jpg", workspace_id=self.ws["_id"],
        )
        for pipeline in (self.doomed, self.keeper):
            job, _ = self.repo.ensure_processing_job(
                asset_id=self.asset["_id"], pipeline_id=pipeline["_id"],
                pipeline_version="v1", workspace_id=self.ws["_id"],
            )
            run = self.repo.start_job(job["_id"])
            self.repo.add_model_output(
                asset_id=self.asset["_id"], pipeline_run_id=run["pipeline_run_id"],
                model_name="m", model_version="v", output_type="detections",
                payload={"detections": []}, workspace_id=self.ws["_id"],
                pipeline_id=pipeline["_id"], pipeline_version="v1",
            )
            self.repo.complete_job(job["_id"], run["pipeline_run_id"])

    def _counts(self, pipeline_id):
        return (
            len(list(self.repo.model_outputs.find({"pipeline_id": pipeline_id}))),
            len(list(self.repo.pipeline_runs.find({"pipeline_id": pipeline_id}))),
            len(list(self.repo.processing_jobs.find({"pipeline_id": pipeline_id}))),
        )

    def test_outputs_runs_and_jobs_are_deleted(self):
        self.assertEqual(self._counts(self.doomed["_id"]), (1, 1, 1))
        self.repo.delete_pipeline(self.doomed["_id"])
        self.assertEqual(self._counts(self.doomed["_id"]), (0, 0, 0))

    def test_other_pipelines_are_untouched(self):
        self.repo.delete_pipeline(self.doomed["_id"])
        self.assertEqual(self._counts(self.keeper["_id"]), (1, 1, 1))

    def test_id_is_pulled_from_referencing_workspaces(self):
        self.repo.delete_pipeline(self.doomed["_id"])
        workspace = self.repo.get_workspace(self.ws["_id"])
        self.assertEqual(workspace["pipeline_ids"], [self.keeper["_id"]])

    def test_asset_survives(self):
        self.repo.delete_pipeline(self.doomed["_id"])
        self.assertIsNotNone(self.repo.get_asset(self.asset["_id"]))

    def test_detail_no_longer_lists_the_deleted_pipeline(self):
        self.repo.delete_pipeline(self.doomed["_id"])
        detail = ImageService(self.repo).get_image_detail(self.asset["_id"])
        listed = [p["pipeline_id"] for p in detail["provenance"]["pipelines"]]
        self.assertEqual(listed, [self.keeper["_id"]])


class MemoryRepoArrayMatchTests(unittest.TestCase):
    """The in-memory repo must mirror Mongo's array-contains equality semantics."""

    def test_scalar_query_matches_array_field(self):
        repo = InMemoryPipelineRepository()
        ws = repo.create_workspace(
            owner_id="o", name="W", workspace_path="/w", pipeline_ids=["p1", "p2"],
        )
        found = list(repo.workspace_definitions.find({"pipeline_ids": "p1"}))
        self.assertEqual([w["_id"] for w in found], [ws["_id"]])
        self.assertEqual(list(repo.workspace_definitions.find({"pipeline_ids": "nope"})), [])


if __name__ == "__main__":
    unittest.main()
