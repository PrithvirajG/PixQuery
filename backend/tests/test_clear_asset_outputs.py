"""RBAC for clearing one pipeline's outputs for a single image.

Cascade-depth coverage lives in test_workspace_clear_outputs_cascade.py; the
workspace-wide sibling's RBAC is covered in test_clear_pipeline_outputs.py. This
file is about who is allowed to trigger the per-image clear.
"""
import unittest

from src.errors.workspaces import WorkspaceAccessError
from src.services.workspace_service import WorkspaceService
from tests.repo_factory import new_repos


def _workspace_service(r):
    return WorkspaceService(
        workspaces=r.workspaces, users=r.users, assets=r.assets, observations=r.observations,
        jobs=r.jobs, runs=r.runs, outputs=r.outputs,
    )


def _seed_processed_asset(r, *, sha, path, workspace_id, pipeline_id):
    """An asset that has been through one pipeline and has an output to show for it."""
    asset = r.assets.upsert(
        content_sha256=sha, mime_type="image/jpeg", size_bytes=5,
        current_path=path, workspace_id=workspace_id,
    )
    job, _ = r.jobs.get_or_create(
        asset_id=asset["_id"], pipeline_id=pipeline_id, pipeline_version="v1", workspace_id=workspace_id,
    )
    r.jobs.start(job["_id"])
    run = r.runs.create(
        job_id=job["_id"], asset_id=asset["_id"], pipeline_id=pipeline_id, pipeline_version="v1",
    )
    r.outputs.add(
        asset_id=asset["_id"], pipeline_run_id=run["_id"],
        model_name="yolo", model_version="v8n", output_type="detections",
        payload={"detections": [{"label": "car"}]},
        workspace_id=workspace_id, pipeline_id=pipeline_id, pipeline_version="v1",
    )
    r.jobs.complete(job["_id"])
    return asset, job


class ClearAssetPipelineOutputsServiceTests(unittest.TestCase):
    """Role enforcement — same rules as the workspace-wide clear."""

    def setUp(self):
        self.r = new_repos()
        self.service = _workspace_service(self.r)
        self.workspace = self.r.workspaces.create(
            owner_id="owner-1", name="A", workspace_path="/photos",
        )
        self.asset, _ = _seed_processed_asset(
            self.r, sha="h1", path="/photos/a.jpg",
            workspace_id=self.workspace["_id"], pipeline_id="p1",
        )

    def test_owner_may_clear(self):
        result = self.service.clear_asset_pipeline_outputs(
            self.asset["_id"], "p1", owner_id="owner-1"
        )
        self.assertEqual(result["outputs_deleted"], 1)

    def test_editor_may_clear(self):
        self.r.workspaces.add_member(self.workspace["_id"], "editor-1", "editor")
        result = self.service.clear_asset_pipeline_outputs(
            self.asset["_id"], "p1", owner_id="editor-1"
        )
        self.assertEqual(result["outputs_deleted"], 1)

    def test_viewer_is_refused(self):
        self.r.workspaces.add_member(self.workspace["_id"], "viewer-1", "viewer")
        with self.assertRaises(WorkspaceAccessError):
            self.service.clear_asset_pipeline_outputs(
                self.asset["_id"], "p1", owner_id="viewer-1"
            )
        # Refused means nothing was deleted, not "raised after the damage".
        self.assertEqual(
            len(list(self.r.outputs.collection.find({"asset_id": self.asset["_id"]}))), 1
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
