"""Model selection per pipeline node: advertised by executors, chosen per node.

The executor classes are the single source of truth for which models a node type
can run. These tests pin the three places that truth flows through: the node
library API response (what the editor's Model dropdown shows), pipeline saves
(an unsupported model is rejected up front), and the pipeline version hash (a
model change reprocesses; the field's mere existence doesn't).
"""
import asyncio
import unittest

from fastapi import HTTPException

from src.errors.pipelines import PipelineValidationError
from src.repositories.pipeline_nodes_repository import PipelineNodesRepository
from src.services.executors.registry import _EXECUTOR_CLASSES, describe_node_type
from src.services.pipeline_service import PipelineService
from src.services.pipeline_versioning import pipeline_version_hash
from tests.repo_factory import new_repos


def _service(r):
    return PipelineService(
        pipelines=r.pipelines, nodes=r.nodes, runs=r.runs, outputs=r.outputs,
        jobs=r.jobs, workspaces=r.workspaces,
    )


class ExecutorCatalogTests(unittest.TestCase):
    def test_every_model_node_advertises_a_valid_default(self):
        for node_type, cls in _EXECUTOR_CLASSES.items():
            with self.subTest(node_type=node_type):
                if cls.kind == "model":
                    self.assertTrue(cls.models)
                    self.assertIn(cls.default_model, {m.id for m in cls.models})
                else:
                    self.assertEqual(cls.models, ())
                    self.assertIsNone(cls.default_model)

    def test_model_ids_are_unique_per_node_type(self):
        for node_type, cls in _EXECUTOR_CLASSES.items():
            with self.subTest(node_type=node_type):
                ids = [m.id for m in cls.models]
                self.assertEqual(len(ids), len(set(ids)))

    def test_design_model_lists(self):
        def labels(node_type):
            return [m["label"] for m in describe_node_type(node_type)["models"]]

        self.assertEqual(labels("object_detection"), ["YOLOv8n", "YOLOv8s", "YOLOv8m"])
        self.assertEqual(labels("face_detection"), ["YuNet", "SCRFD", "RetinaFace-R50"])
        self.assertEqual(labels("classification"), ["ResNet-50", "EfficientNet-B0", "ViT-B/16"])
        self.assertEqual(labels("embedding"), ["CLIP ViT-B/32", "CLIP ViT-L/14", "DINOv2"])

    def test_embedding_model_specs_catalog(self):
        from src.services.executors import embedding_model_specs

        specs = {spec.id: spec for spec in embedding_model_specs()}
        self.assertEqual(set(specs), {"clip", "clip_vit_l14", "dinov2"})
        # Only DINOv2 lacks a text tower — the one fact search relies on to
        # build a query encoder (and so a Weaviate class to search) per model.
        self.assertEqual(specs["clip"].supports_text, True)
        self.assertEqual(specs["clip_vit_l14"].supports_text, True)
        self.assertEqual(specs["dinov2"].supports_text, False)

    def test_embedding_model_node_type_kind_and_outputs_label(self):
        desc = describe_node_type("embedding")
        self.assertEqual(desc["kind"], "model")
        self.assertEqual(desc["executor"], "EmbeddingExecutor")
        self.assertEqual(desc["default_model"], "clip")

    def test_describe_does_not_instantiate_executors(self):
        from src.services.executors import registry

        before = dict(registry._INSTANCES)
        describe_node_type("face_detection")
        self.assertEqual(registry._INSTANCES, before)

    def test_seeded_nodes_carry_no_model_config(self):
        # The model is a node field now, not a config key the JSON editor shows.
        for spec in PipelineNodesRepository._SYSTEM_NODES:
            with self.subTest(node_type=spec["node_type"]):
                self.assertNotIn("model", spec["default_config"])
                self.assertNotIn("model", spec["config_schema"])


class NodeLibraryResponseTests(unittest.TestCase):
    def setUp(self):
        self.r = new_repos()
        self.service = _service(self.r)

    def test_each_node_carries_its_executor_description(self):
        nodes = {n["node_type"]: n for n in self.service.list_pipeline_nodes(owner_id="u")}
        face = nodes["face_detection"]
        self.assertEqual(face["kind"], "model")
        self.assertEqual(face["executor"], "FaceDetectionExecutor")
        self.assertEqual(face["outputs_label"], "bounding boxes")
        self.assertEqual(face["default_model"], "retinaface_r50")
        self.assertEqual(
            face["models"][0], {"id": "yunet", "label": "YuNet", "supports_prompt": False}
        )
        resize = nodes["resize"]
        self.assertEqual((resize["kind"], resize["models"]), ("transform", []))

    def test_vision_language_model_exposes_which_models_take_a_prompt(self):
        # The inspector needs this to decide whether to show the Prompt field
        # for whichever model is currently selected — unlike supports_text
        # (Embedding), this one genuinely has to reach the frontend.
        nodes = {n["node_type"]: n for n in self.service.list_pipeline_nodes(owner_id="u")}
        vlm = nodes["vision_language_model"]
        self.assertEqual(vlm["default_model"], "blip")
        by_id = {m["id"]: m["supports_prompt"] for m in vlm["models"]}
        self.assertEqual(by_id, {"blip": False, "qwen2_vl_2b": True, "moondream2": True})

    def test_single_node_lookup_is_enriched_too(self):
        node_id = next(
            n["_id"] for n in self.service.list_pipeline_nodes(owner_id="u")
            if n["node_type"] == "classification"
        )
        self.assertEqual(self.service.get_pipeline_node(node_id)["default_model"], "efficientnet_b0")


class PipelineModelValidationTests(unittest.TestCase):
    def setUp(self):
        self.r = new_repos()
        self.service = _service(self.r)
        self.node_ids = {
            n["node_type"]: n["_id"] for n in self.r.nodes.list_all()
        }

    def _create(self, node_type, model):
        return self.service.create_pipeline(
            owner_id="u",
            data={"name": "P", "nodes": [
                {"pipeline_node_id": self.node_ids[node_type], "model": model},
            ]},
        )

    def test_supported_model_is_stored_on_the_node(self):
        pipeline = self._create("face_detection", "scrfd")
        self.assertEqual(pipeline["nodes"][0]["model"], "scrfd")

    def test_no_model_is_stored_as_none(self):
        pipeline = self._create("face_detection", None)
        self.assertIsNone(pipeline["nodes"][0]["model"])

    def test_unsupported_model_is_rejected(self):
        with self.assertRaises(PipelineValidationError):
            self._create("face_detection", "yolov8n")  # a real model, wrong node type

    def test_model_on_a_transform_node_is_rejected(self):
        with self.assertRaises(PipelineValidationError):
            self._create("resize", "yolov8n")

    def test_update_validates_too(self):
        pipeline = self._create("object_detection", "yolov8s")
        with self.assertRaises(PipelineValidationError):
            self.service.update_pipeline(
                pipeline["_id"], owner_id="u",
                data={"nodes": [
                    {"pipeline_node_id": self.node_ids["object_detection"], "model": "nope"},
                ]},
            )


class VersionHashTests(unittest.TestCase):
    NODE = {"node_id": "n0", "pipeline_node_id": "p0", "config_overrides": {}}

    def test_unset_model_hashes_like_a_node_from_before_the_field_existed(self):
        self.assertEqual(
            pipeline_version_hash([{**self.NODE, "model": None}]),
            pipeline_version_hash([self.NODE]),
        )

    def test_choosing_a_model_changes_the_version(self):
        a = pipeline_version_hash([{**self.NODE, "model": "yunet"}])
        b = pipeline_version_hash([{**self.NODE, "model": "scrfd"}])
        self.assertNotEqual(a, b)
        self.assertNotEqual(a, pipeline_version_hash([self.NODE]))


class _StubYolo:
    def detect(self, image, write_image, conf=None):
        return [{"label": "person", "confidence": 0.9, "bbox": [1, 2, 3, 4]}]


class ModelProvenanceThroughAJobTests(unittest.TestCase):
    """The chosen model must end up on the stored model_outputs row."""

    def setUp(self):
        from src.services.executors.builtin import ObjectDetectionExecutor
        from src.services.pipeline_execution_service import PipelineExecutionService

        self.r = new_repos()
        self.executor = ObjectDetectionExecutor()
        for spec in ObjectDetectionExecutor.models:
            self.executor._models[spec.id] = _StubYolo()
        self.service = PipelineExecutionService(
            jobs=self.r.jobs, runs=self.r.runs, outputs=self.r.outputs, assets=self.r.assets,
            pipelines=self.r.pipelines, nodes=self.r.nodes,
            get_executor=lambda node_type: self.executor,
            image_loader=lambda asset: "FAKE_IMAGE",
        )
        self.node_id = next(
            n["_id"] for n in self.r.nodes.list_all() if n["node_type"] == "object_detection"
        )
        self.asset = self.r.assets.upsert(
            content_sha256="h", mime_type="image/jpeg", size_bytes=1, current_path="/x.jpg",
        )

    def _run(self, model):
        pipeline = self.r.pipelines.create(
            owner_id="u", name="P",
            nodes=[{"node_id": "n0", "pipeline_node_id": self.node_id,
                    "config_overrides": {}, "model": model}],
        )
        job, _ = self.r.jobs.get_or_create(
            asset_id=self.asset["_id"], pipeline_id=pipeline["_id"], pipeline_version="v",
        )
        self.service.run_job(job["_id"])
        (output,) = [o for o in self.r.outputs.list_for_asset(self.asset["_id"])
                     if o["output_type"] == "detections"]
        return output

    def test_chosen_model_is_recorded(self):
        output = self._run("yolov8s")
        self.assertEqual((output["model_name"], output["model_version"]), ("yolov8s", "ultralytics-v8"))

    def test_unset_model_records_the_default(self):
        self.assertEqual(self._run(None)["model_name"], "yolov8n")

    def test_default_pipeline_nodes_carry_no_model_config(self):
        from src.services.pipeline_execution_service import DEFAULT_PIPELINE_NODES

        for node in DEFAULT_PIPELINE_NODES:
            with self.subTest(node_type=node["node_type"]):
                self.assertNotIn("model", node["config"])


class PipelineRouteModelTests(unittest.TestCase):
    """Route layer: `model` is accepted in the request body; a bad one is a 400."""

    def setUp(self):
        self.r = new_repos()
        self.service = _service(self.r)
        self.user = {"_id": "u"}
        self.face_id = next(
            n["_id"] for n in self.r.nodes.list_all() if n["node_type"] == "face_detection"
        )

    def _create(self, model):
        from src.api.routes.rest.pipelines import PipelineCreate, PipelineNodeRef, create_pipeline

        body = PipelineCreate(
            name="P", nodes=[PipelineNodeRef(pipeline_node_id=self.face_id, model=model)]
        )
        return asyncio.run(
            create_pipeline(body=body, pipeline_service=self.service, current_user=self.user)
        )

    def test_create_accepts_and_returns_the_model(self):
        self.assertEqual(self._create("yunet")["nodes"][0]["model"], "yunet")

    def test_create_with_unsupported_model_is_400(self):
        with self.assertRaises(HTTPException) as ctx:
            self._create("not-a-model")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_update_with_unsupported_model_is_400(self):
        from src.api.routes.rest.pipelines import PipelineNodeRef, PipelineUpdate, update_pipeline

        pipeline = self._create("yunet")
        body = PipelineUpdate(
            nodes=[PipelineNodeRef(pipeline_node_id=self.face_id, model="yolov8n")]
        )
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(update_pipeline(
                pipeline_id=pipeline["_id"], body=body,
                pipeline_service=self.service, current_user=self.user,
            ))
        self.assertEqual(ctx.exception.status_code, 400)

    def test_node_library_route_returns_model_lists(self):
        from src.api.routes.rest.pipeline_nodes import list_pipeline_nodes

        nodes = asyncio.run(
            list_pipeline_nodes(pipeline_service=self.service, current_user=self.user)
        )
        by_type = {n["node_type"]: n for n in nodes}
        self.assertEqual(len(by_type["object_detection"]["models"]), 3)
        self.assertEqual(by_type["grayscale"]["models"], [])


if __name__ == "__main__":
    unittest.main()
