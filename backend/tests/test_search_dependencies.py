"""Semantic search exercised through its injected collaborators.

These tests are the reason ``SearchService`` takes a vector store and a query
encoder rather than importing Weaviate and CLIP mid-method: the whole semantic
path — hit resolution, access scoping, degradation — is now reachable with two
stubs and no infrastructure.
"""
import logging
import unittest

from src.infrastructure.vector_store.protocol import (
    QueryEncoder,
    VectorHit,
    VectorSearchClient,
)
from src.services.search_service import SearchService
from tests.repo_factory import new_repos


class StubVectorStore:
    """Returns canned hits; records the arguments it was called with."""

    def __init__(self, hits=None, error: Exception | None = None):
        self.hits = hits or []
        self.error = error
        self.calls: list[dict] = []

    def near_vector(self, *, class_name, vector, top_k, certainty=0.0):
        self.calls.append(
            {"class_name": class_name, "vector": vector, "top_k": top_k, "certainty": certainty}
        )
        if self.error:
            raise self.error
        return self.hits


class StubEncoder:
    def __init__(self, vector=None):
        self.vector = vector

    def encode(self, text):
        return self.vector


def _search_service(r, **overrides):
    return SearchService(
        assets=r.assets, observations=r.observations, workspaces=r.workspaces, outputs=r.outputs,
        **overrides,
    )


class ProtocolConformanceTests(unittest.TestCase):
    def test_stubs_satisfy_the_declared_protocols(self):
        # If this fails, the stubs have drifted from the contract and the rest of
        # this file is testing something the real adapters don't have to honour.
        self.assertIsInstance(StubVectorStore(), VectorSearchClient)
        self.assertIsInstance(StubEncoder(), QueryEncoder)

    def test_real_adapters_satisfy_the_declared_protocols(self):
        from src.infrastructure.vector_store.query_encoder import ClipQueryEncoder
        from src.infrastructure.vector_store.weaviate import WeaviateSearchClient

        self.assertIsInstance(WeaviateSearchClient("http://localhost:8080"), VectorSearchClient)
        self.assertIsInstance(ClipQueryEncoder(), QueryEncoder)


class SemanticSearchTests(unittest.TestCase):
    def setUp(self):
        self.r = new_repos()
        self.user = self.r.users.create("alice", "hash")
        self.workspace = self.r.workspaces.create(
            owner_id=self.user["_id"], name="ws", workspace_path="/photos"
        )
        self.asset = self._add_asset("h1", "/photos/cat.jpg", "a tabby cat")

    def _add_asset(self, sha, path, caption, workspace=None):
        workspace = workspace or self.workspace
        asset = self.r.assets.upsert(
            content_sha256=sha,
            mime_type="image/jpeg",
            size_bytes=5,
            current_path=path,
            workspace_id=workspace["_id"],
        )
        self.r.observations.upsert(
            asset_id=asset["_id"],
            workspace_id=workspace["_id"],
            relative_path=path.rsplit("/", 1)[-1],
            absolute_path=path,
            content_sha256=sha,
        )
        self.r.outputs.add(
            asset_id=asset["_id"],
            pipeline_run_id=f"run-{sha}",
            model_name="blip",
            model_version="base",
            output_type="caption",
            payload={"text": caption},
        )
        return asset

    def _service(self, store, encoder):
        return _search_service(self.r, vector_store=store, query_encoder=encoder)

    def test_semantic_hits_are_resolved_into_assets(self):
        store = StubVectorStore([VectorHit(asset_id=self.asset["_id"], certainty=0.91)])
        service = self._service(store, StubEncoder([0.1, 0.2, 0.3]))

        results = service.search(
            query="cat", user_id=self.user["_id"], mode="semantic", top_k=10
        )

        self.assertEqual([r["_id"] for r in results], [self.asset["_id"]])
        self.assertEqual(results[0]["score"], 0.91)
        self.assertEqual(results[0]["match_reason"]["mode"], "semantic")
        self.assertEqual(results[0]["description"], "a tabby cat")

    def test_query_vector_and_paging_reach_the_vector_store(self):
        store = StubVectorStore([])
        service = self._service(store, StubEncoder([0.5, 0.5]))

        service.search(
            query="cat",
            user_id=self.user["_id"],
            mode="semantic",
            top_k=5,
            skip=10,
            threshold=0.7,
        )

        # top_k + skip, so the caller can page past the first window.
        self.assertEqual(
            store.calls,
            [{"class_name": "TextEmbedding", "vector": [0.5, 0.5], "top_k": 15, "certainty": 0.7}],
        )

    def test_hits_outside_the_users_access_are_dropped(self):
        stranger = self.r.users.create("bob", "hash")
        other_ws = self.r.workspaces.create(
            owner_id=stranger["_id"], name="theirs", workspace_path="/other"
        )
        theirs = self._add_asset("h2", "/other/dog.jpg", "a dog", workspace=other_ws)

        store = StubVectorStore([
            VectorHit(asset_id=theirs["_id"], certainty=0.99),
            VectorHit(asset_id=self.asset["_id"], certainty=0.80),
        ])
        service = self._service(store, StubEncoder([0.1]))

        results = service.search(
            query="animal", user_id=self.user["_id"], mode="semantic", top_k=10
        )

        # The stranger's asset scored higher but is not alice's to see.
        self.assertEqual([r["_id"] for r in results], [self.asset["_id"]])

    def test_unencodable_query_degrades_to_keyword_search(self):
        store = StubVectorStore([VectorHit(asset_id=self.asset["_id"], certainty=0.9)])
        service = self._service(store, StubEncoder(None))

        with self.assertLogs("pixquery.services.search_service", level=logging.INFO):
            results = service.search(
                query="tabby", user_id=self.user["_id"], mode="semantic"
            )

        self.assertEqual(store.calls, [])  # never queried
        self.assertEqual([r["_id"] for r in results], [self.asset["_id"]])
        self.assertEqual(results[0]["match_reason"]["mode"], "keyword")

    def test_vector_store_failure_degrades_to_keyword_and_is_logged(self):
        store = StubVectorStore(error=ConnectionError("weaviate unreachable"))
        service = self._service(store, StubEncoder([0.1]))

        with self.assertLogs("pixquery.services.search_service", level=logging.WARNING) as captured:
            results = service.search(
                query="tabby", user_id=self.user["_id"], mode="semantic"
            )

        # An operational fault must be distinguishable in the logs from the
        # benign "CLIP isn't installed" case — both used to be silent.
        self.assertIn("Vector store query failed", "\n".join(captured.output))
        self.assertEqual([r["_id"] for r in results], [self.asset["_id"]])


class WorkspaceScopingTests(unittest.TestCase):
    """``workspace_id`` arrives unvalidated from the query string, so it must only
    ever narrow a user's own scope — never widen it."""

    def setUp(self):
        self.r = new_repos()
        self.alice = self.r.users.create("alice", "hash")
        self.bob = self.r.users.create("bob", "hash")
        self.bob_ws = self.r.workspaces.create(
            owner_id=self.bob["_id"], name="bob's", workspace_path="/bob"
        )
        asset = self.r.assets.upsert(
            content_sha256="secret",
            mime_type="image/jpeg",
            size_bytes=5,
            current_path="/bob/private.jpg",
            workspace_id=self.bob_ws["_id"],
        )
        self.r.observations.upsert(
            asset_id=asset["_id"],
            workspace_id=self.bob_ws["_id"],
            relative_path="private.jpg",
            absolute_path="/bob/private.jpg",
            content_sha256="secret",
        )
        self.r.outputs.add(
            asset_id=asset["_id"],
            pipeline_run_id="run-1",
            model_name="blip",
            model_version="base",
            output_type="caption",
            payload={"text": "a private photo"},
        )
        self.bob_asset = asset["_id"]
        self.service = _search_service(self.r)

    def test_browsing_another_users_workspace_returns_nothing(self):
        results = self.service.search(query="", user_id=self.alice["_id"])
        self.assertEqual(results, [])

        leaked = self.service.search(
            query="", user_id=self.alice["_id"], workspace_id=self.bob_ws["_id"]
        )
        self.assertEqual(leaked, [])

    def test_keyword_search_in_another_users_workspace_returns_nothing(self):
        results = self.service.search(
            query="private",
            user_id=self.alice["_id"],
            workspace_id=self.bob_ws["_id"],
            mode="keyword",
        )
        self.assertEqual(results, [])

    def test_semantic_hits_in_another_users_workspace_are_dropped(self):
        store = StubVectorStore([VectorHit(asset_id=self.bob_asset, certainty=0.99)])
        service = _search_service(
            self.r, vector_store=store, query_encoder=StubEncoder([0.1])
        )
        results = service.search(
            query="private",
            user_id=self.alice["_id"],
            workspace_id=self.bob_ws["_id"],
            mode="semantic",
        )
        self.assertEqual(results, [])

    def test_owner_still_sees_their_own_workspace(self):
        results = self.service.search(
            query="", user_id=self.bob["_id"], workspace_id=self.bob_ws["_id"]
        )
        self.assertEqual([r["_id"] for r in results], [self.bob_asset])

    def test_unknown_workspace_id_returns_nothing_rather_than_everything(self):
        results = self.service.search(
            query="", user_id=self.bob["_id"], workspace_id="does-not-exist"
        )
        self.assertEqual(results, [])


if __name__ == "__main__":
    unittest.main()
