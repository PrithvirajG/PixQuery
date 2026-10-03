"""/images, /jobs and /pipeline-nodes routes: auth scoping, status codes, side effects."""
import tempfile
import unittest
from pathlib import Path

from tests.api_client import FakePublisher, auth_headers, build_client, make_user


class ImageRouteFixture(unittest.TestCase):
    def setUp(self):
        FakePublisher.reset()
        self.client, self.r = build_client()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.owner = make_user(self.r, "owner")
        self.editor = make_user(self.r, "editor")
        self.viewer = make_user(self.r, "viewer")
        self.stranger = make_user(self.r, "stranger")
        self.pipeline = self.r.pipelines.create(owner_id=self.owner["_id"], name="P", nodes=[])
        self.ws = self.r.workspaces.create(
            owner_id=self.owner["_id"], name="W", workspace_path=self.tmp.name,
            pipeline_ids=[self.pipeline["_id"]], extensions=[".jpg"], active=True,
        )
        self.wid = self.ws["_id"]
        self.r.workspaces.add_member(self.wid, self.editor["_id"], "editor")
        self.r.workspaces.add_member(self.wid, self.viewer["_id"], "viewer")

        self.file = Path(self.tmp.name) / "cat.jpg"
        self.file.write_bytes(b"\xff\xd8fake-jpeg")
        self.asset = self.r.assets.upsert(
            content_sha256="h1", mime_type="image/jpeg", size_bytes=10,
            current_path=str(self.file), workspace_id=self.wid,
        )
        self.aid = self.asset["_id"]
        self.r.observations.upsert(
            asset_id=self.aid, workspace_id=self.wid, relative_path="cat.jpg",
            absolute_path=str(self.file), content_sha256="h1",
        )

    def as_(self, user):
        return auth_headers(user["_id"])


class ImageReadTests(ImageRouteFixture):
    def test_list_requires_auth(self):
        self.assertEqual(self.client.get("/images").status_code, 401)

    def test_member_sees_the_image_stranger_sees_nothing(self):
        mine = self.client.get("/images", headers=self.as_(self.viewer)).json()
        theirs = self.client.get("/images", headers=self.as_(self.stranger)).json()
        self.assertEqual([a["_id"] for a in mine], [self.aid])
        self.assertEqual(theirs, [])

    def test_get_image_is_scoped_by_workspace_membership(self):
        self.assertEqual(self.client.get(f"/images/{self.aid}", headers=self.as_(self.viewer)).status_code, 200)
        self.assertEqual(self.client.get(f"/images/{self.aid}", headers=self.as_(self.stranger)).status_code, 404)
        self.assertEqual(self.client.get("/images/nope", headers=self.as_(self.owner)).status_code, 404)

    def test_detail_is_scoped_too(self):
        ok = self.client.get(f"/images/{self.aid}/detail", headers=self.as_(self.owner))
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.json()["_id"], self.aid)
        self.assertEqual(
            self.client.get(f"/images/{self.aid}/detail", headers=self.as_(self.stranger)).status_code, 404
        )

    def test_thumbnail_serves_the_file_without_auth(self):
        res = self.client.get(f"/images/{self.aid}/thumbnail")
        self.assertEqual((res.status_code, res.content), (200, b"\xff\xd8fake-jpeg"))
        self.assertEqual(res.headers["content-type"], "image/jpeg")

    def test_thumbnail_404s(self):
        self.assertEqual(self.client.get("/images/nope/thumbnail").status_code, 404)
        self.file.unlink()
        res = self.client.get(f"/images/{self.aid}/thumbnail")
        self.assertEqual((res.status_code, res.json()["message"]), (404, "File not found on disk"))

    def test_written_image_for_an_unknown_output_is_404(self):
        self.assertEqual(self.client.get(f"/images/{self.aid}/outputs/nope/file").status_code, 404)


class ImageReprocessTests(ImageRouteFixture):
    def _reprocess(self, user, pipeline_id=None, asset_id=None):
        return self.client.post(
            f"/images/{asset_id or self.aid}/reprocess",
            json={"pipeline_id": pipeline_id or self.pipeline["_id"]},
            headers=self.as_(user),
        )

    def test_editor_reprocess_queues_and_publishes_the_job(self):
        res = self._reprocess(self.editor)
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual((body["asset_id"], body["status"]), (self.aid, "queued"))
        self.assertEqual(FakePublisher.published, [body["_id"]])

    def test_viewer_and_stranger_are_forbidden(self):
        for user in (self.viewer, self.stranger):
            with self.subTest(user=user["username"]):
                self.assertEqual(self._reprocess(user).status_code, 403)
        self.assertEqual(FakePublisher.published, [])

    def test_a_pipeline_not_attached_to_the_workspace_is_409(self):
        other = self.r.pipelines.create(owner_id=self.owner["_id"], name="Other", nodes=[])
        res = self._reprocess(self.owner, pipeline_id=other["_id"])
        self.assertEqual(res.status_code, 409)

    def test_unknown_image_or_missing_pipeline_definition_is_404(self):
        self.assertEqual(self._reprocess(self.owner, asset_id="nope").status_code, 404)
        self.r.workspaces.update(self.wid, {"pipeline_ids": ["ghost"]})
        self.assertEqual(self._reprocess(self.owner, pipeline_id="ghost").status_code, 404)

    def test_requires_auth(self):
        res = self.client.post(f"/images/{self.aid}/reprocess", json={"pipeline_id": "p"})
        self.assertEqual(res.status_code, 401)


class ImageClearOutputsTests(ImageRouteFixture):
    def _clear(self, user):
        return self.client.delete(
            f"/images/{self.aid}/outputs/{self.pipeline['_id']}", headers=self.as_(user)
        )

    def test_editor_can_clear_one_images_outputs(self):
        self.assertEqual(self._clear(self.editor).status_code, 200)

    def test_viewer_is_forbidden_and_stranger_gets_404(self):
        self.assertEqual(self._clear(self.viewer).status_code, 403)
        self.assertEqual(self._clear(self.stranger).status_code, 404)


class JobRouteTests(ImageRouteFixture):
    def _job(self, status="failed"):
        job, _ = self.r.jobs.get_or_create(
            asset_id=self.aid, pipeline_id=self.pipeline["_id"], pipeline_version="v1",
            workspace_id=self.wid,
        )
        if status == "failed":
            self.r.jobs.fail(job["_id"], final_status="failed", next_attempt_at=None,
                             error={"class": "X", "message": "boom"})
        return job

    def test_list_jobs_and_status_filter(self):
        job = self._job("failed")
        everything = self.client.get("/jobs").json()
        failed = self.client.get("/jobs", params={"status": "failed"}).json()
        completed = self.client.get("/jobs", params={"status": "completed"}).json()
        self.assertEqual([j["_id"] for j in everything], [job["_id"]])
        self.assertEqual([j["_id"] for j in failed], [job["_id"]])
        self.assertEqual(completed, [])

    def test_requeue_resets_the_job_and_publishes_it(self):
        job = self._job("failed")
        res = self.client.post(f"/jobs/{job['_id']}/requeue")
        self.assertEqual((res.status_code, res.json()["status"]), (200, "queued"))
        self.assertEqual(FakePublisher.published, [job["_id"]])

    def test_requeue_unknown_job_is_404(self):
        res = self.client.post("/jobs/nope/requeue")
        self.assertEqual(res.status_code, 404)
        self.assertEqual(FakePublisher.published, [])


class PipelineNodeRouteTests(ImageRouteFixture):
    def test_requires_auth(self):
        self.assertEqual(self.client.get("/pipeline-nodes").status_code, 401)

    def test_lists_the_seeded_system_nodes_with_model_catalogs(self):
        nodes = self.client.get("/pipeline-nodes", headers=self.as_(self.owner)).json()
        by_type = {n["node_type"]: n for n in nodes}
        self.assertIn("vision_language_model", by_type)
        self.assertEqual(
            {m["id"] for m in by_type["vision_language_model"]["models"]},
            {"blip", "qwen2_vl_2b", "moondream2"},
        )

    def test_creating_a_node_is_disabled(self):
        res = self.client.post(
            "/pipeline-nodes", json={"name": "N", "node_type": "custom"}, headers=self.as_(self.owner)
        )
        self.assertEqual(res.status_code, 403)

    def test_unknown_or_system_nodes_cannot_be_updated_or_deleted(self):
        nodes = self.client.get("/pipeline-nodes", headers=self.as_(self.owner)).json()
        system_id = nodes[0]["_id"]
        for node_id in ("nope", system_id):
            with self.subTest(node_id=node_id):
                put = self.client.put(
                    f"/pipeline-nodes/{node_id}", json={"name": "X"}, headers=self.as_(self.owner)
                )
                delete = self.client.delete(f"/pipeline-nodes/{node_id}", headers=self.as_(self.owner))
                self.assertEqual((put.status_code, delete.status_code), (404, 404))


if __name__ == "__main__":
    unittest.main()
