"""Tests for search match_reason and image-detail provenance."""
import unittest

from src.repositories import InMemoryPipelineRepository
from src.services.image_service import ImageService
from src.services.search_service import SearchService, _combine_match_reasons


class MatchReasonTests(unittest.TestCase):
    def setUp(self):
        self.repo = InMemoryPipelineRepository()
        self.search = SearchService(self.repo)

    def _add(self, sha, path, caption):
        asset = self.repo.upsert_asset(
            content_sha256=sha, mime_type="image/jpeg", size_bytes=5, current_path=path
        )
        if caption:
            self.repo.add_model_output(
                asset_id=asset["_id"], pipeline_run_id="r", model_name="blip",
                model_version="base", output_type="caption", payload={"text": caption},
            )
        return asset["_id"]

    def test_keyword_reason_reports_caption_field(self):
        self._add("h1", "/photos/img001.jpg", "a tabby cat on a sofa")
        results = self.search.search(query="tabby", mode="keyword")
        self.assertEqual(len(results), 1)
        reason = results[0]["match_reason"]
        self.assertEqual(reason["mode"], "keyword")
        self.assertEqual(reason["terms"], ["tabby"])
        self.assertEqual(reason["fields"], ["caption"])

    def test_keyword_reason_reports_filename_field(self):
        self._add("h2", "/photos/sunset-beach.jpg", "")
        results = self.search.search(query="sunset", mode="keyword")
        self.assertEqual(results[0]["match_reason"]["fields"], ["filename"])

    def test_keyword_reason_reports_both_fields(self):
        self._add("h3", "/photos/cat.jpg", "a cat")
        results = self.search.search(query="cat", mode="keyword")
        self.assertEqual(results[0]["match_reason"]["fields"], ["filename", "caption"])

    def test_combine_match_reasons_hybrid(self):
        kw = {"mode": "keyword", "terms": ["cat"], "fields": ["caption"]}
        combined = _combine_match_reasons(kw, 0.82)
        self.assertEqual(combined["mode"], "hybrid")
        self.assertEqual(combined["terms"], ["cat"])
        self.assertEqual(combined["fields"], ["caption"])
        self.assertEqual(combined["similarity"], 0.82)

    def test_combine_match_reasons_keyword_only(self):
        kw = {"mode": "keyword", "terms": ["cat"], "fields": ["filename"]}
        self.assertEqual(_combine_match_reasons(kw, None), kw)

    def test_combine_match_reasons_semantic_only(self):
        self.assertEqual(
            _combine_match_reasons(None, 0.7), {"mode": "semantic", "similarity": 0.7}
        )


class ProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.repo = InMemoryPipelineRepository()
        self.images = ImageService(self.repo)

    def test_detail_includes_ordered_outputs_and_pipeline_run(self):
        asset = self.repo.upsert_asset(
            content_sha256="h1", mime_type="image/jpeg", size_bytes=5,
            current_path="/photos/cat.jpg",
        )
        job, _ = self.repo.ensure_processing_job(
            asset_id=asset["_id"], pipeline_id="pipeline-x", pipeline_version="v1"
        )
        started = self.repo.start_job(job["_id"])
        run_id = started["pipeline_run_id"]
        # Add outputs out of order; provenance must sort by node order.
        self.repo.add_model_output(
            asset_id=asset["_id"], pipeline_run_id=run_id, model_name="blip",
            model_version="base", output_type="caption", payload={"text": "a cat"},
            node_id="n1", node_type="captioning", order=1,
        )
        self.repo.add_model_output(
            asset_id=asset["_id"], pipeline_run_id=run_id, model_name="yolo",
            model_version="v8n", output_type="detections", payload={"detections": []},
            node_id="n0", node_type="object_detection", order=0,
        )
        self.repo.complete_job(job["_id"], run_id)

        detail = self.images.get_image_detail(asset["_id"])

        self.assertEqual(detail["description"], "a cat")
        prov = detail["provenance"]
        # One pipeline group, its outputs sorted by node order.
        self.assertEqual(len(prov["pipelines"]), 1)
        grp = prov["pipelines"][0]
        self.assertEqual(grp["pipeline_id"], "pipeline-x")
        self.assertEqual(grp["pipeline_version"], "v1")
        self.assertEqual(grp["status"], "completed")
        self.assertIsNotNone(grp["finished_at"])
        self.assertEqual([o["node_type"] for o in grp["outputs"]],
                         ["object_detection", "captioning"])
        self.assertEqual(grp["outputs"][0]["model_name"], "yolo")
        self.assertIsNotNone(grp["outputs"][0]["created_at"])
        self.assertIn("summary", grp["outputs"][1])  # caption summary present

    def test_reprocessing_replaces_outputs_not_accumulates(self):
        asset = self.repo.upsert_asset(
            content_sha256="h2", mime_type="image/jpeg", size_bytes=5, current_path="/p/x.jpg",
        )
        job, _ = self.repo.ensure_processing_job(
            asset_id=asset["_id"], pipeline_id="pl", pipeline_version="v1"
        )
        for _ in range(3):  # scan three times
            started = self.repo.start_job(job["_id"])
            self.repo.add_model_output(
                asset_id=asset["_id"], pipeline_run_id=started["pipeline_run_id"],
                model_name="exif", model_version="pillow", output_type="metadata",
                payload={"metadata": {"width": 10, "height": 10}}, pipeline_id="pl",
            )
            self.repo.complete_job(job["_id"], started["pipeline_run_id"])

        # Only the latest run's output survives — no accumulation across re-scans.
        outs = list(self.repo.model_outputs.find({"asset_id": asset["_id"]}))
        self.assertEqual(len(outs), 1)
        detail = self.images.get_image_detail(asset["_id"])
        self.assertEqual(len(detail["provenance"]["pipelines"]), 1)
        self.assertEqual(len(detail["provenance"]["pipelines"][0]["outputs"]), 1)

    def test_detail_missing_asset_returns_none(self):
        self.assertIsNone(self.images.get_image_detail("nope"))


if __name__ == "__main__":
    unittest.main()
