"""WorkspaceService authorization: owner / editor / viewer / stranger, per operation.

Contract (CLAUDE.md): viewers read-only, editors edit + scan + clear outputs, the
owner alone deletes and manages members. A user with no role gets None/False (the
route turns that into 404) — never an access error, so existence isn't leaked.
"""
import unittest

from src.errors.workspaces import WorkspaceAccessError, WorkspaceValidationError
from src.services.workspace_service import WorkspaceService, role_for
from tests.repo_factory import new_repos


class RbacFixture(unittest.TestCase):
    def setUp(self):
        self.r = new_repos()
        mk = lambda name: self.r.users.create(name, "h")  # noqa: E731
        self.owner, self.editor, self.viewer, self.stranger, self.carol = (
            mk("owner"), mk("editor"), mk("viewer"), mk("stranger"), mk("carol"),
        )
        self.ws = self.r.workspaces.create(
            owner_id=self.owner["_id"], name="W", workspace_path="/w",
            pipeline_ids=["p1"], extensions=[".jpg"], active=True,
        )
        self.r.workspaces.add_member(self.ws["_id"], self.editor["_id"], "editor")
        self.r.workspaces.add_member(self.ws["_id"], self.viewer["_id"], "viewer")
        self.svc = WorkspaceService(
            workspaces=self.r.workspaces, users=self.r.users, assets=self.r.assets,
            observations=self.r.observations, jobs=self.r.jobs, runs=self.r.runs,
            outputs=self.r.outputs,
        )
        self.wid = self.ws["_id"]


class RoleForTests(unittest.TestCase):
    def test_roles(self):
        ws = {"owner_id": "o", "members": [{"user_id": "e", "role": "editor"}, {"user_id": "v"}]}
        self.assertEqual(role_for(ws, "o"), "owner")
        self.assertEqual(role_for(ws, "e"), "editor")
        self.assertEqual(role_for(ws, "v"), "viewer")  # role missing → viewer
        self.assertIsNone(role_for(ws, "x"))


class ReadAccessTests(RbacFixture):
    def test_stranger_cannot_see_the_workspace(self):
        self.assertIsNone(self.svc.get_workspace(self.wid, owner_id=self.stranger["_id"]))

    def test_members_see_it_with_their_role(self):
        for user, role in ((self.owner, "owner"), (self.editor, "editor"), (self.viewer, "viewer")):
            with self.subTest(role=role):
                self.assertEqual(self.svc.get_workspace(self.wid, owner_id=user["_id"])["my_role"], role)

    def test_list_includes_workspaces_shared_with_me(self):
        listed = self.svc.list_workspaces(owner_id=self.viewer["_id"])
        self.assertEqual([(w["_id"], w["my_role"]) for w in listed], [(self.wid, "viewer")])
        self.assertEqual(self.svc.list_workspaces(owner_id=self.stranger["_id"]), [])


class UpdateTests(RbacFixture):
    def test_viewer_cannot_edit(self):
        with self.assertRaises(WorkspaceAccessError):
            self.svc.update_workspace(self.wid, owner_id=self.viewer["_id"], data={"name": "X"})

    def test_editor_can_edit(self):
        updated = self.svc.update_workspace(self.wid, owner_id=self.editor["_id"], data={"name": "X"})
        self.assertEqual(updated["name"], "X")

    def test_stranger_gets_none(self):
        self.assertIsNone(self.svc.update_workspace(self.wid, owner_id=self.stranger["_id"], data={"name": "X"}))

    def test_protected_fields_are_ignored(self):
        # An editor must not be able to take ownership or rewrite membership via update.
        self.svc.update_workspace(
            self.wid, owner_id=self.editor["_id"],
            data={"owner_id": self.editor["_id"], "members": []},
        )
        ws = self.r.workspaces.get(self.wid)
        self.assertEqual(ws["owner_id"], self.owner["_id"])
        self.assertEqual(len(ws["members"]), 2)


class DeleteTests(RbacFixture):
    def test_only_owner_deletes(self):
        for user in (self.editor, self.viewer):
            with self.subTest(user=user["username"]):
                with self.assertRaises(WorkspaceAccessError):
                    self.svc.delete_workspace(self.wid, owner_id=user["_id"])
        self.assertFalse(self.svc.delete_workspace(self.wid, owner_id=self.stranger["_id"]))
        self.assertTrue(self.svc.delete_workspace(self.wid, owner_id=self.owner["_id"]))
        self.assertIsNone(self.r.workspaces.get(self.wid))


class ScanAndClearTests(RbacFixture):
    def test_viewer_cannot_scan(self):
        with self.assertRaises(WorkspaceAccessError):
            self.svc.trigger_scan(self.wid, owner_id=self.viewer["_id"])

    def test_editor_can_scan(self):
        self.assertEqual(self.svc.trigger_scan(self.wid, owner_id=self.editor["_id"])["_id"], self.wid)

    def test_scan_without_pipelines_is_a_validation_error(self):
        self.r.workspaces.update(self.wid, {"pipeline_ids": []})
        with self.assertRaises(WorkspaceValidationError):
            self.svc.trigger_scan(self.wid, owner_id=self.owner["_id"])

    def test_stranger_scan_is_none(self):
        self.assertIsNone(self.svc.trigger_scan(self.wid, owner_id=self.stranger["_id"]))

    def test_viewer_cannot_clear_outputs(self):
        with self.assertRaises(WorkspaceAccessError):
            self.svc.clear_pipeline_outputs(self.wid, "p1", owner_id=self.viewer["_id"])

    def test_editor_clear_returns_counts(self):
        counts = self.svc.clear_pipeline_outputs(self.wid, "p1", owner_id=self.editor["_id"])
        # jobs are intentionally kept (see clear_pipeline_outputs' docstring) so reconciliation regenerates cleared outputs
        self.assertEqual(set(counts), {"outputs_deleted", "runs_deleted"})


class MembershipTests(RbacFixture):
    def test_member_list_starts_with_owner(self):
        members = self.svc.list_members(self.wid, actor_id=self.viewer["_id"])
        self.assertEqual(members[0], {"user_id": self.owner["_id"], "username": "owner", "role": "owner"})
        self.assertEqual({m["username"] for m in members[1:]}, {"editor", "viewer"})

    def test_member_list_hidden_from_strangers(self):
        self.assertIsNone(self.svc.list_members(self.wid, actor_id=self.stranger["_id"]))

    def test_deleted_user_shows_as_unknown(self):
        self.r.workspaces.add_member(self.wid, "ghost-id", "viewer")
        names = [m["username"] for m in self.svc.list_members(self.wid, actor_id=self.owner["_id"])]
        self.assertIn("(unknown)", names)

    def test_only_owner_manages_members(self):
        for call in (
            lambda: self.svc.add_member(self.wid, actor_id=self.editor["_id"], username="carol", role="viewer"),
            lambda: self.svc.update_member_role(self.wid, self.viewer["_id"], actor_id=self.editor["_id"], role="editor"),
            lambda: self.svc.remove_member(self.wid, self.viewer["_id"], actor_id=self.editor["_id"]),
            lambda: self.svc.search_users_for_workspace(self.wid, actor_id=self.viewer["_id"], query="c"),
        ):
            with self.assertRaises(WorkspaceAccessError):
                call()

    def test_add_member(self):
        members = self.svc.add_member(self.wid, actor_id=self.owner["_id"], username="carol", role="editor")
        self.assertIn({"carol": "editor"}, [{m["username"]: m["role"]} for m in members])

    def test_re_adding_changes_role_without_duplicating(self):
        self.svc.add_member(self.wid, actor_id=self.owner["_id"], username="viewer", role="editor")
        roles = [m["role"] for m in self.svc.list_members(self.wid, actor_id=self.owner["_id"]) if m["username"] == "viewer"]
        self.assertEqual(roles, ["editor"])

    def test_add_member_rejections(self):
        cases = {
            "bad role": dict(username="carol", role="owner"),
            "unknown user": dict(username="nobody", role="viewer"),
            "owner themself": dict(username="owner", role="viewer"),
        }
        for label, kwargs in cases.items():
            with self.subTest(case=label):
                with self.assertRaises(ValueError):
                    self.svc.add_member(self.wid, actor_id=self.owner["_id"], **kwargs)

    def test_update_member_role(self):
        members = self.svc.update_member_role(self.wid, self.viewer["_id"], actor_id=self.owner["_id"], role="editor")
        self.assertEqual({m["username"]: m["role"] for m in members}["viewer"], "editor")

    def test_update_role_of_non_member_is_value_error(self):
        with self.assertRaises(ValueError):
            self.svc.update_member_role(self.wid, self.carol["_id"], actor_id=self.owner["_id"], role="editor")

    def test_update_role_to_invalid_role_is_value_error(self):
        with self.assertRaises(ValueError):
            self.svc.update_member_role(self.wid, self.viewer["_id"], actor_id=self.owner["_id"], role="admin")

    def test_remove_member_revokes_access(self):
        self.svc.remove_member(self.wid, self.viewer["_id"], actor_id=self.owner["_id"])
        self.assertIsNone(self.svc.get_workspace(self.wid, owner_id=self.viewer["_id"]))

    def test_user_search_excludes_owner_and_existing_members(self):
        results = self.svc.search_users_for_workspace(self.wid, actor_id=self.owner["_id"], query="")
        self.assertEqual(results, [])
        names = [u["username"] for u in self.svc.search_users_for_workspace(self.wid, actor_id=self.owner["_id"], query="  ")]
        self.assertEqual(names, [])
        found = [u["username"] for u in self.svc.search_users_for_workspace(self.wid, actor_id=self.owner["_id"], query="c")]
        self.assertEqual(found, ["carol"])
        # 'editor', 'viewer', 'owner' are already in the workspace
        self.assertEqual(self.svc.search_users_for_workspace(self.wid, actor_id=self.owner["_id"], query="e"), [])


if __name__ == "__main__":
    unittest.main()
