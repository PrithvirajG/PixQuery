"""Direct tests for the 9 per-collection repositories.

These construct each repository straight against ``FakeDatabase`` — no facade,
no InMemoryXRepository subclass needed, since a per-collection repository is
just ``database["name"]`` plus named methods, and FakeDatabase/FakeCollection
already emulate a pymongo collection generically. Coverage here favours the
places behavior changed versus the old god-repository (retry policy stripped
out of the job repo) and the seams between repositories (ids returned by one
delete feeding the next), since the straightforward CRUD methods are thin
wrappers unlikely to hide bugs.
"""

import unittest

from src.repositories.fake_mongo import FakeDatabase
from src.repositories.file_observations_repository import FileObservationsRepository
from src.repositories.image_assets_repository import ImageAssetsRepository
from src.repositories.model_outputs_repository import ModelOutputsRepository
from src.repositories.pipeline_definitions_repository import PipelineDefinitionsRepository
from src.repositories.pipeline_nodes_repository import PipelineNodesRepository
from src.repositories.pipeline_runs_repository import PipelineRunsRepository
from src.repositories.processing_jobs_repository import ProcessingJobsRepository
from src.repositories.users_repository import UsersRepository
from src.repositories.workspace_definitions_repository import WorkspaceDefinitionsRepository


def make_db():
    return FakeDatabase()


class ImageAssetsRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.repo = ImageAssetsRepository(make_db())

    def test_upsert_creates_then_updates_same_asset(self):
        first = self.repo.upsert(
            content_sha256="h1", mime_type="image/jpeg", size_bytes=10,
            current_path="/a.jpg", workspace_id="ws1",
        )
        second = self.repo.upsert(
            content_sha256="h1", mime_type="image/jpeg", size_bytes=20,
            current_path="/a-renamed.jpg", workspace_id="ws1",
        )
        self.assertEqual(first["_id"], second["_id"])
        self.assertEqual(self.repo.get(first["_id"])["current_path"], "/a-renamed.jpg")

    def test_same_content_different_workspace_is_a_different_asset(self):
        a = self.repo.upsert(
            content_sha256="h1", mime_type="image/jpeg", size_bytes=10,
            current_path="/a.jpg", workspace_id="ws1",
        )
        b = self.repo.upsert(
            content_sha256="h1", mime_type="image/jpeg", size_bytes=10,
            current_path="/a.jpg", workspace_id="ws2",
        )
        self.assertNotEqual(a["_id"], b["_id"])

    def test_list_by_ids_only_returns_active_by_default(self):
        a = self.repo.upsert(content_sha256="h1", mime_type=None, size_bytes=1, current_path="/a.jpg")
        b = self.repo.upsert(content_sha256="h2", mime_type=None, size_bytes=1, current_path="/b.jpg")
        self.repo.set_active(b["_id"], False)
        results = self.repo.list_by_ids([a["_id"], b["_id"]])
        self.assertEqual([r["_id"] for r in results], [a["_id"]])

    def test_claim_unowned_only_touches_assets_without_an_owner(self):
        owned = self.repo.upsert(
            content_sha256="h1", mime_type=None, size_bytes=1, current_path="/a.jpg", owner_id="u0"
        )
        unowned = self.repo.upsert(content_sha256="h2", mime_type=None, size_bytes=1, current_path="/b.jpg")
        claimed = self.repo.claim_unowned("u1")
        self.assertEqual(claimed, 1)
        self.assertEqual(self.repo.get(owned["_id"])["owner_id"], "u0")
        self.assertEqual(self.repo.get(unowned["_id"])["owner_id"], "u1")


class FileObservationsRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.repo = FileObservationsRepository(make_db())

    def test_mark_missing_leaves_present_paths_active(self):
        self.repo.upsert(asset_id="a1", workspace_id="ws1", relative_path="keep.jpg",
                          absolute_path="/ws1/keep.jpg", content_sha256="h1")
        self.repo.upsert(asset_id="a2", workspace_id="ws1", relative_path="gone.jpg",
                          absolute_path="/ws1/gone.jpg", content_sha256="h2")
        self.repo.mark_missing("ws1", {"keep.jpg"})
        statuses = {o["relative_path"]: o["status"] for o in self.repo.list_for_workspace("ws1")}
        self.assertEqual(statuses, {"keep.jpg": "active", "gone.jpg": "missing"})

    def test_distinct_active_asset_ids_excludes_missing(self):
        self.repo.upsert(asset_id="a1", workspace_id="ws1", relative_path="keep.jpg",
                          absolute_path="/ws1/keep.jpg", content_sha256="h1")
        self.repo.upsert(asset_id="a2", workspace_id="ws1", relative_path="gone.jpg",
                          absolute_path="/ws1/gone.jpg", content_sha256="h2")
        self.repo.mark_missing("ws1", {"keep.jpg"})
        self.assertEqual(self.repo.distinct_active_asset_ids(), {"a1"})

    def test_list_active_for_workspace_falls_back_to_legacy_watch_root_id(self):
        # Simulate an observation recorded before the workspace_id rename: it only
        # carries watch_root_id, so the legacy fallback is what makes it visible.
        self.repo.collection.insert_one({
            "_id": "obs-legacy", "asset_id": "a3", "watch_root_id": "old-root-id",
            "status": "active", "relative_path": "legacy.jpg",
        })
        found = self.repo.list_active_for_workspace("ws-new", legacy_watch_root_id="old-root-id")
        self.assertEqual([o["asset_id"] for o in found], ["a3"])


class ProcessingJobsRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.repo = ProcessingJobsRepository(make_db())

    def test_get_or_create_is_idempotent_for_the_same_key(self):
        job1, created1 = self.repo.get_or_create(
            asset_id="a1", pipeline_id="p1", pipeline_version="v1", workspace_id="ws1"
        )
        job2, created2 = self.repo.get_or_create(
            asset_id="a1", pipeline_id="p1", pipeline_version="v1", workspace_id="ws1"
        )
        self.assertTrue(created1)
        self.assertFalse(created2)
        self.assertEqual(job1["_id"], job2["_id"])

    def test_start_increments_attempt_count_and_marks_processing(self):
        job, _ = self.repo.get_or_create(asset_id="a1", pipeline_id="p1", pipeline_version="v1")
        started = self.repo.start(job["_id"])
        self.assertEqual(started["status"], "processing")
        self.assertEqual(started["attempt_count"], 1)

    def test_start_on_unknown_job_raises(self):
        with self.assertRaises(ValueError):
            self.repo.start("does-not-exist")

    def test_fail_takes_the_decided_outcome_without_computing_any_policy(self):
        """The repository no longer knows about retry delays or max attempts —
        it just persists whatever final_status/next_attempt_at it's given."""
        job, _ = self.repo.get_or_create(asset_id="a1", pipeline_id="p1", pipeline_version="v1")
        self.repo.start(job["_id"])
        self.repo.fail(
            job["_id"],
            final_status="queued",
            next_attempt_at="sentinel-value-not-interpreted",
            error={"class": "ValueError", "message": "boom"},
        )
        stored = self.repo.get(job["_id"])
        self.assertEqual(stored["status"], "queued")
        self.assertEqual(stored["next_attempt_at"], "sentinel-value-not-interpreted")
        self.assertEqual(stored["last_error"]["message"], "boom")

    def test_delete_for_workspace_pipeline_returns_deleted_ids(self):
        job, _ = self.repo.get_or_create(
            asset_id="a1", pipeline_id="p1", pipeline_version="v1", workspace_id="ws1"
        )
        ids, count = self.repo.delete_for_workspace_pipeline("ws1", "p1")
        self.assertEqual(ids, [job["_id"]])
        self.assertEqual(count, 1)
        self.assertIsNone(self.repo.get(job["_id"]))


class PipelineRunsRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.repo = PipelineRunsRepository(make_db())

    def test_delete_for_jobs_only_removes_matching_runs(self):
        r1 = self.repo.create(job_id="j1", asset_id="a1", pipeline_id="p1", pipeline_version="v1")
        self.repo.create(job_id="j2", asset_id="a1", pipeline_id="p1", pipeline_version="v1")
        deleted = self.repo.delete_for_jobs(["j1"])
        self.assertEqual(deleted, 1)
        remaining = self.repo.list_for_job("j2")
        self.assertEqual(len(remaining), 1)
        self.assertIsNone(self.repo.get(r1["_id"]))

    def test_update_status_sets_finished_at_and_error(self):
        run = self.repo.create(job_id="j1", asset_id="a1", pipeline_id="p1", pipeline_version="v1")
        self.repo.update_status(run["_id"], status="failed", finished_at="t1", error={"message": "x"})
        stored = self.repo.get(run["_id"])
        self.assertEqual(stored["status"], "failed")
        self.assertEqual(stored["error"]["message"], "x")


class ModelOutputsRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.repo = ModelOutputsRepository(make_db())

    def test_list_by_type_only_returns_matching_outputs(self):
        self.repo.add(asset_id="a1", pipeline_run_id="r1", model_name="blip",
                       model_version="v1", output_type="caption", payload={"text": "a cat"})
        self.repo.add(asset_id="a1", pipeline_run_id="r1", model_name="yolo",
                       model_version="v1", output_type="detections", payload={"detections": []})
        captions = self.repo.list_by_type("caption")
        self.assertEqual(len(captions), 1)
        self.assertEqual(captions[0]["payload"]["text"], "a cat")

    def test_delete_for_runs_scopes_to_the_given_run_ids(self):
        self.repo.add(asset_id="a1", pipeline_run_id="r1", model_name="blip",
                       model_version="v1", output_type="caption", payload={"text": "x"})
        self.repo.add(asset_id="a1", pipeline_run_id="r2", model_name="blip",
                       model_version="v1", output_type="caption", payload={"text": "y"})
        deleted = self.repo.delete_for_runs(["r1"])
        self.assertEqual(deleted, 1)
        self.assertEqual(len(self.repo.list_for_asset("a1")), 1)


class UsersRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.repo = UsersRepository(make_db())

    def test_search_by_username_prefix_excludes_given_ids(self):
        a = self.repo.create("alice", "hash")
        self.repo.create("alicia", "hash")
        results = self.repo.search_by_username_prefix("ali", exclude_ids={a["_id"]})
        self.assertEqual([r["username"] for r in results], ["alicia"])

    def test_count_reflects_created_users(self):
        self.assertEqual(self.repo.count(), 0)
        self.repo.create("alice", "hash")
        self.assertEqual(self.repo.count(), 1)


class PipelineDefinitionsRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.repo = PipelineDefinitionsRepository(make_db())

    def test_count_for_owner_scopes_correctly(self):
        self.repo.create(owner_id="u1", name="p1")
        self.repo.create(owner_id="u1", name="p2")
        self.repo.create(owner_id="u2", name="p3")
        self.assertEqual(self.repo.count_for_owner("u1"), 2)
        self.assertEqual(self.repo.count_for_owner("u2"), 1)

    def test_update_stamps_updated_at_and_protects_identity_fields(self):
        pipeline = self.repo.create(owner_id="u1", name="p1")
        updated = self.repo.update(pipeline["_id"], {"_id": "hijack", "owner_id": "u2", "name": "renamed"})
        self.assertEqual(updated["_id"], pipeline["_id"])
        self.assertEqual(updated["owner_id"], "u1")
        self.assertEqual(updated["name"], "renamed")
        self.assertIsNotNone(updated["updated_at"])


class PipelineNodesRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.repo = PipelineNodesRepository(make_db())

    def test_seed_system_nodes_is_idempotent(self):
        self.repo.seed_system_nodes()
        self.repo.seed_system_nodes()
        system_nodes = [n for n in self.repo.list_all() if n["owner_id"] == "system"]
        node_types = [n["node_type"] for n in system_nodes]
        self.assertEqual(len(node_types), len(set(node_types)))
        self.assertIn("object_detection", node_types)

    def test_list_all_with_owner_includes_system_and_own_nodes(self):
        self.repo.seed_system_nodes()
        self.repo.create(
            name="custom", description="", node_type="custom_type",
            context_inputs=[], context_outputs=[], config_schema={}, default_config={},
            owner_id="u1",
        )
        owners = {n["owner_id"] for n in self.repo.list_all(owner_id="u1")}
        self.assertEqual(owners, {"system", "u1"})

    def test_list_all_without_owner_returns_only_system(self):
        self.repo.seed_system_nodes()
        self.repo.create(
            name="custom", description="", node_type="custom_type",
            context_inputs=[], context_outputs=[], config_schema={}, default_config={},
            owner_id="u1",
        )
        owners = {n["owner_id"] for n in self.repo.list_all()}
        self.assertEqual(owners, {"system"})

    def _system_node(self, node_type):
        return self.repo.collection.find_one({"node_type": node_type, "owner_id": "system"})

    def _spec(self, node_type):
        return next(n for n in self.repo._SYSTEM_NODES if n["node_type"] == node_type)

    def test_stale_managed_fields_are_corrected_on_reseed(self):
        # Mirrors test_system_node_seed.py's coverage of the god-repository's
        # _seed_system_nodes, now against this repository's own copy of it.
        self.repo.seed_system_nodes()
        self.repo.collection.update_one(
            {"node_type": "face_detection", "owner_id": "system"},
            {"$set": {
                "config_schema": {"min_confidence": {"type": "number"}},
                "default_config": {"min_confidence": 0.8},
                "context_outputs": ["faces"],
                "description": "stale",
            }},
        )

        self.repo.seed_system_nodes()

        node = self._system_node("face_detection")
        spec = self._spec("face_detection")
        self.assertEqual(node["config_schema"], spec["config_schema"])
        self.assertEqual(node["default_config"], spec["default_config"])
        self.assertEqual(node["context_outputs"], spec["context_outputs"])
        self.assertEqual(node["description"], spec["description"])

    def test_reseed_keeps_node_identity_stable(self):
        # Pipelines reference nodes by _id; reseeding must not orphan them.
        self.repo.seed_system_nodes()
        before = self._system_node("face_detection")["_id"]

        self.repo.seed_system_nodes()

        self.assertEqual(self._system_node("face_detection")["_id"], before)

    def test_reseed_does_not_duplicate_nodes(self):
        for _ in range(3):
            self.repo.seed_system_nodes()
        found = [
            n for n in self.repo.list_all() if n["node_type"] == "face_detection" and n["owner_id"] == "system"
        ]
        self.assertEqual(len(found), 1)

    def test_every_system_node_matches_its_spec(self):
        self.repo.seed_system_nodes()
        for spec in self.repo._SYSTEM_NODES:
            with self.subTest(node_type=spec["node_type"]):
                node = self._system_node(spec["node_type"])
                self.assertIsNotNone(node)
                for field in self.repo._SYSTEM_NODE_MANAGED_FIELDS:
                    self.assertEqual(node[field], spec[field])


class WorkspaceDefinitionsRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.repo = WorkspaceDefinitionsRepository(make_db())

    def test_list_for_owner_includes_membership_not_just_ownership(self):
        owned = self.repo.create(owner_id="u1", name="mine", workspace_path="/a")
        shared = self.repo.create(owner_id="u2", name="shared", workspace_path="/b")
        self.repo.add_member(shared["_id"], "u1", "viewer")
        visible_ids = {w["_id"] for w in self.repo.list_for_owner("u1")}
        self.assertEqual(visible_ids, {owned["_id"], shared["_id"]})

    def test_remove_pipeline_id_only_removes_the_given_id(self):
        ws = self.repo.create(
            owner_id="u1", name="ws", workspace_path="/a", pipeline_ids=["p1", "p2"]
        )
        self.repo.remove_pipeline_id(ws["_id"], "p1")
        self.assertEqual(self.repo.get(ws["_id"])["pipeline_ids"], ["p2"])

    def test_set_member_role_fails_for_a_non_member(self):
        ws = self.repo.create(owner_id="u1", name="ws", workspace_path="/a")
        result = self.repo.set_member_role(ws["_id"], "not-a-member", "editor")
        self.assertIsNone(result)

    def test_add_member_then_remove_member_round_trips(self):
        ws = self.repo.create(owner_id="u1", name="ws", workspace_path="/a")
        self.repo.add_member(ws["_id"], "u2", "viewer")
        self.assertEqual(len(self.repo.get(ws["_id"])["members"]), 1)
        self.repo.remove_member(ws["_id"], "u2")
        self.assertEqual(len(self.repo.get(ws["_id"])["members"]), 0)

    def test_scalar_query_matches_array_field(self):
        # FakeDatabase must mirror Mongo's array-contains equality semantics —
        # this repository's list_for_owner and delete_pipeline's referencing-
        # workspace lookup both rely on {"pipeline_ids": some_id} matching a doc
        # whose pipeline_ids array contains that id.
        ws = self.repo.create(owner_id="o", name="W", workspace_path="/w", pipeline_ids=["p1", "p2"])
        found = list(self.repo.collection.find({"pipeline_ids": "p1"}))
        self.assertEqual([w["_id"] for w in found], [ws["_id"]])
        self.assertEqual(list(self.repo.collection.find({"pipeline_ids": "nope"})), [])


if __name__ == "__main__":
    unittest.main()
