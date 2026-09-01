"""StatsService.get_overview and list_recent_jobs.

No test exercised these before the per-collection migration — not at the old
god-repository level, not through the service. Covers the composition now:
counts are scoped to the owner's accessible assets/workspaces, not global.
"""
import unittest

from src.services.stats_service import StatsService
from tests.repo_factory import new_repos


def _stats_service(r):
    return StatsService(
        workspaces=r.workspaces, observations=r.observations, assets=r.assets,
        pipelines=r.pipelines, jobs=r.jobs,
    )


class StatsOverviewTests(unittest.TestCase):
    def setUp(self):
        self.r = new_repos()
        self.owner = self.r.users.create("alice", "hash")
        self.ws = self.r.workspaces.create(
            owner_id=self.owner["_id"], name="ws", workspace_path="/photos"
        )
        self.pipeline = self.r.pipelines.create(owner_id=self.owner["_id"], name="P", nodes=[])

    def _add_asset(self, sha, path, workspace=None):
        workspace = workspace or self.ws
        asset = self.r.assets.upsert(
            content_sha256=sha, mime_type="image/jpeg", size_bytes=1,
            current_path=path, workspace_id=workspace["_id"],
        )
        self.r.observations.upsert(
            asset_id=asset["_id"], workspace_id=workspace["_id"],
            relative_path=path.rsplit("/", 1)[-1], absolute_path=path, content_sha256=sha,
        )
        return asset

    def test_counts_reflect_owned_data(self):
        self._add_asset("h1", "/photos/a.jpg")
        self._add_asset("h2", "/photos/b.jpg")

        overview = _stats_service(self.r).get_overview(owner_id=self.owner["_id"])

        self.assertEqual(overview["total_images"], 2)
        self.assertEqual(overview["active_workspaces"], 1)
        self.assertEqual(overview["pipelines_defined"], 1)
        self.assertEqual(overview["jobs_queued"], 0)

    def test_another_users_assets_are_not_counted(self):
        stranger = self.r.users.create("bob", "hash")
        other_ws = self.r.workspaces.create(
            owner_id=stranger["_id"], name="theirs", workspace_path="/other"
        )
        self._add_asset("h1", "/other/x.jpg", workspace=other_ws)

        overview = _stats_service(self.r).get_overview(owner_id=self.owner["_id"])

        self.assertEqual(overview["total_images"], 0)

    def test_job_status_counts_are_scoped_to_accessible_assets(self):
        asset = self._add_asset("h1", "/photos/a.jpg")
        self.r.jobs.get_or_create(
            asset_id=asset["_id"], pipeline_id=self.pipeline["_id"], pipeline_version="v1",
            workspace_id=self.ws["_id"],
        )

        stranger = self.r.users.create("bob", "hash")
        other_ws = self.r.workspaces.create(
            owner_id=stranger["_id"], name="theirs", workspace_path="/other"
        )
        other_asset = self._add_asset("h2", "/other/y.jpg", workspace=other_ws)
        self.r.jobs.get_or_create(
            asset_id=other_asset["_id"], pipeline_id=self.pipeline["_id"], pipeline_version="v1",
            workspace_id=other_ws["_id"],
        )

        overview = _stats_service(self.r).get_overview(owner_id=self.owner["_id"])

        self.assertEqual(overview["jobs_queued"], 1)  # only alice's job

    def test_inactive_workspace_is_not_counted_as_active(self):
        self.r.workspaces.update(self.ws["_id"], {"active": False})
        overview = _stats_service(self.r).get_overview(owner_id=self.owner["_id"])
        self.assertEqual(overview["active_workspaces"], 0)


class ListRecentJobsTests(unittest.TestCase):
    def setUp(self):
        self.r = new_repos()
        self.owner = self.r.users.create("alice", "hash")
        self.ws = self.r.workspaces.create(
            owner_id=self.owner["_id"], name="ws", workspace_path="/photos"
        )
        self.asset = self.r.assets.upsert(
            content_sha256="h1", mime_type="image/jpeg", size_bytes=1,
            current_path="/photos/a.jpg", workspace_id=self.ws["_id"],
        )
        self.r.observations.upsert(
            asset_id=self.asset["_id"], workspace_id=self.ws["_id"],
            relative_path="a.jpg", absolute_path="/photos/a.jpg", content_sha256="h1",
        )
        self.job, _ = self.r.jobs.get_or_create(
            asset_id=self.asset["_id"], pipeline_id="p1", pipeline_version="v1",
            workspace_id=self.ws["_id"],
        )

    def test_scoped_to_user_returns_only_accessible_jobs(self):
        stranger = self.r.users.create("bob", "hash")
        other_ws = self.r.workspaces.create(
            owner_id=stranger["_id"], name="theirs", workspace_path="/other"
        )
        other_asset = self.r.assets.upsert(
            content_sha256="h2", mime_type="image/jpeg", size_bytes=1,
            current_path="/other/x.jpg", workspace_id=other_ws["_id"],
        )
        self.r.observations.upsert(
            asset_id=other_asset["_id"], workspace_id=other_ws["_id"],
            relative_path="x.jpg", absolute_path="/other/x.jpg", content_sha256="h2",
        )
        self.r.jobs.get_or_create(
            asset_id=other_asset["_id"], pipeline_id="p1", pipeline_version="v1",
            workspace_id=other_ws["_id"],
        )

        jobs = _stats_service(self.r).list_recent_jobs(user_id=self.owner["_id"])

        self.assertEqual([j["_id"] for j in jobs], [self.job["_id"]])

    def test_unscoped_returns_every_job(self):
        stranger = self.r.users.create("bob", "hash")
        other_ws = self.r.workspaces.create(
            owner_id=stranger["_id"], name="theirs", workspace_path="/other"
        )
        other_asset = self.r.assets.upsert(
            content_sha256="h2", mime_type="image/jpeg", size_bytes=1,
            current_path="/other/x.jpg", workspace_id=other_ws["_id"],
        )
        other_job, _ = self.r.jobs.get_or_create(
            asset_id=other_asset["_id"], pipeline_id="p1", pipeline_version="v1",
            workspace_id=other_ws["_id"],
        )

        jobs = _stats_service(self.r).list_recent_jobs(user_id=None)

        self.assertEqual({j["_id"] for j in jobs}, {self.job["_id"], other_job["_id"]})

    def test_respects_limit(self):
        for i in range(3):
            self.r.jobs.get_or_create(
                asset_id=self.asset["_id"], pipeline_id=f"p{i}", pipeline_version="v1",
                workspace_id=self.ws["_id"],
            )
        jobs = _stats_service(self.r).list_recent_jobs(user_id=self.owner["_id"], limit=2)
        self.assertEqual(len(jobs), 2)


if __name__ == "__main__":
    unittest.main()
