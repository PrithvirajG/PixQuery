"""WorkspaceService.delete_workspace's cascade.

Unlike delete_pipeline and clear_*_outputs, this cascade had no direct test
coverage before the per-collection migration — neither at the old
god-repository level nor through the service. Covers it now: an asset with no
observation left anywhere is fully swept (jobs, outputs, runs, the asset
itself); an asset still observed by another workspace (a legacy shared asset)
survives untouched.
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


class DeleteWorkspaceCascadeTests(unittest.TestCase):
    def setUp(self):
        self.r = new_repos()
        self.ws = self.r.workspaces.create(owner_id="owner-1", name="A", workspace_path="/a")
        self.asset = self.r.assets.upsert(
            content_sha256="h1", mime_type="image/jpeg", size_bytes=5,
            current_path="/a/photo.jpg", workspace_id=self.ws["_id"],
        )
        self.r.observations.upsert(
            asset_id=self.asset["_id"], workspace_id=self.ws["_id"],
            relative_path="photo.jpg", absolute_path="/a/photo.jpg", content_sha256="h1",
        )
        job, _ = self.r.jobs.get_or_create(
            asset_id=self.asset["_id"], pipeline_id="p1", pipeline_version="v1",
            workspace_id=self.ws["_id"],
        )
        self.r.jobs.start(job["_id"])
        run = self.r.runs.create(
            job_id=job["_id"], asset_id=self.asset["_id"], pipeline_id="p1", pipeline_version="v1",
        )
        self.r.outputs.add(
            asset_id=self.asset["_id"], pipeline_run_id=run["_id"],
            model_name="m", model_version="v", output_type="detections",
            payload={"detections": []}, workspace_id=self.ws["_id"],
            pipeline_id="p1", pipeline_version="v1",
        )
        self.job_id = job["_id"]

    def test_deletes_the_workspace(self):
        deleted = _workspace_service(self.r).delete_workspace(self.ws["_id"], owner_id="owner-1")
        self.assertTrue(deleted)
        self.assertIsNone(self.r.workspaces.get(self.ws["_id"]))

    def test_asset_with_no_remaining_observation_is_fully_swept(self):
        _workspace_service(self.r).delete_workspace(self.ws["_id"], owner_id="owner-1")

        self.assertIsNone(self.r.assets.get(self.asset["_id"]))
        self.assertEqual(self.r.observations.list_for_asset(self.asset["_id"]), [])
        self.assertEqual(self.r.jobs.list_for_asset(self.asset["_id"]), [])
        self.assertEqual(list(self.r.outputs.collection.find({"asset_id": self.asset["_id"]})), [])
        self.assertEqual(self.r.runs.list_for_asset(self.asset["_id"]), [])

    def test_asset_still_observed_by_another_workspace_survives(self):
        other_ws = self.r.workspaces.create(owner_id="owner-1", name="B", workspace_path="/b")
        # Legacy shared asset: same asset, a second observation in another workspace.
        self.r.observations.upsert(
            asset_id=self.asset["_id"], workspace_id=other_ws["_id"],
            relative_path="photo.jpg", absolute_path="/b/photo.jpg", content_sha256="h1",
        )

        _workspace_service(self.r).delete_workspace(self.ws["_id"], owner_id="owner-1")

        self.assertIsNotNone(self.r.assets.get(self.asset["_id"]))
        self.assertEqual(len(list(self.r.outputs.collection.find({"asset_id": self.asset["_id"]}))), 1)
        # Only this workspace's observation is gone; the other workspace's remains.
        remaining_obs = self.r.observations.list_for_asset(self.asset["_id"])
        self.assertEqual([o["workspace_id"] for o in remaining_obs], [other_ws["_id"]])

    def test_other_workspaces_assets_are_untouched(self):
        other_ws = self.r.workspaces.create(owner_id="owner-1", name="B", workspace_path="/b")
        other_asset = self.r.assets.upsert(
            content_sha256="h2", mime_type="image/jpeg", size_bytes=5,
            current_path="/b/x.jpg", workspace_id=other_ws["_id"],
        )
        self.r.observations.upsert(
            asset_id=other_asset["_id"], workspace_id=other_ws["_id"],
            relative_path="x.jpg", absolute_path="/b/x.jpg", content_sha256="h2",
        )

        _workspace_service(self.r).delete_workspace(self.ws["_id"], owner_id="owner-1")

        self.assertIsNotNone(self.r.assets.get(other_asset["_id"]))

    def test_editor_cannot_delete_only_owner_can(self):
        self.r.workspaces.add_member(self.ws["_id"], "editor-1", "editor")
        with self.assertRaises(WorkspaceAccessError):
            _workspace_service(self.r).delete_workspace(self.ws["_id"], owner_id="editor-1")
        self.assertIsNotNone(self.r.workspaces.get(self.ws["_id"]))

    def test_stranger_gets_false_not_a_permission_error(self):
        deleted = _workspace_service(self.r).delete_workspace(self.ws["_id"], owner_id="stranger")
        self.assertFalse(deleted)
        self.assertIsNotNone(self.r.workspaces.get(self.ws["_id"]))

    def test_unknown_workspace_returns_false(self):
        self.assertFalse(_workspace_service(self.r).delete_workspace("nope", owner_id="owner-1"))


if __name__ == "__main__":
    unittest.main()
