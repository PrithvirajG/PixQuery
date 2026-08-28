"""Tests for clearing one pipeline's outputs for a single image.

The workspace-wide sibling is covered in test_clear_pipeline_outputs.py; what
matters here is that the blast radius really is one image, and that the pair ends
up in a state the UI will offer to run again.
"""
import unittest

from src.services.image_service import _pipeline_state
from src.repositories import InMemoryPipelineRepository
from src.services.workspace_service import WorkspaceAccessError, WorkspaceService


def _seed_processed_asset(repo, *, sha, path, workspace_id, pipeline_id):
    """An asset that has been through one pipeline and has an output to show for it."""
    asset = repo.upsert_asset(
        content_sha256=sha,
        mime_type="image/jpeg",
        size_bytes=5,
        current_path=path,
        workspace_id=workspace_id,
    )
    job, _ = repo.ensure_processing_job(
        asset_id=asset["_id"],
        pipeline_id=pipeline_id,
        pipeline_version="v1",
        workspace_id=workspace_id,
    )
    run = repo.start_job(job["_id"])
    repo.add_model_output(
        asset_id=asset["_id"],
        pipeline_run_id=run["pipeline_run_id"],
        model_name="yolo",
        model_version="v8n",
        output_type="detections",
        payload={"detections": [{"label": "car"}]},
        workspace_id=workspace_id,
        pipeline_id=pipeline_id,
        pipeline_version="v1",
    )
    repo.complete_job(job["_id"], run["pipeline_run_id"])
    return asset, job


class ClearAssetPipelineOutputsRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.repo = InMemoryPipelineRepository()
        self.asset, self.job = _seed_processed_asset(
            self.repo, sha="h1", path="/photos/a.jpg",
            workspace_id="ws-a", pipeline_id="p1",
        )
        # A second image in the same workspace, same pipeline — the control.
        self.other_asset, self.other_job = _seed_processed_asset(
            self.repo, sha="h2", path="/photos/b.jpg",
            workspace_id="ws-a", pipeline_id="p1",
        )

    def test_reports_what_it_deleted(self):
        result = self.repo.clear_asset_pipeline_outputs(self.asset["_id"], "p1")
        self.assertEqual(
            result, {"outputs_deleted": 1, "runs_deleted": 1, "jobs_deleted": 1}
        )

    def test_leaves_other_images_in_the_same_workspace_alone(self):
        self.repo.clear_asset_pipeline_outputs(self.asset["_id"], "p1")

        self.assertEqual(
            list(self.repo.model_outputs.find({"asset_id": self.asset["_id"]})), []
        )
        survivors = list(self.repo.model_outputs.find({"asset_id": self.other_asset["_id"]}))
        self.assertEqual(len(survivors), 1)
        self.assertEqual(self.repo.get_job(self.other_job["_id"])["status"], "completed")

    def test_leaves_other_pipelines_on_the_same_image_alone(self):
        job, _ = self.repo.ensure_processing_job(
            asset_id=self.asset["_id"], pipeline_id="p2",
            pipeline_version="v1", workspace_id="ws-a",
        )
        run = self.repo.start_job(job["_id"])
        self.repo.add_model_output(
            asset_id=self.asset["_id"], pipeline_run_id=run["pipeline_run_id"],
            model_name="blip", model_version="v1", output_type="caption",
            payload={"text": "a cat"}, workspace_id="ws-a",
            pipeline_id="p2", pipeline_version="v1",
        )
        self.repo.complete_job(job["_id"], run["pipeline_run_id"])

        self.repo.clear_asset_pipeline_outputs(self.asset["_id"], "p1")

        remaining = list(self.repo.model_outputs.find({"asset_id": self.asset["_id"]}))
        self.assertEqual([o["pipeline_id"] for o in remaining], ["p2"])

    def test_the_pair_returns_to_not_started(self):
        self.repo.clear_asset_pipeline_outputs(self.asset["_id"], "p1")
        # No job row is exactly how the detail view derives NOT_STARTED, which is
        # what re-enables the Process button.
        self.assertIsNone(self.repo.get_job(self.job["_id"]))
        self.assertEqual(_pipeline_state(None, []), "not_started")

    def test_sweeps_outputs_that_predate_the_denormalized_pipeline_id(self):
        """Older rows carry no pipeline_id and are reachable only via their run."""
        run = self.repo.pipeline_runs.find_one({"job_id": self.job["_id"]})
        self.repo.model_outputs.insert_one({
            "_id": "legacy-1",
            "asset_id": self.asset["_id"],
            "pipeline_run_id": run["_id"],
            "pipeline_id": None,
            "output_type": "caption",
            "payload": {"text": "old"},
        })

        self.repo.clear_asset_pipeline_outputs(self.asset["_id"], "p1")

        self.assertIsNone(self.repo.model_outputs.find_one({"_id": "legacy-1"}))

    def test_clearing_an_untouched_pair_is_a_harmless_no_op(self):
        result = self.repo.clear_asset_pipeline_outputs(self.asset["_id"], "never-ran")
        self.assertEqual(
            result, {"outputs_deleted": 0, "runs_deleted": 0, "jobs_deleted": 0}
        )


class ClearAssetPipelineOutputsServiceTests(unittest.TestCase):
    """Role enforcement — same rules as the workspace-wide clear."""

    def setUp(self):
        self.repo = InMemoryPipelineRepository()
        self.service = WorkspaceService(self.repo)
        self.workspace = self.repo.create_workspace(
            owner_id="owner-1", name="A", workspace_path="/photos",
        )
        self.asset, _ = _seed_processed_asset(
            self.repo, sha="h1", path="/photos/a.jpg",
            workspace_id=self.workspace["_id"], pipeline_id="p1",
        )

    def test_owner_may_clear(self):
        result = self.service.clear_asset_pipeline_outputs(
            self.asset["_id"], "p1", owner_id="owner-1"
        )
        self.assertEqual(result["outputs_deleted"], 1)

    def test_editor_may_clear(self):
        self.repo.add_workspace_member(self.workspace["_id"], "editor-1", "editor")
        result = self.service.clear_asset_pipeline_outputs(
            self.asset["_id"], "p1", owner_id="editor-1"
        )
        self.assertEqual(result["outputs_deleted"], 1)

    def test_viewer_is_refused(self):
        self.repo.add_workspace_member(self.workspace["_id"], "viewer-1", "viewer")
        with self.assertRaises(WorkspaceAccessError):
            self.service.clear_asset_pipeline_outputs(
                self.asset["_id"], "p1", owner_id="viewer-1"
            )
        # Refused means nothing was deleted, not "raised after the damage".
        self.assertEqual(
            len(list(self.repo.model_outputs.find({"asset_id": self.asset["_id"]}))), 1
        )

    def test_a_stranger_gets_not_found_rather_than_a_permissions_hint(self):
        """Absence of access reads as absence of the image — don't confirm it exists."""
        self.assertIsNone(
            self.service.clear_asset_pipeline_outputs(
                self.asset["_id"], "p1", owner_id="stranger"
            )
        )

    def test_unknown_asset_is_not_found(self):
        self.assertIsNone(
            self.service.clear_asset_pipeline_outputs("nope", "p1", owner_id="owner-1")
        )


if __name__ == "__main__":
    unittest.main()
