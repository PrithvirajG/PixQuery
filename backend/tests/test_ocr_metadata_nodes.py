"""Tests for the OCR and metadata-extraction nodes (P4).

The executors themselves need pytesseract / Pillow, which aren't available here,
so model execution is faked. The pure EXIF mapping, registry wiring, persisted
output shapes, and OCR-aware keyword search are all covered without heavy deps.
"""
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from src.pipelines.processing.executors import get_executor
from src.pipelines.processing.executors.builtin import (
    _dms_to_decimal,
    _exif_to_dict,
    _gps_to_dict,
)
from src.pipelines.processing.pipeline import DynamicPipeline, _shape_output
from src.repositories import InMemoryPipelineRepository
from src.services.search_service import SearchService


class RegistryAndShapeTests(unittest.TestCase):
    def test_registry_returns_ocr_executor(self):
        self.assertEqual(get_executor("ocr").node_type, "ocr")

    def test_ocr_text_persisted_as_ocr_output(self):
        self.assertEqual(_shape_output("ocr_text", "INVOICE 42"), ("ocr", {"text": "INVOICE 42"}))

    def test_metadata_persisted_generically(self):
        meta = {"width": 10, "height": 20}
        self.assertEqual(_shape_output("metadata", meta), ("metadata", {"metadata": meta}))


class ExifMappingTests(unittest.TestCase):
    def test_maps_known_tags_and_strips_strings(self):
        raw = {271: "Canon ", 272: "EOS", 306: "2024:01:02 03:04:05", 99999: "ignored"}
        out = _exif_to_dict(raw)
        self.assertEqual(out["camera_make"], "Canon")
        self.assertEqual(out["camera_model"], "EOS")
        self.assertEqual(out["datetime"], "2024:01:02 03:04:05")
        self.assertNotIn(99999, out)

    def test_skips_empty_values(self):
        self.assertEqual(_exif_to_dict({271: "", 272: None}), {})


class GpsExtractionTests(unittest.TestCase):
    def test_dms_to_decimal_signs_by_hemisphere(self):
        # 40°44'54.36" N  →  +40.7484
        self.assertAlmostEqual(_dms_to_decimal((40, 44, 54.36), "N"), 40.7484, places=4)
        # 73°59'8.5" W  →  negative (western hemisphere)
        self.assertAlmostEqual(_dms_to_decimal((73, 59, 8.5), "W"), -73.98569, places=4)

    def test_gps_ifd_maps_to_lat_long(self):
        gps = {1: "N", 2: (10, 30, 0), 3: "E", 4: (20, 15, 0)}
        out = _gps_to_dict(gps)
        self.assertAlmostEqual(out["gps_latitude"], 10.5, places=4)
        self.assertAlmostEqual(out["gps_longitude"], 20.25, places=4)

    def test_missing_or_malformed_gps_is_skipped(self):
        self.assertEqual(_gps_to_dict({}), {})
        self.assertEqual(_gps_to_dict({2: "garbage", 1: "N"}), {})


class OcrPersistenceAndSearchTests(unittest.TestCase):
    def setUp(self):
        self.repo = InMemoryPipelineRepository()
        self.node_ids = {
            n["node_type"]: n["_id"]
            for n in self.repo.list_pipeline_nodes(owner_id="owner-1")
        }
        self.asset = self.repo.upsert_asset(
            content_sha256="h1", mime_type="image/jpeg", size_bytes=5,
            current_path="/photos/scan.png",
        )

    def test_ocr_node_output_persisted_and_searchable(self):
        # Pipeline with just the OCR node; fake executor returns recognized text.
        nodes = [{
            "node_id": "n0",
            "pipeline_node_id": self.node_ids["ocr"],
            "order": 0,
            "config_overrides": {},
        }]
        definition = self.repo.create_pipeline(owner_id="owner-1", name="ocr", nodes=nodes)
        job, _ = self.repo.ensure_processing_job(
            asset_id=self.asset["_id"], pipeline_id=definition["_id"], pipeline_version="v",
        )

        class FakeOcr:
            node_type = "ocr"
            model_name = "tesseract"
            model_version = "pytesseract"
            def run(self, context, config):
                return {"ocr_text": "Quarterly Revenue Report 2024"}

        pipeline = DynamicPipeline(
            get_executor=lambda nt: FakeOcr(),
            image_loader=lambda asset: "IMG",
        )
        pipeline.run_job(self.repo, job["_id"])

        # Persisted under output_type "ocr" with text payload.
        stored = list(self.repo.model_outputs.find({"asset_id": self.asset["_id"]}))
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0]["output_type"], "ocr")
        self.assertEqual(stored[0]["payload"]["text"], "Quarterly Revenue Report 2024")
        self.assertEqual(stored[0]["node_type"], "ocr")

        # Searchable by recognized text, with an "ocr" match field.
        results = SearchService(self.repo).search(query="revenue", mode="keyword")
        self.assertEqual([r["_id"] for r in results], [self.asset["_id"]])
        self.assertIn("ocr", results[0]["match_reason"]["fields"])


class MetadataPipelineSettingTests(unittest.TestCase):
    """EXIF extraction is a pipeline-wide setting, not a node."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.img = Path(self.tmp.name) / "p.png"
        Image.new("RGB", (12, 7), "green").save(self.img)
        self.repo = InMemoryPipelineRepository()
        self.asset = self.repo.upsert_asset(
            content_sha256="h", mime_type="image/png", size_bytes=1,
            current_path=str(self.img),
        )
        # A no-op node so the empty-pipeline default chain doesn't kick in.
        self.noop = self.repo.create_pipeline_node(
            name="Noop", description="", node_type="noop",
            context_inputs=["image"], context_outputs=[],
            config_schema={}, default_config={}, owner_id="o",
        )

    def tearDown(self):
        self.tmp.cleanup()

    def _run(self, extract_metadata):
        nodes = [{"node_id": "n0", "pipeline_node_id": self.noop["_id"],
                  "order": 0, "config_overrides": {}}]
        pipeline_def = self.repo.create_pipeline(
            owner_id="o", name="P", nodes=nodes, extract_metadata=extract_metadata,
        )
        job, _ = self.repo.ensure_processing_job(
            asset_id=self.asset["_id"], pipeline_id=pipeline_def["_id"], pipeline_version="v",
        )

        class FakeNoop:
            node_type = "noop"
            model_name = "noop"
            model_version = "v"
            def run(self, context, config):
                return {}

        DynamicPipeline(
            get_executor=lambda nt: FakeNoop(),
            image_loader=lambda a: "IMG",
        ).run_job(self.repo, job["_id"])
        return list(self.repo.model_outputs.find({"asset_id": self.asset["_id"]}))

    def test_setting_on_writes_metadata_read_from_original_file(self):
        outs = self._run(True)
        self.assertEqual(len(outs), 1)
        self.assertEqual(outs[0]["output_type"], "metadata")
        self.assertEqual(outs[0]["payload"]["metadata"]["width"], 12)
        self.assertEqual(outs[0]["payload"]["metadata"]["height"], 7)

    def test_setting_off_writes_no_metadata(self):
        self.assertEqual(self._run(False), [])


if __name__ == "__main__":
    unittest.main()
