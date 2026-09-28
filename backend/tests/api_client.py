"""HTTP-level test harness: the real FastAPI app on an in-memory FakeDatabase.

``build_client()`` builds the production app (``src.api.app.create_app``), then
overrides every dependency getter in ``src/api/dependencies.py`` so repositories
and services run against a fresh ``FakeDatabase``. Requests go through real
routing, auth, validation and the error-envelope handlers. Nothing touches Mongo,
RabbitMQ or the network: ``TestClient`` is used without a ``with`` block, so the
app's startup hooks (migrations, event bus) never run.
"""
from __future__ import annotations

import tempfile
from unittest import mock

from fastapi.testclient import TestClient

from src.api import dependencies as deps
from src.api.security import create_access_token, hash_password
from src.services import (
    ImageService,
    JobService,
    PipelineService,
    SearchService,
    StatsService,
    WorkspaceService,
)
from tests.repo_factory import Repos, new_repos


class FakePublisher:
    """Stands in for ``RabbitPublisher``; records published messages."""

    published: list[str] = []
    fail_connect: bool = False

    def __init__(self, *args, **kwargs):
        pass

    async def connect(self):
        if type(self).fail_connect:
            raise ConnectionError("broker down")

    async def publish(self, message, **kwargs):
        type(self).published.append(message)

    async def close(self):
        pass

    @classmethod
    def reset(cls):
        cls.published = []
        cls.fail_connect = False


def build_client(repos: Repos | None = None) -> tuple[TestClient, Repos]:
    repos = repos or new_repos()
    # create_app() mounts WATCH_ROOT as static files (and mkdirs it); point it at
    # a throwaway directory so tests never touch ~/pixquery_photos.
    with mock.patch("src.api.app.WATCH_ROOT", tempfile.mkdtemp()):
        from src.api.app import create_app

        app = create_app()

    o = app.dependency_overrides
    o[deps.get_users_repository] = lambda: repos.users
    o[deps.get_image_assets_repository] = lambda: repos.assets
    o[deps.get_file_observations_repository] = lambda: repos.observations
    o[deps.get_processing_jobs_repository] = lambda: repos.jobs
    o[deps.get_pipeline_runs_repository] = lambda: repos.runs
    o[deps.get_model_outputs_repository] = lambda: repos.outputs
    o[deps.get_pipeline_nodes_repository] = lambda: repos.nodes
    o[deps.get_pipeline_definitions_repository] = lambda: repos.pipelines
    o[deps.get_workspace_definitions_repository] = lambda: repos.workspaces
    o[deps.get_workspace_service] = lambda: WorkspaceService(
        workspaces=repos.workspaces, users=repos.users, assets=repos.assets,
        observations=repos.observations, jobs=repos.jobs, runs=repos.runs,
        outputs=repos.outputs,
    )
    o[deps.get_pipeline_service] = lambda: PipelineService(
        pipelines=repos.pipelines, nodes=repos.nodes, runs=repos.runs,
        outputs=repos.outputs, jobs=repos.jobs, workspaces=repos.workspaces,
    )
    o[deps.get_job_service] = lambda: JobService(
        jobs=repos.jobs, assets=repos.assets, workspaces=repos.workspaces,
        pipelines=repos.pipelines, publisher_factory=FakePublisher,
    )
    o[deps.get_image_service] = lambda: ImageService(
        assets=repos.assets, observations=repos.observations,
        workspaces=repos.workspaces, pipelines=repos.pipelines, jobs=repos.jobs,
        runs=repos.runs, outputs=repos.outputs,
    )
    o[deps.get_search_service] = lambda: SearchService(
        assets=repos.assets, observations=repos.observations,
        workspaces=repos.workspaces, outputs=repos.outputs,
    )
    o[deps.get_stats_service] = lambda: StatsService(
        workspaces=repos.workspaces, observations=repos.observations,
        assets=repos.assets, pipelines=repos.pipelines, jobs=repos.jobs,
    )
    # raise_server_exceptions=False: let unhandled errors reach the 500 envelope
    # handler instead of re-raising into the test.
    return TestClient(app, raise_server_exceptions=False), repos


def auth_headers(user_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token({'sub': user_id})}"}


def make_user(repos: Repos, username: str, password: str = "secret1") -> dict:
    return repos.users.create(username, hash_password(password))
