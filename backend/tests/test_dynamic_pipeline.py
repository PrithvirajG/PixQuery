"""Unit tests for the dynamic pipeline executor framework.

These exercise orchestration only — executors, the embedding store, and image
loading are faked, so no model weights, numpy, or PIL are required.
"""
import unittest

from src.domain_events import EVENT_PIPELINE_STATE
from src.infrastructure.messaging import EventSink
from src.services.executors import (
    NodeExecutionError,
    PermanentNodeError,
    get_executor,
)
from src.services.pipeline_execution_service import PipelineExecutionService
from tests.repo_factory import new_repos


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
        self.r = new_repos()
        self.recorder = []
        self.store = FakeEmbeddingStore()
        # System nodes are seeded by the repository; map node_type -> id.
        self.node_ids = {
            n["node_type"]: n["_id"]
            for n in self.r.nodes.list_all(owner_id="owner-1")
        }
        self.asset = self.r.assets.upsert(
            content_sha256="hash-1",
            mime_type="image/jpeg",
            size_bytes=10,
            current_path="/tmp/whatever.jpg",
        )

    def _pipeline(self, outputs_by_type):
        return PipelineExecutionService(
            jobs=self.r.jobs, runs=self.r.runs, outputs=self.r.outputs, assets=self.r.assets,
            pipelines=self.r.pipelines, nodes=self.r.nodes,
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
        return self.r.pipelines.create(owner_id="owner-1", name="P", nodes=nodes)

    def _job_for(self, pipeline_id, version="v-test"):
        job, _ = self.r.jobs.get_or_create(
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
        self._pipeline(outputs).run_job(job["_id"])

        # Nodes ran in declared order.
        self.assertEqual([nt for nt, _ in self.recorder],
                         ["object_detection", "captioning", "embedding"])
        # Job completed.
        self.assertEqual(self.r.jobs.get(job["_id"])["status"], "completed")

        stored = list(self.r.outputs.collection.find({"asset_id": self.asset["_id"]}))
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
        self._pipeline(outputs).run_job(job["_id"])

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
        self._pipeline(outputs).run_job(job["_id"])

        self.assertEqual([nt for nt, _ in self.recorder],
                         ["object_detection", "captioning", "embedding"])
        self.assertEqual(self.r.jobs.get(job["_id"])["status"], "completed")

    def test_missing_required_input_fails_job(self):
        # A node that needs a "detections" input, run first (nothing produced it),
        # must fail clearly rather than silently skip.
        node = self.r.nodes.create(
            name="Needs Detections", description="", node_type="needs_detections",
            context_inputs=["detections"], context_outputs=["image"],
            config_schema={}, default_config={}, owner_id="owner-1",
        )
        nodes = [{"node_id": "n0", "pipeline_node_id": node["_id"],
                  "order": 0, "config_overrides": {}}]
        definition = self.r.pipelines.create(owner_id="owner-1", name="P", nodes=nodes)
        job = self._job_for(definition["_id"])

        pipeline = self._pipeline({"needs_detections": {"image": "X"}})
        with self.assertRaises(PermanentNodeError):
            pipeline.run_job(job["_id"])

        # A missing required input is a config error — it can never succeed on
        # retry, so the job is failed outright (not requeued) with the cause.
        failed_job = self.r.jobs.get(job["_id"])
        self.assertEqual(failed_job["status"], "failed")
        self.assertIsNone(failed_job["next_attempt_at"])
        self.assertIn("detections", failed_job["last_error"]["message"])

    def test_transient_failure_retries_three_times_then_marks_failed(self):
        # Mirrors the old god-repository's ProcessingRetryTests, now against
        # PipelineExecutionService's own retry policy (RETRY_DELAYS/MAX_ATTEMPTS)
        # rather than the repository's.
        definition = self._make_definition(["object_detection"])
        job = self._job_for(definition["_id"])

        class AlwaysFails:
            node_type = "object_detection"
            model_name = "m"
            model_version = "v"

            def run(self, context, config):
                raise RuntimeError("transient boom")

        pipeline = PipelineExecutionService(
            jobs=self.r.jobs, runs=self.r.runs, outputs=self.r.outputs, assets=self.r.assets,
            pipelines=self.r.pipelines, nodes=self.r.nodes,
            get_executor=lambda nt: AlwaysFails(),
            image_loader=lambda asset: "FAKE_IMAGE",
        )

        statuses = []
        for _ in range(3):
            with self.assertRaises(RuntimeError):
                pipeline.run_job(job["_id"])
            statuses.append(self.r.jobs.get(job["_id"])["status"])

        self.assertEqual(statuses, ["queued", "queued", "failed"])
        final = self.r.jobs.get(job["_id"])
        self.assertEqual(final["attempt_count"], 3)
        self.assertIsNone(final["next_attempt_at"])
        self.assertEqual(final["last_error"]["message"], "transient boom")

    def test_retryable_failure_emits_queued_not_failed(self):
        # Mirrors test_events.py's old JobLifecycleEventTests coverage of the
        # god-repository's fail_job emission, now against
        # PipelineExecutionService's own _emit_state.
        definition = self._make_definition(["object_detection"])
        job = self._job_for(definition["_id"])

        class Fails:
            node_type = "object_detection"
            model_name = "m"
            model_version = "v"

            def run(self, context, config):
                raise RuntimeError("boom")

        events = []
        sink = EventSink()
        sink.set(events.append)
        pipeline = PipelineExecutionService(
            jobs=self.r.jobs, runs=self.r.runs, outputs=self.r.outputs, assets=self.r.assets,
            pipelines=self.r.pipelines, nodes=self.r.nodes,
            get_executor=lambda nt: Fails(),
            image_loader=lambda asset: "FAKE_IMAGE",
            event_sink=sink,
        )

        with self.assertRaises(RuntimeError):
            pipeline.run_job(job["_id"])

        states = [e.data["state"] for e in events if e.type == EVENT_PIPELINE_STATE]
        # processing (job start), then queued (retry pending) — not failed.
        self.assertEqual(states, ["processing", "queued"])

    def test_permanent_failure_emits_failed_with_the_message(self):
        node = self.r.nodes.create(
            name="Needs Detections", description="", node_type="needs_detections",
            context_inputs=["detections"], context_outputs=["image"],
            config_schema={}, default_config={}, owner_id="owner-1",
        )
        nodes = [{"node_id": "n0", "pipeline_node_id": node["_id"], "order": 0, "config_overrides": {}}]
        definition = self.r.pipelines.create(owner_id="owner-1", name="P", nodes=nodes)
        job = self._job_for(definition["_id"])

        events = []
        sink = EventSink()
        sink.set(events.append)
        pipeline = PipelineExecutionService(
            jobs=self.r.jobs, runs=self.r.runs, outputs=self.r.outputs, assets=self.r.assets,
            pipelines=self.r.pipelines, nodes=self.r.nodes,
            get_executor=lambda nt: FakeExecutor(nt, {}, self.recorder),
            image_loader=lambda asset: "FAKE_IMAGE",
            event_sink=sink,
        )

        with self.assertRaises(PermanentNodeError):
            pipeline.run_job(job["_id"])

        state_events = [e for e in events if e.type == EVENT_PIPELINE_STATE]
        self.assertEqual(state_events[-1].data["state"], "failed")
        self.assertIn("detections", state_events[-1].data["error"]["message"])

    def test_config_overrides_merge_over_node_defaults(self):
        nodes = [
            {
                "node_id": "n0",
                "pipeline_node_id": self.node_ids["object_detection"],
                "order": 0,
                "config_overrides": {"threshold": 0.9},
            }
        ]
        definition = self.r.pipelines.create(owner_id="owner-1", name="P", nodes=nodes)
        job = self._job_for(definition["_id"])

        self._pipeline({"object_detection": {"detections": []}}).run_job(job["_id"])

        _, config = self.recorder[0]
        # default model from the seeded node + overridden threshold.
        self.assertEqual(config["model"], "yolov8n")
        self.assertEqual(config["threshold"], 0.9)


if __name__ == "__main__":
    unittest.main()
