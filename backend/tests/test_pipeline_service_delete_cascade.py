"""PipelineService.delete_pipeline's cascade and event emission.

Mirrors test_delete_pipeline_cascade.py's fixture, which exercises the same
cascade at the OLD god-repository's ``delete_pipeline`` — this proves the
migrated version (service-orchestrated, composing 5 repositories, event
emission moved out of the repository into an injected EventSink) behaves
identically, plus covers what the old test couldn't: that the event actually
fires, once per affected workspace, and only when a pipeline is actually
deleted.
"""
import unittest

from src.domain_events import EVENT_OUTPUTS_CLEARED
from src.infrastructure.messaging import EventSink
from src.services.pipeline_service import PipelineService
from tests.repo_factory import new_repos


def _service(r, event_sink=None):
    return PipelineService(
        pipelines=r.pipelines, nodes=r.nodes, runs=r.runs, outputs=r.outputs,
        jobs=r.jobs, workspaces=r.workspaces, event_sink=event_sink,
    )


class DeletePipelineCascadeTests(unittest.TestCase):
    def setUp(self):
        self.r = new_repos()
        self.doomed = self.r.pipelines.create(owner_id="o", name="Doomed", nodes=[])
        self.keeper = self.r.pipelines.create(owner_id="o", name="Keeper", nodes=[])
        self.ws = self.r.workspaces.create(
            owner_id="o", name="W", workspace_path="/w",
            pipeline_ids=[self.doomed["_id"], self.keeper["_id"]],
        )
        self.asset = self.r.assets.upsert(
            content_sha256="h", mime_type="image/jpeg", size_bytes=1,
            current_path="/w/a.jpg", workspace_id=self.ws["_id"],
        )
        for pipeline in (self.doomed, self.keeper):
            job, _ = self.r.jobs.get_or_create(
                asset_id=self.asset["_id"], pipeline_id=pipeline["_id"],
                pipeline_version="v1", workspace_id=self.ws["_id"],
            )
            self.r.jobs.start(job["_id"])
            run = self.r.runs.create(
                job_id=job["_id"], asset_id=self.asset["_id"],
                pipeline_id=pipeline["_id"], pipeline_version="v1",
            )
            self.r.outputs.add(
                asset_id=self.asset["_id"], pipeline_run_id=run["_id"],
                model_name="m", model_version="v", output_type="detections",
                payload={"detections": []}, workspace_id=self.ws["_id"],
                pipeline_id=pipeline["_id"], pipeline_version="v1",
            )
            self.r.jobs.complete(job["_id"])

    def _counts(self, pipeline_id):
        return (
            len(list(self.r.outputs.collection.find({"pipeline_id": pipeline_id}))),
            len(self.r.runs.list_for_pipeline(pipeline_id)),
            len(list(self.r.jobs.collection.find({"pipeline_id": pipeline_id}))),
        )

    def test_outputs_runs_and_jobs_are_deleted(self):
        self.assertEqual(self._counts(self.doomed["_id"]), (1, 1, 1))
        deleted = _service(self.r).delete_pipeline(self.doomed["_id"], owner_id="o")
        self.assertTrue(deleted)
        self.assertEqual(self._counts(self.doomed["_id"]), (0, 0, 0))

    def test_other_pipelines_are_untouched(self):
        _service(self.r).delete_pipeline(self.doomed["_id"], owner_id="o")
        self.assertEqual(self._counts(self.keeper["_id"]), (1, 1, 1))

    def test_id_is_pulled_from_referencing_workspaces(self):
        _service(self.r).delete_pipeline(self.doomed["_id"], owner_id="o")
        workspace = self.r.workspaces.get(self.ws["_id"])
        self.assertEqual(workspace["pipeline_ids"], [self.keeper["_id"]])

    def test_asset_survives(self):
        _service(self.r).delete_pipeline(self.doomed["_id"], owner_id="o")
        self.assertIsNotNone(self.r.assets.get(self.asset["_id"]))

    def test_wrong_owner_is_refused_and_nothing_is_deleted(self):
        deleted = _service(self.r).delete_pipeline(self.doomed["_id"], owner_id="someone-else")
        self.assertFalse(deleted)
        self.assertEqual(self._counts(self.doomed["_id"]), (1, 1, 1))

    def test_unknown_pipeline_returns_false(self):
        self.assertFalse(_service(self.r).delete_pipeline("nope", owner_id="o"))

    def test_emits_one_outputs_cleared_event_per_affected_workspace(self):
        sink = EventSink()
        emitted = []
        sink.set(emitted.append)

        _service(self.r, event_sink=sink).delete_pipeline(self.doomed["_id"], owner_id="o")

        self.assertEqual(len(emitted), 1)
        event = emitted[0]
        self.assertEqual(event.type, EVENT_OUTPUTS_CLEARED)
        self.assertEqual(event.workspace_id, self.ws["_id"])
        self.assertEqual(event.pipeline_id, self.doomed["_id"])
        self.assertEqual(event.data["counts"], {"pipeline_deleted": 1})

    def test_emits_one_event_per_workspace_when_a_pipeline_is_shared(self):
        # A pipeline attached to two workspaces must notify both, not just the
        # first one found — proves the emit loop, not just single-iteration.
        other_ws = self.r.workspaces.create(
            owner_id="o", name="W2", workspace_path="/w2", pipeline_ids=[self.doomed["_id"]],
        )
        sink = EventSink()
        emitted = []
        sink.set(emitted.append)

        _service(self.r, event_sink=sink).delete_pipeline(self.doomed["_id"], owner_id="o")

        cleared = [e for e in emitted if e.type == EVENT_OUTPUTS_CLEARED]
        self.assertEqual({e.workspace_id for e in cleared}, {self.ws["_id"], other_ws["_id"]})

    def test_no_event_when_deletion_is_refused(self):
        sink = EventSink()
        emitted = []
        sink.set(emitted.append)

        _service(self.r, event_sink=sink).delete_pipeline(self.doomed["_id"], owner_id="wrong")

        self.assertEqual(emitted, [])

    def test_missing_event_sink_is_fine(self):
        # No sink injected — deletion must still succeed, just silently.
        deleted = _service(self.r, event_sink=None).delete_pipeline(self.doomed["_id"], owner_id="o")
        self.assertTrue(deleted)


if __name__ == "__main__":
    unittest.main()
