"""Repository implementations.

Nine repositories, one per MongoDB collection, each pure CRUD against exactly
one collection — no cascades, no policy, no event emission. Cross-collection
orchestration lives in the service that owns the operation (see
``services/access_scope.py`` and any service composing more than one of these).
Call ``repositories.bootstrap.ensure_schema(db)`` once per process, against a
shared connection, before using any of them — see ``api/dependencies.py`` for
the pattern.
"""

from src.repositories.file_observations_repository import FileObservationsRepository
from src.repositories.image_assets_repository import ImageAssetsRepository
from src.repositories.model_outputs_repository import ModelOutputsRepository
from src.repositories.pipeline_definitions_repository import PipelineDefinitionsRepository
from src.repositories.pipeline_nodes_repository import PipelineNodesRepository
from src.repositories.pipeline_runs_repository import PipelineRunsRepository
from src.repositories.processing_jobs_repository import ProcessingJobsRepository
from src.repositories.users_repository import UsersRepository
from src.repositories.workspace_definitions_repository import WorkspaceDefinitionsRepository

__all__ = [
    "FileObservationsRepository",
    "ImageAssetsRepository",
    "ModelOutputsRepository",
    "PipelineDefinitionsRepository",
    "PipelineNodesRepository",
    "PipelineRunsRepository",
    "ProcessingJobsRepository",
    "UsersRepository",
    "WorkspaceDefinitionsRepository",
]
