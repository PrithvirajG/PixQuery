"""Builds the 9 per-collection repositories against a shared fake database.

No facade involved: ``FakeDatabase`` (from ``src.repositories.fake_mongo``) is
the same collection-agnostic pymongo stand-in the real repositories use against
a live Mongo, so building all 9 off one shared instance is enough for any test
to write through one repo and read it back through another.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.repositories.fake_mongo import FakeDatabase
from src.repositories.file_observations_repository import FileObservationsRepository
from src.repositories.image_assets_repository import ImageAssetsRepository
from src.repositories.model_outputs_repository import ModelOutputsRepository
from src.repositories.pipeline_definitions_repository import PipelineDefinitionsRepository
from src.repositories.pipeline_nodes_repository import PipelineNodesRepository
from src.repositories.pipeline_runs_repository import PipelineRunsRepository
from src.repositories.processing_jobs_repository import ProcessingJobsRepository
from src.repositories.users_repository import UsersRepository
from src.repositories.workspace_definitions_repository import WorkspaceDefinitionsRepository


@dataclass
class Repos:
    assets: ImageAssetsRepository
    observations: FileObservationsRepository
    jobs: ProcessingJobsRepository
    runs: PipelineRunsRepository
    outputs: ModelOutputsRepository
    users: UsersRepository
    nodes: PipelineNodesRepository
    pipelines: PipelineDefinitionsRepository
    workspaces: WorkspaceDefinitionsRepository


def repos_from_database(db) -> Repos:
    return Repos(
        assets=ImageAssetsRepository(db),
        observations=FileObservationsRepository(db),
        jobs=ProcessingJobsRepository(db),
        runs=PipelineRunsRepository(db),
        outputs=ModelOutputsRepository(db),
        users=UsersRepository(db),
        nodes=PipelineNodesRepository(db),
        pipelines=PipelineDefinitionsRepository(db),
        workspaces=WorkspaceDefinitionsRepository(db),
    )


def new_repos(*, seed_system_nodes: bool = True) -> Repos:
    """Build all 9 repositories against a fresh, shared FakeDatabase.

    ``seed_system_nodes`` mirrors what the real app does at startup (every
    process seeds the pipeline-node library) — on by default so tests see the
    same system nodes (object_detection, captioning, ...) production does,
    matching what the old ``InMemoryPipelineRepository`` did implicitly.
    """
    repos = repos_from_database(FakeDatabase())
    if seed_system_nodes:
        repos.nodes.seed_system_nodes()
    return repos
