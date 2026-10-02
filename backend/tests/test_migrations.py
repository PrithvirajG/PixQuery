"""Migrations must apply exactly once and leave the schema baseline correct.

``_baseline``/``_resync_system_nodes`` used to be ``MongoPipelineRepository(db)``
verbatim; they're now direct calls into the per-collection repositories'
``ensure_indexes``/``seed_system_nodes``. This proves the observable effect
(system nodes seeded, migrations recorded, idempotent on rerun) is unchanged.
"""
import unittest

from src.migrations.runner import MIGRATIONS, applied_migration_ids, run_migrations
from src.repositories.fake_mongo import FakeDatabase
from src.repositories.pipeline_nodes_repository import PipelineNodesRepository


class RunMigrationsTests(unittest.TestCase):
    def setUp(self):
        self.db = FakeDatabase()

    def test_all_migrations_apply_on_a_fresh_database(self):
        ran = run_migrations(self.db)
        self.assertEqual(ran, [m.id for m in MIGRATIONS])
        self.assertEqual(applied_migration_ids(self.db), {m.id for m in MIGRATIONS})

    def test_baseline_seeds_the_system_pipeline_nodes(self):
        run_migrations(self.db)
        nodes = PipelineNodesRepository(self.db)
        system_nodes = [n for n in nodes.list_all() if n["owner_id"] == "system"]
        self.assertIn("object_detection", {n["node_type"] for n in system_nodes})
        self.assertGreaterEqual(len(system_nodes), 9)

    def test_rerunning_is_idempotent(self):
        run_migrations(self.db)
        second_run = run_migrations(self.db)
        self.assertEqual(second_run, [])  # nothing pending — already applied

        # Seeding a second time must not duplicate system nodes.
        nodes = PipelineNodesRepository(self.db)
        object_detection_nodes = [
            n for n in nodes.list_all() if n["node_type"] == "object_detection" and n["owner_id"] == "system"
        ]
        self.assertEqual(len(object_detection_nodes), 1)

    def test_rename_preserves_the_existing_nodes_id_so_pipelines_keep_resolving_it(self):
        # Simulate a pre-rename database: only the old "captioning" row exists,
        # and some pipeline references it by _id (never by node_type).
        run_migrations(self.db)  # seeds with the CURRENT code -> already "vision_language_model"
        nodes_col = self.db["pipeline_nodes"]
        current = nodes_col.find_one({"node_type": "vision_language_model", "owner_id": "system"})
        original_id = current["_id"]
        nodes_col.update_one({"_id": original_id}, {"$set": {"node_type": "captioning"}})
        self.db["schema_migrations"].delete_one({"_id": "0003_rename_captioning_to_vision_language_model"})

        ran = run_migrations(self.db)

        self.assertEqual(ran, ["0003_rename_captioning_to_vision_language_model"])
        renamed = nodes_col.find_one({"node_type": "vision_language_model", "owner_id": "system"})
        self.assertEqual(renamed["_id"], original_id)  # same row, not a new one
        self.assertIsNone(nodes_col.find_one({"node_type": "captioning", "owner_id": "system"}))

    def test_rename_survives_a_process_having_already_seeded_a_fresh_row(self):
        # seed_system_nodes() runs on every process start, independent of
        # migrations — a worker/watcher booted on the new code before this
        # migration ran would already have inserted a brand-new
        # "vision_language_model" row (upsert key is node_type) alongside the
        # original "captioning" row that existing pipelines still reference.
        run_migrations(self.db)
        nodes_col = self.db["pipeline_nodes"]
        current = nodes_col.find_one({"node_type": "vision_language_model", "owner_id": "system"})
        original_id = current["_id"]
        nodes_col.update_one({"_id": original_id}, {"$set": {"node_type": "captioning"}})
        self.db["schema_migrations"].delete_one({"_id": "0003_rename_captioning_to_vision_language_model"})
        PipelineNodesRepository(self.db).seed_system_nodes()  # inserts a fresh duplicate row

        fresh = nodes_col.find_one({"node_type": "vision_language_model", "owner_id": "system"})
        self.assertNotEqual(fresh["_id"], original_id)  # confirms the hazard is real before the fix

        run_migrations(self.db)

        matches = list(nodes_col.find({"node_type": "vision_language_model", "owner_id": "system"}))
        self.assertEqual(len(matches), 1)  # the duplicate was discarded, not left alongside
        self.assertEqual(matches[0]["_id"], original_id)  # the original (pipeline-referenced) row won
        self.assertIsNone(nodes_col.find_one({"_id": fresh["_id"]}))

    def test_rename_is_a_no_op_on_a_fresh_database(self):
        # No "captioning" row ever existed — nothing to migrate.
        ran = run_migrations(self.db)
        self.assertIn("0003_rename_captioning_to_vision_language_model", ran)
        nodes_col = self.db["pipeline_nodes"]
        self.assertEqual(
            nodes_col.count_documents({"node_type": "vision_language_model", "owner_id": "system"}), 1
        )

    def test_migration_records_carry_a_description_and_timestamp(self):
        run_migrations(self.db)
        docs = list(self.db["schema_migrations"].find({}))
        self.assertEqual({d["_id"] for d in docs}, {m.id for m in MIGRATIONS})
        for doc in docs:
            self.assertTrue(doc["description"])
            self.assertIsNotNone(doc["applied_at"])


if __name__ == "__main__":
    unittest.main()
