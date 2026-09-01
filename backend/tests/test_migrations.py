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

    def test_migration_records_carry_a_description_and_timestamp(self):
        run_migrations(self.db)
        docs = list(self.db["schema_migrations"].find({}))
        self.assertEqual({d["_id"] for d in docs}, {m.id for m in MIGRATIONS})
        for doc in docs:
            self.assertTrue(doc["description"])
            self.assertIsNotNone(doc["applied_at"])


if __name__ == "__main__":
    unittest.main()
