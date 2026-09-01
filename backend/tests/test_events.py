"""Tests for the live-event system.

Covers the three things that can silently break it: events not being emitted at a
transition, an event carrying the wrong identity (so the UI can't route it), and
an emission failure escaping into the operation that triggered it.

Job-lifecycle and outputs-cleared emission (queued/processing/completed/failed,
per-workspace clear notifications) are covered where those transitions actually
live now: test_filesystem_pipeline.py's ReconciliationEventTests (queued),
test_dynamic_pipeline.py (processing/completed/failed), and
test_pipeline_service_delete_cascade.py / test_workspace_clear_outputs_cascade.py
(outputs cleared). This file covers the event system's own primitives —
serialization, the EventSink's swallow-on-failure behavior — and per-stage
progress, which has no other home.
"""
import unittest

from src.domain_events import (
    EVENT_PIPELINE_STAGE,
    EVENT_PIPELINE_STATE,
    Event,
    pipeline_state_event,
)
from src.infrastructure.messaging import EventSink


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


class EventSinkIsolationTests(unittest.TestCase):
    """Live updates are a convenience layered on durable writes.

    If publishing were allowed to raise, a broker problem would start failing
    pipeline runs — the exact inversion of what this feature is worth.
    """

    def test_a_failing_sink_never_raises_out_of_emit(self):
        def explode(_event):
            raise RuntimeError("broker is on fire")

        sink = EventSink()
        sink.set(explode)

        # Must not raise — the whole point of routing every emission through
        # EventSink instead of calling the sink directly.
        sink.emit(pipeline_state_event(
            workspace_id="ws-1", asset_id="a-1", pipeline_id="p-1", state="processing",
        ))

    def test_no_sink_attached_is_a_silent_no_op(self):
        sink = EventSink()  # never .set()
        sink.emit(pipeline_state_event(
            workspace_id="ws-1", asset_id="a-1", pipeline_id="p-1", state="processing",
        ))  # must not raise


class StageEventTests(unittest.TestCase):
    """The pipeline announces each node as it finishes, for in-run progress."""

    def _run_two_node_pipeline(self):
        from src.services.pipeline_execution_service import PipelineExecutionService
        from tests.repo_factory import new_repos

        r = new_repos()
        asset = r.assets.upsert(
            content_sha256="h1", mime_type="image/jpeg", size_bytes=5,
            current_path="/photos/a.jpg", workspace_id="ws-a",
        )
        r.nodes.collection.insert_one({
            "_id": "n-detect", "node_type": "object_detection", "owner_id": "u1",
            "context_inputs": ["image"], "context_outputs": ["detections"],
            "default_config": {},
        })
        r.nodes.collection.insert_one({
            "_id": "n-caption", "node_type": "captioning", "owner_id": "u1",
            "context_inputs": ["image"], "context_outputs": ["caption"],
            "default_config": {},
        })
        r.pipelines.collection.insert_one({
            "_id": "p1", "name": "P1", "owner_id": "u1",
            "nodes": [
                {"node_id": "a", "pipeline_node_id": "n-detect", "order": 0, "config_overrides": {}},
                {"node_id": "b", "pipeline_node_id": "n-caption", "order": 1, "config_overrides": {}},
            ],
            "edges": [{"from_node_id": "a", "to_node_id": "b"}],
        })
        job, _ = r.jobs.get_or_create(
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

        sink = EventSink()
        events = []
        sink.set(events.append)
        pipeline = PipelineExecutionService(
            jobs=r.jobs, runs=r.runs, outputs=r.outputs, assets=r.assets,
            pipelines=r.pipelines, nodes=r.nodes,
            get_executor=lambda t: _FakeExecutor(
                "detections" if t == "object_detection" else "caption"
            ),
            image_loader=lambda asset: object(),
            event_sink=sink,
        )
        pipeline.run_job(job["_id"])
        return events

    def test_each_node_reports_its_position_in_the_run(self):
        events = self._run_two_node_pipeline()
        stages = [e for e in events if e.type == EVENT_PIPELINE_STAGE]
        self.assertEqual(
            [(s.data["index"], s.data["total"], s.data["node_type"]) for s in stages],
            [(1, 2, "object_detection"), (2, 2, "captioning")],
        )

    def test_stage_events_are_addressed_to_the_image_being_processed(self):
        events = self._run_two_node_pipeline()
        stage = next(e for e in events if e.type == EVENT_PIPELINE_STAGE)
        self.assertEqual(stage.workspace_id, "ws-a")
        self.assertEqual(stage.pipeline_id, "p1")
        self.assertIsNotNone(stage.asset_id)

    def test_stages_are_bracketed_by_the_processing_and_completed_states(self):
        events = self._run_two_node_pipeline()
        types = [e.type for e in events]
        first_stage = types.index(EVENT_PIPELINE_STAGE)
        last_state = len(types) - 1 - types[::-1].index(EVENT_PIPELINE_STATE)
        self.assertEqual(types[0], EVENT_PIPELINE_STATE)  # processing
        self.assertLess(first_stage, last_state)  # completed comes last
        self.assertEqual(events[0].data["state"], "processing")
        self.assertEqual(events[last_state].data["state"], "completed")


if __name__ == "__main__":
    unittest.main()
