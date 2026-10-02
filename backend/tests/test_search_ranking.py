"""Tests for hybrid ranking (RRF) and semantic search fallback."""
import unittest
from unittest import mock

from src.services.search_service import SearchService, _reciprocal_rank_fusion
from tests.repo_factory import new_repos


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


class _UnencodableQuery:
    def encode(self, text):
        return None


class _VectorStoreDown:
    def near_vector(self, *args, **kwargs):
        raise ConnectionError("vector store unreachable")


class SemanticFallbackTests(unittest.TestCase):
    """When CLIP can't be loaded, semantic search degrades to keyword search.

    Encoder and vector store are injected so this neither loads real CLIP onto
    the GPU nor depends on whether a real Weaviate happens to be running.
    """

    def setUp(self):
        self.r = new_repos()
        self.search = SearchService(
            assets=self.r.assets, observations=self.r.observations,
            workspaces=self.r.workspaces, outputs=self.r.outputs,
            vector_store=_VectorStoreDown(),
            query_encoders={"clip": _UnencodableQuery()},
        )
        asset = self.r.assets.upsert(
            content_sha256="h1",
            mime_type="image/jpeg",
            size_bytes=5,
            current_path="/photos/cat.jpg",
        )
        self.asset_id = asset["_id"]
        self.r.outputs.add(
            asset_id=asset["_id"],
            pipeline_run_id="run-1",
            model_name="blip",
            model_version="base",
            output_type="caption",
            payload={"text": "a tabby cat"},
        )

    def test_query_encoder_returns_none_without_clip(self):
        # Simulate CLIP genuinely being unavailable (e.g. missing torch/clip
        # dependency, or model load failure) rather than relying on it being
        # absent from the test environment -- in this environment CLIP is
        # installed and loads successfully, so encode() would otherwise return
        # a real embedding and this test would be asserting a fact about the
        # environment, not about the fallback behavior. Exercised directly on
        # ClipQueryEncoder — the real logic, and what SearchService.query_encoders
        # builds one of per text-capable embedding model — rather than through
        # SearchService, which is just a thin multi-model fan-out over these.
        from src.infrastructure.vector_store.query_encoder import ClipQueryEncoder

        with mock.patch(
            "src.infrastructure.ml.clip.get_clip_model",
            side_effect=ImportError("CLIP is unavailable"),
        ):
            self.assertIsNone(ClipQueryEncoder().encode("cat"))

    def test_query_encoder_returns_none_when_embed_text_fails(self):
        # embed_text() itself returns None on internal failure (see
        # ClipModel.embed_text's except branch) -- encode() must propagate that
        # as None too, not raise.
        from src.infrastructure.vector_store.query_encoder import ClipQueryEncoder

        fake_model = mock.Mock()
        fake_model.embed_text.return_value = None
        with mock.patch(
            "src.infrastructure.ml.clip.get_clip_model",
            return_value=fake_model,
        ):
            self.assertIsNone(ClipQueryEncoder().encode("cat"))

    def test_semantic_falls_back_to_keyword(self):
        results = self.search.search(query="tabby", mode="semantic")
        self.assertEqual([r["_id"] for r in results], [self.asset_id])

    def test_hybrid_returns_keyword_hits_when_semantic_unavailable(self):
        results = self.search.search(query="cat", mode="hybrid")
        self.assertEqual([r["_id"] for r in results], [self.asset_id])


if __name__ == "__main__":
    unittest.main()
