"""RBAC for bulk-clearing one pipeline's outputs within one workspace.

Cascade-depth coverage lives in test_workspace_clear_outputs_cascade.py; this
file is about who is allowed to trigger the clear.
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


class ClearPipelineOutputsPermissionTests(unittest.TestCase):
    def setUp(self):
        self.r = new_repos()
        self.service = _workspace_service(self.r)
        self.ws = self.r.workspaces.create(owner_id="owner-1", name="A", workspace_path="/a")

    def test_owner_can_clear(self):
        result = self.service.clear_pipeline_outputs(self.ws["_id"], "p1", owner_id="owner-1")
        self.assertEqual(result, {"outputs_deleted": 0, "runs_deleted": 0, "jobs_deleted": 0})

    def test_viewer_denied(self):
        self.r.workspaces.update(
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
