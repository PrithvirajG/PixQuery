"""System pipeline nodes must track the executors, not freeze at first seed.

Seeding originally used ``$setOnInsert`` for every field, so a node written by an
older build kept that build's schema forever. Face Detection ended up advertising
``min_confidence`` (a YOLO knob its executor never reads) while hiding the three
it does read — the editor showed a control that did nothing.
"""
import unittest

from src.repositories import InMemoryPipelineRepository
from src.repositories.mongo_pipeline import MongoPipelineRepository


def _spec(node_type):
    return next(n for n in MongoPipelineRepository._SYSTEM_NODES if n["node_type"] == node_type)


class SystemNodeSeedTests(unittest.TestCase):
    def setUp(self):
        self.repo = InMemoryPipelineRepository()

    def _node(self, node_type):
        return self.repo.pipeline_nodes_col.find_one(
            {"node_type": node_type, "owner_id": "system"}
        )

    def test_face_detection_advertises_the_knobs_its_executor_reads(self):
        node = self._node("face_detection")
        self.assertEqual(
            set(node["config_schema"]), {"scale_factor", "min_neighbors", "min_size"}
        )
        # The stale schema's key must be gone — it did nothing.
        self.assertNotIn("min_confidence", node["config_schema"])

    def test_face_detection_declares_the_port_its_executor_emits(self):
        # Executor returns {"detections": [...]}, so the declared output port must
        # match or DAG edge wiring (from_output/to_input) silently breaks.
        self.assertEqual(self._node("face_detection")["context_outputs"], ["detections"])

    def test_stale_managed_fields_are_corrected_on_reseed(self):
        # Simulate a node frozen by an older build.
        self.repo.pipeline_nodes_col.update_one(
            {"node_type": "face_detection", "owner_id": "system"},
            {"$set": {
                "config_schema": {"min_confidence": {"type": "number"}},
                "default_config": {"min_confidence": 0.8},
                "context_outputs": ["faces"],
                "description": "stale",
            }},
        )
        self.repo._seed_system_nodes()

        node = self._node("face_detection")
        spec = _spec("face_detection")
        self.assertEqual(node["config_schema"], spec["config_schema"])
        self.assertEqual(node["default_config"], spec["default_config"])
        self.assertEqual(node["context_outputs"], spec["context_outputs"])
        self.assertEqual(node["description"], spec["description"])

    def test_reseed_keeps_node_identity_stable(self):
        # Pipelines reference nodes by _id; reseeding must not orphan them.
        before = self._node("face_detection")["_id"]
        self.repo._seed_system_nodes()
        self.assertEqual(self._node("face_detection")["_id"], before)

    def test_reseed_does_not_duplicate_nodes(self):
        for _ in range(3):
            self.repo._seed_system_nodes()
        found = [
            n for n in self.repo.pipeline_nodes_col.find({"owner_id": "system"})
            if n["node_type"] == "face_detection"
        ]
        self.assertEqual(len(found), 1)

    def test_every_system_node_matches_its_spec(self):
        for spec in MongoPipelineRepository._SYSTEM_NODES:
            with self.subTest(node_type=spec["node_type"]):
                node = self._node(spec["node_type"])
                self.assertIsNotNone(node)
                for field in MongoPipelineRepository._SYSTEM_NODE_MANAGED_FIELDS:
                    self.assertEqual(node[field], spec[field])


if __name__ == "__main__":
    unittest.main()
