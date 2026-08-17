"""Unit tests for the dynamic pipeline executor framework.

These exercise orchestration only — executors, the embedding store, and image
loading are faked, so no model weights, numpy, or PIL are required.
"""
import unittest

from src.pipelines.processing.executors import (
    NodeExecutionError,
    PermanentNodeError,
    get_executor,
)
from src.pipelines.processing.pipeline import DynamicPipeline
from src.repositories import InMemoryPipelineRepository


class FakeExecutor:
    def __init__(self, node_type, outputs, recorder):
        self.node_type = node_type
        self.model_name = f"{node_type}-model"
        self.model_version = "test"
        self._outputs = outputs
        self._recorder = recorder

    def run(self, context, config):
        self._recorder.append((self.node_type, dict(config)))
        return dict(self._outputs)


def make_get_executor(outputs_by_type, recorder):
    def _get(node_type):
        if node_type not in outputs_by_type:
            raise NodeExecutionError(f"no fake executor for {node_type}")
        return FakeExecutor(node_type, outputs_by_type[node_type], recorder)

    return _get


class FakeEmbeddingStore:
    def __init__(self):
        self.image_upserts = []
        self.text_upserts = []

    def upsert_image_embedding(self, *, vector, properties):
        self.image_upserts.append((vector, properties))

    def upsert_text_embedding(self, *, vector, properties):
        self.text_upserts.append((vector, properties))


class RegistryTests(unittest.TestCase):
    def test_known_node_returns_cached_instance(self):
        executor = get_executor("object_detection")
        self.assertEqual(executor.node_type, "object_detection")
        self.assertIs(get_executor("object_detection"), executor)

    def test_all_seeded_node_types_resolve(self):
        # Every seeded node type — including face_detection and classification —
        # now has an executor (construction is lazy, so no models load here).
        for node_type in ("face_detection", "classification", "ocr", "image_write"):
            self.assertEqual(get_executor(node_type).node_type, node_type)

    def test_unknown_node_raises_permanent(self):
        with self.assertRaises(PermanentNodeError):
            get_executor("does_not_exist")


class DynamicPipelineTests(unittest.TestCase):
    def setUp(self):
        self.repo = InMemoryPipelineRepository()
        self.recorder = []
        self.store = FakeEmbeddingStore()
        # System nodes are seeded by the repository; map node_type -> id.
        self.node_ids = {
            n["node_type"]: n["_id"]
            for n in self.repo.list_pipeline_nodes(owner_id="owner-1")
        }
        self.asset = self.repo.upsert_asset(
            content_sha256="hash-1",
            mime_type="image/jpeg",
            size_bytes=10,
            current_path="/tmp/whatever.jpg",
        )

    def _pipeline(self, outputs_by_type):
        return DynamicPipeline(
            embedding_store=self.store,
            get_executor=make_get_executor(outputs_by_type, self.recorder),
            image_loader=lambda asset: "FAKE_IMAGE",
        )

    def _make_definition(self, node_types):
        nodes = [
            {
                "node_id": f"n{i}",
                "pipeline_node_id": self.node_ids[nt],
                "order": i,
                "config_overrides": {},
            }
            for i, nt in enumerate(node_types)
        ]
        return self.repo.create_pipeline(owner_id="owner-1", name="P", nodes=nodes)

    def _job_for(self, pipeline_id, version="v-test"):
        job, _ = self.repo.ensure_processing_job(
            asset_id=self.asset["_id"],
            pipeline_id=pipeline_id,
            pipeline_version=version,
        )
        return job

    def test_runs_definition_nodes_in_order_and_persists_outputs(self):
        definition = self._make_definition(["object_detection", "captioning", "embedding"])
        job = self._job_for(definition["_id"])

        outputs = {
            "object_detection": {"detections": [{"label": "cat", "confidence": 0.9, "bbox": [1, 2, 3, 4]}]},
            "captioning": {"caption": "a cat"},
            "embedding": {"embeddings": [3.0, 4.0], "text_embedding": [0.0, 5.0]},
        }
        self._pipeline(outputs).run_job(self.repo, job["_id"])

        # Nodes ran in declared order.
        self.assertEqual([nt for nt, _ in self.recorder],
                         ["object_detection", "captioning", "embedding"])
        # Job completed.
        self.assertEqual(self.repo.get_job(job["_id"])["status"], "completed")

        stored = list(self.repo.model_outputs.find({"asset_id": self.asset["_id"]}))
        by_type = {o["output_type"]: o for o in stored}
        # Caption + detections persisted in their historical shapes.
        self.assertEqual(by_type["caption"]["payload"], {"text": "a cat"})
        self.assertEqual(by_type["detections"]["payload"]["detections"][0]["label"], "cat")
        # Per-node provenance recorded.
        self.assertEqual(by_type["caption"]["node_type"], "captioning")
        self.assertEqual(by_type["detections"]["order"], 0)
        # Embeddings are NOT stored as model_outputs.
        self.assertNotIn("embeddings", by_type)
        self.assertNotIn("text_embedding", by_type)

    def test_embeddings_are_normalized_and_upserted(self):
        definition = self._make_definition(["captioning", "embedding"])
        job = self._job_for(definition["_id"])
        outputs = {
            "captioning": {"caption": "hello"},
            "embedding": {"embeddings": [3.0, 4.0], "text_embedding": [0.0, 2.0]},
        }
        self._pipeline(outputs).run_job(self.repo, job["_id"])

        self.assertEqual(len(self.store.image_upserts), 1)
        vector, props = self.store.image_upserts[0]
        self.assertAlmostEqual(vector[0], 0.6)
        self.assertAlmostEqual(vector[1], 0.8)
        self.assertEqual(props["pipeline_id"], definition["_id"])
        # Text embedding carries the caption text.
        self.assertEqual(len(self.store.text_upserts), 1)
        self.assertEqual(self.store.text_upserts[0][1]["text"], "hello")

    def test_default_chain_used_when_pipeline_has_no_definition(self):
        # Legacy pipeline id with no stored definition → DEFAULT_PIPELINE_NODES.
        job = self._job_for("default_image_analysis", version="v1")
        outputs = {
            "object_detection": {"detections": []},
            "captioning": {"caption": "x"},
            "embedding": {"embeddings": [1.0]},
        }
        self._pipeline(outputs).run_job(self.repo, job["_id"])

        self.assertEqual([nt for nt, _ in self.recorder],
                         ["object_detection", "captioning", "embedding"])
        self.assertEqual(self.repo.get_job(job["_id"])["status"], "completed")

    def test_missing_required_input_fails_job(self):
        # A node that needs a "detections" input, run first (nothing produced it),
        # must fail clearly rather than silently skip.
        node = self.repo.create_pipeline_node(
            name="Needs Detections", description="", node_type="needs_detections",
            context_inputs=["detections"], context_outputs=["image"],
            config_schema={}, default_config={}, owner_id="owner-1",
        )
        nodes = [{"node_id": "n0", "pipeline_node_id": node["_id"],
                  "order": 0, "config_overrides": {}}]
        definition = self.repo.create_pipeline(owner_id="owner-1", name="P", nodes=nodes)
        job = self._job_for(definition["_id"])

        pipeline = self._pipeline({"needs_detections": {"image": "X"}})
        with self.assertRaises(PermanentNodeError):
            pipeline.run_job(self.repo, job["_id"])

        # A missing required input is a config error — it can never succeed on
        # retry, so the job is failed outright (not requeued) with the cause.
        failed_job = self.repo.get_job(job["_id"])
        self.assertEqual(failed_job["status"], "failed")
        self.assertIsNone(failed_job["next_attempt_at"])
        self.assertIn("detections", failed_job["last_error"]["message"])

    def test_config_overrides_merge_over_node_defaults(self):
        nodes = [
            {
                "node_id": "n0",
                "pipeline_node_id": self.node_ids["object_detection"],
                "order": 0,
                "config_overrides": {"threshold": 0.9},
            }
        ]
        definition = self.repo.create_pipeline(owner_id="owner-1", name="P", nodes=nodes)
        job = self._job_for(definition["_id"])

        self._pipeline({"object_detection": {"detections": []}}).run_job(self.repo, job["_id"])

        _, config = self.recorder[0]
        # default model from the seeded node + overridden threshold.
        self.assertEqual(config["model"], "yolov8n")
        self.assertEqual(config["threshold"], 0.9)


if __name__ == "__main__":
    unittest.main()
