"""End-to-end smoke test: ingest -> (simulated) process -> search.

Exercises the full ingestion + search path against the in-memory repository
with no external infrastructure (no MongoDB / RabbitMQ / Weaviate) and no model
weights. The processing step is simulated by writing a caption to
``model_outputs`` the way the worker would, so keyword search can find it.

This is the fast "is the wiring intact?" check referenced in the README
quickstart. The real end-to-end path (with infra + models) is covered by the
manual checklist in the README.
"""
import tempfile
import unittest
from pathlib import Path

from src.services.reconciliation_service import ReconciliationService
from src.services.search_service import SearchService
from tests.repo_factory import new_repos


class FakePublisher:
    def __init__(self):
        self.messages = []

    async def publish(self, message):
        self.messages.append(message)


class SmokeSearchTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.r = new_repos()
        self.publisher = FakePublisher()
        self.reconciler = ReconciliationService(
            assets=self.r.assets, observations=self.r.observations, jobs=self.r.jobs, pipelines=self.r.pipelines,
            publisher=self.publisher,
            workspace_path=str(self.root),
            workspace_id="smoke-root",
            pipeline_id="test-pipeline",
            pipeline_version="v1",
            stable_interval_seconds=0.01,
            stable_timeout_seconds=1,
        )
        self.search = SearchService(
            assets=self.r.assets, observations=self.r.observations,
            workspaces=self.r.workspaces, outputs=self.r.outputs,
        )

    async def asyncTearDown(self):
        self.tmp.cleanup()

    async def _ingest(self, name: str, content: bytes) -> str:
        """Reconcile one file and return its asset_id."""
        (self.root / name).write_bytes(content)
        await self.reconciler.reconcile()
        asset = next(a for a in self.r.assets.list_all(active_only=True) if a["current_path"].endswith(name))
        return asset["_id"]

    def _simulate_processing(self, asset_id: str, caption: str) -> None:
        """Mimic the worker: run a pipeline job and store a caption output."""
        job = self.r.jobs.list_all()[0]
        self.r.jobs.start(job["_id"])
        run = self.r.runs.create(
            job_id=job["_id"], asset_id=job["asset_id"],
            pipeline_id=job["pipeline_id"], pipeline_version=job["pipeline_version"],
        )
        self.r.outputs.add(
            asset_id=asset_id,
            pipeline_run_id=run["_id"],
            model_name="blip",
            model_version="image-captioning-base",
            output_type="caption",
            payload={"text": caption},
        )
        self.r.jobs.complete(job["_id"])

    async def test_ingest_process_then_keyword_search_by_caption(self):
        asset_id = await self._ingest("beach.jpg", b"fake-image-bytes")
        self._simulate_processing(asset_id, "a sunny beach with palm trees")

        results = self.search.search(query="palm trees", mode="keyword")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["_id"], asset_id)
        self.assertEqual(results[0]["description"], "a sunny beach with palm trees")
        self.assertEqual(results[0]["score"], 1.0)

    async def test_keyword_search_matches_on_filename(self):
        asset_id = await self._ingest("vacation-sunset.jpg", b"another-fake-image")
        self._simulate_processing(asset_id, "")

        results = self.search.search(query="sunset", mode="keyword")

        self.assertEqual([r["_id"] for r in results], [asset_id])

    async def test_search_returns_nothing_for_unrelated_query(self):
        asset_id = await self._ingest("cat.jpg", b"cat-bytes")
        self._simulate_processing(asset_id, "a tabby cat on a sofa")

        self.assertEqual(self.search.search(query="airplane", mode="keyword"), [])

    async def test_empty_query_browses_all_active_assets(self):
        a1 = await self._ingest("one.jpg", b"one")
        await self.reconciler.reconcile()  # no-op second pass; asset already known
        self._simulate_processing(a1, "first image")

        results = self.search.search(query="", mode="keyword")

        self.assertEqual([r["_id"] for r in results], [a1])


if __name__ == "__main__":
    unittest.main()
