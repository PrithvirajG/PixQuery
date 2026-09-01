"""Schema bootstrap: every collection's indexes, plus the seeded system nodes.

The one place that composes all 9 per-collection repositories for their startup
side effect. Each process (API, worker, monitor) and the migration runner all
need this exact bootstrap — previously each got it "for free" as a side effect
of constructing the god-repository (``MongoPipelineRepository.__init__`` called
``ensure_indexes()``); now that repositories are pure and side-effect-free at
construction, whoever owns a connection calls this explicitly, once, at startup.
"""

from __future__ import annotations

from typing import Any


def ensure_schema(db: Any) -> None:
    from src.repositories.file_observations_repository import FileObservationsRepository
    from src.repositories.image_assets_repository import ImageAssetsRepository
    from src.repositories.model_outputs_repository import ModelOutputsRepository
    from src.repositories.pipeline_definitions_repository import PipelineDefinitionsRepository
    from src.repositories.pipeline_nodes_repository import PipelineNodesRepository
    from src.repositories.processing_jobs_repository import ProcessingJobsRepository
    from src.repositories.users_repository import UsersRepository
    from src.repositories.workspace_definitions_repository import WorkspaceDefinitionsRepository

    ImageAssetsRepository(db).ensure_indexes()
    FileObservationsRepository(db).ensure_indexes()
    ProcessingJobsRepository(db).ensure_indexes()
    ModelOutputsRepository(db).ensure_indexes()
    UsersRepository(db).ensure_indexes()
    PipelineDefinitionsRepository(db).ensure_indexes()
    WorkspaceDefinitionsRepository(db).ensure_indexes()
    nodes = PipelineNodesRepository(db)
    nodes.ensure_indexes()
    nodes.seed_system_nodes()
