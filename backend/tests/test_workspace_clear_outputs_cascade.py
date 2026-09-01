"""Cascade depth and event emission for WorkspaceService's two clear-outputs paths.

Mirrors the depth of coverage the old god-repository's ``clear_pipeline_outputs``/
``clear_asset_pipeline_outputs`` had (test_clear_pipeline_outputs.py's and
test_clear_asset_outputs.py's ``*RepositoryTests`` classes, including the tricky
"outputs that predate the denormalized pipeline_id" case) — proving the same
correctness now holds for the service-composed version, plus what those tests
structurally couldn't cover: that the ``outputs_cleared`` event actually fires,
with the right shape, only when something was really cleared.
"""
import unittest

from src.domain_events import EVENT_OUTPUTS_CLEARED
from src.infrastructure.messaging import EventSink
from src.services.workspace_service import WorkspaceService
from tests.repo_factory import new_repos


def _service(r, event_sink=None):
    return WorkspaceService(
        workspaces=r.workspaces, users=r.users, assets=r.assets, observations=r.observations,
        jobs=r.jobs, runs=r.runs, outputs=r.outputs, event_sink=event_sink,
    )


def _run_job(r, job_id, *, asset_id, pipeline_id, pipeline_version):
    """Start a job and create its run — what the old facade's start_job did in
    one call, now two explicit steps against the split repositories."""
    r.jobs.start(job_id)
    return r.runs.create(
        job_id=job_id, asset_id=asset_id, pipeline_id=pipeline_id, pipeline_version=pipeline_version,
    )


class ClearPipelineOutputsCascadeTests(unittest.TestCase):
    def setUp(self):
        self.r = new_repos()
        self.ws = self.r.workspaces.create(owner_id="owner-1", name="A", workspace_path="/a")
        self.asset = self.r.assets.upsert(
            content_sha256="h1", mime_type="image/jpeg", size_bytes=5,
            current_path="/photos/a.jpg", workspace_id=self.ws["_id"],
        )
        self.job_a_p1 = self.r.jobs.get_or_create(
            asset_id=self.asset["_id"], pipeline_id="p1", pipeline_version="v1", workspace_id=self.ws["_id"],
        )[0]
        self.job_a_p2 = self.r.jobs.get_or_create(
            asset_id=self.asset["_id"], pipeline_id="p2", pipeline_version="v1", workspace_id=self.ws["_id"],
        )[0]
        for job, pid in ((self.job_a_p1, "p1"), (self.job_a_p2, "p2")):
            run = _run_job(self.r, job["_id"], asset_id=self.asset["_id"], pipeline_id=pid, pipeline_version="v1")
            self.r.outputs.add(
                asset_id=self.asset["_id"], pipeline_run_id=run["_id"],
                model_name="m", model_version="v", output_type="detections",
                payload={}, workspace_id=self.ws["_id"], pipeline_id=pid, pipeline_version="v1",
            )
            self.r.jobs.complete(job["_id"])

    def test_clears_only_the_targeted_pipeline(self):
        result = _service(self.r).clear_pipeline_outputs(self.ws["_id"], "p1", owner_id="owner-1")
        self.assertEqual(result, {"outputs_deleted": 1, "runs_deleted": 1, "jobs_deleted": 1})

        remaining = list(self.r.outputs.collection.find({"asset_id": self.asset["_id"]}))
        self.assertEqual([o["pipeline_id"] for o in remaining], ["p2"])
        remaining_runs = self.r.runs.list_for_job(self.job_a_p1["_id"])
        self.assertEqual(remaining_runs, [])

    def test_deletes_job_so_pair_returns_to_not_started(self):
        _service(self.r).clear_pipeline_outputs(self.ws["_id"], "p1", owner_id="owner-1")
        self.assertIsNone(self.r.jobs.get(self.job_a_p1["_id"]))
        other_job = self.r.jobs.get(self.job_a_p2["_id"])
        self.assertEqual(other_job["status"], "completed")

    def test_does_not_touch_other_workspaces(self):
        other_ws = self.r.workspaces.create(owner_id="owner-1", name="B", workspace_path="/b")
        other_asset = self.r.assets.upsert(
            content_sha256="h2", mime_type="image/jpeg", size_bytes=5,
            current_path="/photos/b.jpg", workspace_id=other_ws["_id"],
        )
        job = self.r.jobs.get_or_create(
            asset_id=other_asset["_id"], pipeline_id="p1", pipeline_version="v1", workspace_id=other_ws["_id"],
        )[0]
        run = _run_job(self.r, job["_id"], asset_id=other_asset["_id"], pipeline_id="p1", pipeline_version="v1")
        self.r.outputs.add(
            asset_id=other_asset["_id"], pipeline_run_id=run["_id"],
            model_name="m", model_version="v", output_type="detections",
            payload={}, workspace_id=other_ws["_id"], pipeline_id="p1", pipeline_version="v1",
        )
        self.r.jobs.complete(job["_id"])

        _service(self.r).clear_pipeline_outputs(self.ws["_id"], "p1", owner_id="owner-1")

        remaining = list(self.r.outputs.collection.find({"asset_id": other_asset["_id"]}))
        self.assertEqual(len(remaining), 1)
        self.assertEqual(self.r.jobs.get(job["_id"])["status"], "completed")

    def test_emits_outputs_cleared_scoped_to_the_workspace(self):
        sink = EventSink()
        emitted = []
        sink.set(emitted.append)

        _service(self.r, event_sink=sink).clear_pipeline_outputs(self.ws["_id"], "p1", owner_id="owner-1")

        self.assertEqual(len(emitted), 1)
        event = emitted[0]
        self.assertEqual(event.type, EVENT_OUTPUTS_CLEARED)
        self.assertEqual(event.workspace_id, self.ws["_id"])
        self.assertEqual(event.pipeline_id, "p1")
        self.assertIsNone(event.asset_id)  # workspace-wide clear, not scoped to one image
        self.assertEqual(event.data["scope"], "workspace")
        self.assertEqual(event.data["counts"], {"outputs_deleted": 1, "runs_deleted": 1, "jobs_deleted": 1})

    def test_no_event_when_nothing_matched(self):
        sink = EventSink()
        emitted = []
        sink.set(emitted.append)

        _service(self.r, event_sink=sink).clear_pipeline_outputs(self.ws["_id"], "never-ran", owner_id="owner-1")

        # An event still fires (zero counts) — the UI needs to know the clear
        # happened even if there was nothing to clear.
        self.assertEqual(len(emitted), 1)
        self.assertEqual(emitted[0].data["counts"], {"outputs_deleted": 0, "runs_deleted": 0, "jobs_deleted": 0})


def _seed_processed_asset(r, *, sha, path, workspace_id, pipeline_id):
    asset = r.assets.upsert(
        content_sha256=sha, mime_type="image/jpeg", size_bytes=5, current_path=path, workspace_id=workspace_id,
    )
    job, _ = r.jobs.get_or_create(
        asset_id=asset["_id"], pipeline_id=pipeline_id, pipeline_version="v1", workspace_id=workspace_id,
    )
    run = _run_job(r, job["_id"], asset_id=asset["_id"], pipeline_id=pipeline_id, pipeline_version="v1")
    r.outputs.add(
        asset_id=asset["_id"], pipeline_run_id=run["_id"],
        model_name="yolo", model_version="v8n", output_type="detections",
        payload={"detections": [{"label": "car"}]},
        workspace_id=workspace_id, pipeline_id=pipeline_id, pipeline_version="v1",
    )
    r.jobs.complete(job["_id"])
    return asset, job


class ClearAssetPipelineOutputsCascadeTests(unittest.TestCase):
    def setUp(self):
        self.r = new_repos()
        self.workspace = self.r.workspaces.create(owner_id="owner-1", name="A", workspace_path="/photos")
        self.asset, self.job = _seed_processed_asset(
            self.r, sha="h1", path="/photos/a.jpg", workspace_id=self.workspace["_id"], pipeline_id="p1",
        )
        self.other_asset, self.other_job = _seed_processed_asset(
            self.r, sha="h2", path="/photos/b.jpg", workspace_id=self.workspace["_id"], pipeline_id="p1",
        )

    def test_reports_what_it_deleted(self):
        result = _service(self.r).clear_asset_pipeline_outputs(self.asset["_id"], "p1", owner_id="owner-1")
        self.assertEqual(result, {"outputs_deleted": 1, "runs_deleted": 1, "jobs_deleted": 1})

    def test_leaves_other_images_in_the_same_workspace_alone(self):
        _service(self.r).clear_asset_pipeline_outputs(self.asset["_id"], "p1", owner_id="owner-1")

        self.assertEqual(list(self.r.outputs.collection.find({"asset_id": self.asset["_id"]})), [])
        survivors = list(self.r.outputs.collection.find({"asset_id": self.other_asset["_id"]}))
        self.assertEqual(len(survivors), 1)
        self.assertEqual(self.r.jobs.get(self.other_job["_id"])["status"], "completed")

    def test_leaves_other_pipelines_on_the_same_image_alone(self):
        job, _ = self.r.jobs.get_or_create(
            asset_id=self.asset["_id"], pipeline_id="p2", pipeline_version="v1", workspace_id=self.workspace["_id"],
        )
        run = _run_job(self.r, job["_id"], asset_id=self.asset["_id"], pipeline_id="p2", pipeline_version="v1")
        self.r.outputs.add(
            asset_id=self.asset["_id"], pipeline_run_id=run["_id"],
            model_name="blip", model_version="v1", output_type="caption",
            payload={"text": "a cat"}, workspace_id=self.workspace["_id"],
            pipeline_id="p2", pipeline_version="v1",
        )
        self.r.jobs.complete(job["_id"])

        _service(self.r).clear_asset_pipeline_outputs(self.asset["_id"], "p1", owner_id="owner-1")

        remaining = list(self.r.outputs.collection.find({"asset_id": self.asset["_id"]}))
        self.assertEqual([o["pipeline_id"] for o in remaining], ["p2"])

    def test_the_pair_returns_to_not_started(self):
        _service(self.r).clear_asset_pipeline_outputs(self.asset["_id"], "p1", owner_id="owner-1")
        self.assertIsNone(self.r.jobs.get(self.job["_id"]))

    def test_sweeps_outputs_that_predate_the_denormalized_pipeline_id(self):
        """Older rows carry no pipeline_id and are reachable only via their run."""
        run = self.r.runs.list_for_job(self.job["_id"])[0]
        self.r.outputs.collection.insert_one({
            "_id": "legacy-1", "asset_id": self.asset["_id"], "pipeline_run_id": run["_id"],
            "pipeline_id": None, "output_type": "caption", "payload": {"text": "old"},
        })

        _service(self.r).clear_asset_pipeline_outputs(self.asset["_id"], "p1", owner_id="owner-1")

        self.assertIsNone(self.r.outputs.collection.find_one({"_id": "legacy-1"}))

    def test_clearing_an_untouched_pair_is_a_harmless_no_op(self):
        result = _service(self.r).clear_asset_pipeline_outputs(self.asset["_id"], "never-ran", owner_id="owner-1")
        self.assertEqual(result, {"outputs_deleted": 0, "runs_deleted": 0, "jobs_deleted": 0})

    def test_emits_outputs_cleared_scoped_to_the_asset(self):
        sink = EventSink()
        emitted = []
        sink.set(emitted.append)

        _service(self.r, event_sink=sink).clear_asset_pipeline_outputs(self.asset["_id"], "p1", owner_id="owner-1")

        self.assertEqual(len(emitted), 1)
        event = emitted[0]
        self.assertEqual(event.type, EVENT_OUTPUTS_CLEARED)
        self.assertEqual(event.workspace_id, self.workspace["_id"])
        self.assertEqual(event.asset_id, self.asset["_id"])
        self.assertEqual(event.data["scope"], "asset")


if __name__ == "__main__":
    unittest.main()
