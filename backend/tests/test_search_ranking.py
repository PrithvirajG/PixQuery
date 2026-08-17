"""Tests for hybrid ranking (RRF) and semantic search fallback."""
import unittest

from src.repositories import InMemoryPipelineRepository
from src.services.search_service import SearchService, _reciprocal_rank_fusion


def doc(_id, description="", score=None):
    d = {"_id": _id, "description": description}
    if score is not None:
        d["score"] = score
    return d


class ReciprocalRankFusionTests(unittest.TestCase):
    def test_document_in_both_lists_outranks_single_list_documents(self):
        keyword = [doc("d1"), doc("d2"), doc("d3")]
        semantic = [doc("d2"), doc("d4")]

        fused = _reciprocal_rank_fusion([keyword, semantic])

        # d2 appears in both lists → highest fused score.
        self.assertEqual([d["_id"] for d in fused], ["d2", "d1", "d4", "d3"])

    def test_preserves_representative_with_description(self):
        # Same doc: keyword entry has no caption, semantic entry has one.
        keyword = [doc("d1", description="")]
        semantic = [doc("d1", description="a tabby cat")]

        fused = _reciprocal_rank_fusion([keyword, semantic])

        self.assertEqual(len(fused), 1)
        self.assertEqual(fused[0]["description"], "a tabby cat")

    def test_empty_lists_produce_empty_result(self):
        self.assertEqual(_reciprocal_rank_fusion([[], []]), [])

    def test_single_list_keeps_order(self):
        ranked = [doc("a"), doc("b"), doc("c")]
        fused = _reciprocal_rank_fusion([ranked])
        self.assertEqual([d["_id"] for d in fused], ["a", "b", "c"])


class SemanticFallbackTests(unittest.TestCase):
    """When CLIP can't be loaded, semantic search degrades to keyword search."""

    def setUp(self):
        self.repo = InMemoryPipelineRepository()
        self.search = SearchService(self.repo)
        asset = self.repo.upsert_asset(
            content_sha256="h1",
            mime_type="image/jpeg",
            size_bytes=5,
            current_path="/photos/cat.jpg",
        )
        self.asset_id = asset["_id"]
        self.repo.add_model_output(
            asset_id=asset["_id"],
            pipeline_run_id="run-1",
            model_name="blip",
            model_version="base",
            output_type="caption",
            payload={"text": "a tabby cat"},
        )

    def test_encode_query_returns_none_without_clip(self):
        # No torch/clip in this environment → graceful None, not an exception.
        self.assertIsNone(self.search._encode_query("cat"))

    def test_semantic_falls_back_to_keyword(self):
        results = self.search.search(query="tabby", mode="semantic")
        self.assertEqual([r["_id"] for r in results], [self.asset_id])

    def test_hybrid_returns_keyword_hits_when_semantic_unavailable(self):
        results = self.search.search(query="cat", mode="hybrid")
        self.assertEqual([r["_id"] for r in results], [self.asset_id])


if __name__ == "__main__":
    unittest.main()
