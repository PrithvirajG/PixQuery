"""Tests for the live-event system.

Covers the three things that can silently break it: events not being emitted at a
transition, an event carrying the wrong identity (so the UI can't route it), and
an emission failure escaping into the operation that triggered it.
"""
import unittest

from src.events import (
    EVENT_OUTPUTS_CLEARED,
    EVENT_PIPELINE_STAGE,
    EVENT_PIPELINE_STATE,
    Event,
    pipeline_state_event,
)
from src.repositories import InMemoryPipelineRepository


class EventSerializationTests(unittest.TestCase):
    def test_round_trips_through_json(self):
        original = Event(
            type=EVENT_PIPELINE_STATE,
            workspace_id="ws-1",
            asset_id="a-1",
            pipeline_id="p-1",
            data={"state": "processing"},
        )
        restored = Event.from_json(original.to_json())
        self.assertEqual(restored.to_dict(), original.to_dict())

    def test_error_payload_carries_message_but_not_the_stack_trace(self):
        event = pipeline_state_event(
            workspace_id="ws-1",
            asset_id="a-1",
            pipeline_id="p-1",
            state="failed",
            error={
                "class": "ValueError",
                "message": "bad input",
                "trace": "Traceback (most recent call last): ...",
            },
        )
        self.assertEqual(event.data["error"], {"message": "bad input", "class": "ValueError"})
        self.assertNotIn("trace", event.data["error"])

    def test_malformed_payload_is_rejected_not_silently_accepted(self):
        with self.assertRaises(ValueError):
            Event.from_json("not json")


class JobLifecycleEventTests(unittest.TestCase):
    def setUp(self):
        self.repo = InMemoryPipelineRepository()
        self.asset = self.repo.upsert_asset(
            content_sha256="h1",
            mime_type="image/jpeg",
            size_bytes=5,
            current_path="/photos/a.jpg",
            workspace_id="ws-a",
        )
        self.repo.events.clear()

    def _states(self):
        return [
            e.data["state"] for e in self.repo.events if e.type == EVENT_PIPELINE_STATE
        ]

    def test_full_lifecycle_emits_queued_processing_completed(self):
        job, _ = self.repo.ensure_processing_job(
            asset_id=self.asset["_id"],
            pipeline_id="p1",
            pipeline_version="v1",
            workspace_id="ws-a",
        )
        started = self.repo.start_job(job["_id"])
        self.repo.complete_job(job["_id"], started["pipeline_run_id"])

        self.assertEqual(self._states(), ["queued", "processing", "completed"])

    def test_events_carry_the_identity_needed_to_route_them(self):
        job, _ = self.repo.ensure_processing_job(
            asset_id=self.asset["_id"],
            pipeline_id="p1",
            pipeline_version="v1",
            workspace_id="ws-a",
        )
        event = self.repo.events[-1]
        self.assertEqual(event.workspace_id, "ws-a")
        self.assertEqual(event.asset_id, self.asset["_id"])
        self.assertEqual(event.pipeline_id, "p1")
        self.assertEqual(event.data["job_id"], job["_id"])

    def test_an_existing_job_is_not_reannounced_as_newly_queued(self):
        self.repo.ensure_processing_job(
            asset_id=self.asset["_id"], pipeline_id="p1",
            pipeline_version="v1", workspace_id="ws-a",
        )
        self.repo.events.clear()
        # Second call finds the existing job; nothing changed, so nothing is emitted.
        _, created = self.repo.ensure_processing_job(
            asset_id=self.asset["_id"], pipeline_id="p1",
            pipeline_version="v1", workspace_id="ws-a",
        )
        self.assertFalse(created)
        self.assertEqual(self.repo.events, [])

    def test_requeue_announces_queued_again(self):
        job, _ = self.repo.ensure_processing_job(
            asset_id=self.asset["_id"], pipeline_id="p1",
            pipeline_version="v1", workspace_id="ws-a",
        )
        self.repo.start_job(job["_id"])
        self.repo.events.clear()
        self.repo.requeue_job(job["_id"])
        self.assertEqual(self._states(), ["queued"])

    def test_retryable_failure_reports_queued_not_failed(self):
        """A failure with retries left goes back to waiting, and the UI should say so."""
        job, _ = self.repo.ensure_processing_job(
            asset_id=self.asset["_id"], pipeline_id="p1",
            pipeline_version="v1", workspace_id="ws-a",
        )
        started = self.repo.start_job(job["_id"])
        self.repo.events.clear()
        status = self.repo.fail_job(
            job["_id"], started["pipeline_run_id"], {"class": "OSError", "message": "boom"}
        )
        self.assertEqual(status, "queued")
        self.assertEqual(self._states(), ["queued"])

    def test_permanent_failure_reports_failed_with_the_message(self):
        job, _ = self.repo.ensure_processing_job(
            asset_id=self.asset["_id"], pipeline_id="p1",
            pipeline_version="v1", workspace_id="ws-a",
        )
        started = self.repo.start_job(job["_id"])
        self.repo.events.clear()
        self.repo.fail_job(
            job["_id"],
            started["pipeline_run_id"],
            {"class": "PermanentNodeError", "message": "unknown node"},
            permanent=True,
        )
        event = self.repo.events[-1]
        self.assertEqual(event.data["state"], "failed")
        self.assertEqual(event.data["error"]["message"], "unknown node")


class ClearingEventTests(unittest.TestCase):
    def setUp(self):
        self.repo = InMemoryPipelineRepository()
        self.asset = self.repo.upsert_asset(
            content_sha256="h1", mime_type="image/jpeg", size_bytes=5,
            current_path="/photos/a.jpg", workspace_id="ws-a",
        )
        job, _ = self.repo.ensure_processing_job(
            asset_id=self.asset["_id"], pipeline_id="p1",
            pipeline_version="v1", workspace_id="ws-a",
        )
        run = self.repo.start_job(job["_id"])
        self.repo.add_model_output(
            asset_id=self.asset["_id"], pipeline_run_id=run["pipeline_run_id"],
            model_name="m", model_version="v", output_type="detections",
            payload={}, workspace_id="ws-a", pipeline_id="p1", pipeline_version="v1",
        )
        self.repo.complete_job(job["_id"], run["pipeline_run_id"])
        self.repo.events.clear()

    def test_workspace_clear_is_scoped_to_the_workspace(self):
        self.repo.clear_pipeline_outputs("ws-a", "p1")
        event = self.repo.events[-1]
        self.assertEqual(event.type, EVENT_OUTPUTS_CLEARED)
        self.assertEqual(event.data["scope"], "workspace")
        # No asset id: every image in the workspace is affected.
        self.assertIsNone(event.asset_id)

    def test_asset_clear_names_the_affected_image(self):
        self.repo.clear_asset_pipeline_outputs(self.asset["_id"], "p1")
        event = self.repo.events[-1]
        self.assertEqual(event.type, EVENT_OUTPUTS_CLEARED)
        self.assertEqual(event.data["scope"], "asset")
        self.assertEqual(event.asset_id, self.asset["_id"])
        # Resolved off the job so the API can route it without a second lookup.
        self.assertEqual(event.workspace_id, "ws-a")

    def test_deleting_a_pipeline_notifies_each_workspace_that_used_it(self):
        self.repo.workspace_definitions.insert_one(
            {"_id": "ws-a", "pipeline_ids": ["p1"], "name": "A"}
        )
        self.repo.workspace_definitions.insert_one(
            {"_id": "ws-b", "pipeline_ids": ["p1"], "name": "B"}
        )
        self.repo.pipeline_definitions.insert_one({"_id": "p1", "name": "P1", "nodes": []})
        self.repo.events.clear()

        self.repo.delete_pipeline("p1")
        cleared = [e for e in self.repo.events if e.type == EVENT_OUTPUTS_CLEARED]
        self.assertEqual({e.workspace_id for e in cleared}, {"ws-a", "ws-b"})


class EmissionIsolationTests(unittest.TestCase):
    def test_a_failing_sink_never_breaks_the_operation(self):
        """Live updates are a convenience layered on durable writes.

        If publishing were allowed to raise, a broker problem would start failing
        pipeline runs — the exact inversion of what this feature is worth.
        """

        def explode(_event):
            raise RuntimeError("broker is on fire")

        repo = InMemoryPipelineRepository(event_sink=explode)
        asset = repo.upsert_asset(
            content_sha256="h1", mime_type="image/jpeg", size_bytes=5,
            current_path="/photos/a.jpg", workspace_id="ws-a",
        )
        job, created = repo.ensure_processing_job(
            asset_id=asset["_id"], pipeline_id="p1",
            pipeline_version="v1", workspace_id="ws-a",
        )
        self.assertTrue(created)
        started = repo.start_job(job["_id"])
        repo.complete_job(job["_id"], started["pipeline_run_id"])
        self.assertEqual(repo.get_job(job["_id"])["status"], "completed")

    def test_a_repository_without_a_sink_stays_silent(self):
        from src.repositories.memory_pipeline import _MemoryDatabase
        from src.repositories.mongo_pipeline import MongoPipelineRepository

        repo = MongoPipelineRepository(_MemoryDatabase())
        asset = repo.upsert_asset(
            content_sha256="h1", mime_type="image/jpeg", size_bytes=5,
            current_path="/photos/a.jpg", workspace_id="ws-a",
        )
        job, _ = repo.ensure_processing_job(
            asset_id=asset["_id"], pipeline_id="p1",
            pipeline_version="v1", workspace_id="ws-a",
        )
        # No sink attached: emitting is a no-op, and the write still happened.
        self.assertIsNotNone(repo.get_job(job["_id"]))


class StageEventTests(unittest.TestCase):
    """The pipeline announces each node as it finishes, for in-run progress."""

    def _run_two_node_pipeline(self):
        from src.pipelines.processing.pipeline import DynamicPipeline

        repo = InMemoryPipelineRepository()
        asset = repo.upsert_asset(
            content_sha256="h1", mime_type="image/jpeg", size_bytes=5,
            current_path="/photos/a.jpg", workspace_id="ws-a",
        )
        repo.pipeline_nodes_col.insert_one({
            "_id": "n-detect", "node_type": "object_detection", "owner_id": "u1",
            "context_inputs": ["image"], "context_outputs": ["detections"],
            "default_config": {},
        })
        repo.pipeline_nodes_col.insert_one({
            "_id": "n-caption", "node_type": "captioning", "owner_id": "u1",
            "context_inputs": ["image"], "context_outputs": ["caption"],
            "default_config": {},
        })
        repo.pipeline_definitions.insert_one({
            "_id": "p1", "name": "P1", "owner_id": "u1",
            "nodes": [
                {"node_id": "a", "pipeline_node_id": "n-detect", "order": 0, "config_overrides": {}},
                {"node_id": "b", "pipeline_node_id": "n-caption", "order": 1, "config_overrides": {}},
            ],
            "edges": [{"from_node_id": "a", "to_node_id": "b"}],
        })
        job, _ = repo.ensure_processing_job(
            asset_id=asset["_id"], pipeline_id="p1",
            pipeline_version="v1", workspace_id="ws-a",
        )

        class _FakeExecutor:
            model_name = "fake"
            model_version = "v1"

            def __init__(self, key):
                self.key = key

            def run(self, context, config):
                return {self.key: ["x"] if self.key == "detections" else "a caption"}

        pipeline = DynamicPipeline(
            get_executor=lambda t: _FakeExecutor(
                "detections" if t == "object_detection" else "caption"
            ),
            image_loader=lambda asset: object(),
        )
        repo.events.clear()
        pipeline.run_job(repo, job["_id"])
        return repo

    def test_each_node_reports_its_position_in_the_run(self):
        repo = self._run_two_node_pipeline()
        stages = [e for e in repo.events if e.type == EVENT_PIPELINE_STAGE]
        self.assertEqual(
            [(s.data["index"], s.data["total"], s.data["node_type"]) for s in stages],
            [(1, 2, "object_detection"), (2, 2, "captioning")],
        )

    def test_stage_events_are_addressed_to_the_image_being_processed(self):
        repo = self._run_two_node_pipeline()
        stage = next(e for e in repo.events if e.type == EVENT_PIPELINE_STAGE)
        self.assertEqual(stage.workspace_id, "ws-a")
        self.assertEqual(stage.pipeline_id, "p1")
        self.assertIsNotNone(stage.asset_id)

    def test_stages_are_bracketed_by_the_processing_and_completed_states(self):
        repo = self._run_two_node_pipeline()
        types = [e.type for e in repo.events]
        first_stage = types.index(EVENT_PIPELINE_STAGE)
        last_state = len(types) - 1 - types[::-1].index(EVENT_PIPELINE_STATE)
        self.assertEqual(types[0], EVENT_PIPELINE_STATE)  # processing
        self.assertLess(first_stage, last_state)  # completed comes last


if __name__ == "__main__":
    unittest.main()
