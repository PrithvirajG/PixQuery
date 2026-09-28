"""/workspaces routes: status-code mapping of the RBAC rules, scan publishing, browse."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.api_client import FakePublisher, auth_headers, build_client, make_user


class WorkspaceRouteFixture(unittest.TestCase):
    def setUp(self):
        FakePublisher.reset()
        self.client, self.r = build_client()
        self.owner = make_user(self.r, "owner")
        self.editor = make_user(self.r, "editor")
        self.viewer = make_user(self.r, "viewer")
        self.stranger = make_user(self.r, "stranger")
        make_user(self.r, "carol")
        self.ws = self.r.workspaces.create(
            owner_id=self.owner["_id"], name="W", workspace_path="/w",
            pipeline_ids=["p1"], extensions=[".jpg"], active=True,
        )
        self.wid = self.ws["_id"]
        self.r.workspaces.add_member(self.wid, self.editor["_id"], "editor")
        self.r.workspaces.add_member(self.wid, self.viewer["_id"], "viewer")
        patcher = mock.patch("src.api.routes.rest.workspaces.RabbitPublisher", FakePublisher)
        patcher.start()
        self.addCleanup(patcher.stop)

    def as_(self, user):
        return auth_headers(user["_id"])


class CrudStatusTests(WorkspaceRouteFixture):
    def test_requires_auth(self):
        self.assertEqual(self.client.get("/workspaces").status_code, 401)

    def test_create_is_201_and_owned_by_caller(self):
        res = self.client.post("/workspaces", json={"name": "N", "workspace_path": "/n"}, headers=self.as_(self.carol_user()))
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()["my_role"], "owner")

    def carol_user(self):
        return self.r.users.get_by_username("carol")

    def test_stranger_gets_404_not_403(self):
        # Review Focus #3: don't leak that the workspace exists.
        res = self.client.get(f"/workspaces/{self.wid}", headers=self.as_(self.stranger))
        self.assertEqual(res.status_code, 404)

    def test_viewer_update_is_403(self):
        res = self.client.put(f"/workspaces/{self.wid}", json={"name": "X"}, headers=self.as_(self.viewer))
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.json()["code"], "forbidden")

    def test_editor_update_is_200(self):
        res = self.client.put(f"/workspaces/{self.wid}", json={"name": "X"}, headers=self.as_(self.editor))
        self.assertEqual((res.status_code, res.json()["name"]), (200, "X"))

    def test_editor_delete_is_403_and_owner_delete_is_204(self):
        self.assertEqual(self.client.delete(f"/workspaces/{self.wid}", headers=self.as_(self.editor)).status_code, 403)
        self.assertEqual(self.client.delete(f"/workspaces/{self.wid}", headers=self.as_(self.owner)).status_code, 204)
        self.assertEqual(self.client.get(f"/workspaces/{self.wid}", headers=self.as_(self.owner)).status_code, 404)

    def test_clear_outputs_status_mapping(self):
        path = f"/workspaces/{self.wid}/pipelines/p1/outputs"
        self.assertEqual(self.client.delete(path, headers=self.as_(self.viewer)).status_code, 403)
        self.assertEqual(self.client.delete(path, headers=self.as_(self.stranger)).status_code, 404)
        self.assertEqual(self.client.delete(path, headers=self.as_(self.editor)).status_code, 200)


class ScanRouteTests(WorkspaceRouteFixture):
    def test_editor_scan_publishes_the_workspace_id(self):
        res = self.client.post(f"/workspaces/{self.wid}/scan", headers=self.as_(self.editor))
        self.assertEqual((res.status_code, res.json()["message"]), (200, "Scan triggered"))
        self.assertEqual(FakePublisher.published, [self.wid])

    def test_viewer_scan_is_403_and_publishes_nothing(self):
        res = self.client.post(f"/workspaces/{self.wid}/scan", headers=self.as_(self.viewer))
        self.assertEqual(res.status_code, 403)
        self.assertEqual(FakePublisher.published, [])

    def test_scan_without_pipelines_is_400(self):
        self.r.workspaces.update(self.wid, {"pipeline_ids": []})
        res = self.client.post(f"/workspaces/{self.wid}/scan", headers=self.as_(self.owner))
        self.assertEqual(res.status_code, 400)

    def test_broker_down_still_returns_200(self):
        # Publishing is best-effort; the file-watcher's refresh loop catches up.
        FakePublisher.fail_connect = True
        res = self.client.post(f"/workspaces/{self.wid}/scan", headers=self.as_(self.owner))
        self.assertEqual(res.status_code, 200)


class MemberRouteTests(WorkspaceRouteFixture):
    def test_viewer_can_list_members(self):
        res = self.client.get(f"/workspaces/{self.wid}/members", headers=self.as_(self.viewer))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()[0]["role"], "owner")

    def test_stranger_member_list_is_404(self):
        self.assertEqual(self.client.get(f"/workspaces/{self.wid}/members", headers=self.as_(self.stranger)).status_code, 404)

    def test_owner_adds_member_201(self):
        res = self.client.post(f"/workspaces/{self.wid}/members", json={"username": "carol", "role": "editor"}, headers=self.as_(self.owner))
        self.assertEqual(res.status_code, 201)

    def test_editor_adding_member_is_403(self):
        # Review Focus #2
        res = self.client.post(f"/workspaces/{self.wid}/members", json={"username": "carol"}, headers=self.as_(self.editor))
        self.assertEqual(res.status_code, 403)

    def test_bad_member_requests_are_400(self):
        bad_role = self.client.post(f"/workspaces/{self.wid}/members", json={"username": "carol", "role": "owner"}, headers=self.as_(self.owner))
        unknown = self.client.post(f"/workspaces/{self.wid}/members", json={"username": "nobody"}, headers=self.as_(self.owner))
        self.assertEqual((bad_role.status_code, unknown.status_code), (400, 400))
        self.assertEqual(unknown.json()["message"], "No user named 'nobody'")

    def test_patch_and_delete_member(self):
        patched = self.client.patch(f"/workspaces/{self.wid}/members/{self.viewer['_id']}", json={"role": "editor"}, headers=self.as_(self.owner))
        self.assertEqual(patched.status_code, 200)
        removed = self.client.delete(f"/workspaces/{self.wid}/members/{self.viewer['_id']}", headers=self.as_(self.owner))
        self.assertEqual(removed.status_code, 200)
        self.assertNotIn(self.viewer["_id"], [m["user_id"] for m in removed.json()])

    def test_user_search(self):
        res = self.client.get(f"/workspaces/{self.wid}/user-search", params={"q": "ca"}, headers=self.as_(self.owner))
        self.assertEqual([u["username"] for u in res.json()], ["carol"])
        self.assertEqual(self.client.get(f"/workspaces/{self.wid}/user-search", params={"q": "ca"}, headers=self.as_(self.viewer)).status_code, 403)


class BrowseRouteTests(WorkspaceRouteFixture):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        (root / "b_dir").mkdir()
        (root / "A_dir").mkdir()
        (root / "file.jpg").write_bytes(b"x")
        self.root = root

    def test_lists_directories_first_case_insensitive(self):
        res = self.client.get("/workspaces/browse", params={"path": str(self.root)}, headers=self.as_(self.owner))
        self.assertEqual([e["name"] for e in res.json()["entries"]], ["A_dir", "b_dir", "file.jpg"])
        self.assertEqual(res.json()["parent"], str(self.root.resolve().parent))

    def test_missing_path_is_404(self):
        res = self.client.get("/workspaces/browse", params={"path": str(self.root / "nope")}, headers=self.as_(self.owner))
        self.assertEqual(res.status_code, 404)

    def test_file_path_is_400(self):
        res = self.client.get("/workspaces/browse", params={"path": str(self.root / "file.jpg")}, headers=self.as_(self.owner))
        self.assertEqual(res.status_code, 400)

    def test_empty_path_lists_roots(self):
        res = self.client.get("/workspaces/browse", headers=self.as_(self.owner))
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["entries"])

    def test_requires_auth(self):
        self.assertEqual(self.client.get("/workspaces/browse").status_code, 401)


if __name__ == "__main__":
    unittest.main()
