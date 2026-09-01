from functools import lru_cache
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from src.config import MONGO_DB_NAME, MONGO_URI
from src.infrastructure.messaging import EventSink, RabbitPublisher
from src.repositories import (
    FileObservationsRepository,
    ImageAssetsRepository,
    ModelOutputsRepository,
    PipelineDefinitionsRepository,
    PipelineNodesRepository,
    PipelineRunsRepository,
    ProcessingJobsRepository,
    UsersRepository,
    WorkspaceDefinitionsRepository,
)
from src.services import ImageService, JobService, PipelineService, SearchService, StatsService, WorkspaceService
from src.api.security import decode_access_token


@lru_cache
def get_database():
    """The one live Mongo connection every repository below shares.

    Bootstraps the schema (indexes + seeded system nodes) on first access —
    the API also runs migrations at startup (``RUN_MIGRATIONS_ON_STARTUP``),
    which covers this redundantly but idempotently; this call is what makes a
    fresh checkout usable even with migrations disabled.
    """
    from pymongo import MongoClient

    from src.repositories.bootstrap import ensure_schema

    db = MongoClient(MONGO_URI)[MONGO_DB_NAME]
    ensure_schema(db)
    return db


@lru_cache
def get_image_assets_repository() -> ImageAssetsRepository:
    return ImageAssetsRepository(get_database())


@lru_cache
def get_file_observations_repository() -> FileObservationsRepository:
    return FileObservationsRepository(get_database())


@lru_cache
def get_processing_jobs_repository() -> ProcessingJobsRepository:
    return ProcessingJobsRepository(get_database())


@lru_cache
def get_pipeline_runs_repository() -> PipelineRunsRepository:
    return PipelineRunsRepository(get_database())


@lru_cache
def get_model_outputs_repository() -> ModelOutputsRepository:
    return ModelOutputsRepository(get_database())


@lru_cache
def get_users_repository() -> UsersRepository:
    return UsersRepository(get_database())


@lru_cache
def get_pipeline_nodes_repository() -> PipelineNodesRepository:
    return PipelineNodesRepository(get_database())


@lru_cache
def get_pipeline_definitions_repository() -> PipelineDefinitionsRepository:
    return PipelineDefinitionsRepository(get_database())


@lru_cache
def get_workspace_definitions_repository() -> WorkspaceDefinitionsRepository:
    return WorkspaceDefinitionsRepository(get_database())


@lru_cache
def get_event_sink() -> EventSink:
    """Shared sink migrated services emit through; wired to the real bus by
    ``_start_event_bus`` once the app's event loop exists. Until every service
    is migrated, ``app.py`` also arms the old facade's own sink — see its
    ``_start_event_bus`` for why both are set during the transition."""
    return EventSink()


# Services are stateless wrappers around repositories, so they are all cached
# alike — building a new instance per request bought nothing but noise, and the
# previous mix of cached and uncached providers implied a distinction that did
# not exist.


@lru_cache
def get_image_service() -> ImageService:
    return ImageService(
        assets=get_image_assets_repository(),
        observations=get_file_observations_repository(),
        workspaces=get_workspace_definitions_repository(),
        pipelines=get_pipeline_definitions_repository(),
        jobs=get_processing_jobs_repository(),
        runs=get_pipeline_runs_repository(),
        outputs=get_model_outputs_repository(),
    )


@lru_cache
def get_job_service() -> JobService:
    return JobService(
        jobs=get_processing_jobs_repository(),
        assets=get_image_assets_repository(),
        workspaces=get_workspace_definitions_repository(),
        pipelines=get_pipeline_definitions_repository(),
        publisher_factory=RabbitPublisher,
    )


@lru_cache
def get_search_service() -> SearchService:
    # The vector store and query encoder are left to their lazy defaults here;
    # tests inject stubs by constructing SearchService directly.
    return SearchService(
        assets=get_image_assets_repository(),
        observations=get_file_observations_repository(),
        workspaces=get_workspace_definitions_repository(),
        outputs=get_model_outputs_repository(),
    )


@lru_cache
def get_pipeline_service() -> PipelineService:
    return PipelineService(
        pipelines=get_pipeline_definitions_repository(),
        nodes=get_pipeline_nodes_repository(),
        runs=get_pipeline_runs_repository(),
        outputs=get_model_outputs_repository(),
        jobs=get_processing_jobs_repository(),
        workspaces=get_workspace_definitions_repository(),
        event_sink=get_event_sink(),
    )


@lru_cache
def get_workspace_service() -> WorkspaceService:
    return WorkspaceService(
        workspaces=get_workspace_definitions_repository(),
        users=get_users_repository(),
        assets=get_image_assets_repository(),
        observations=get_file_observations_repository(),
        jobs=get_processing_jobs_repository(),
        runs=get_pipeline_runs_repository(),
        outputs=get_model_outputs_repository(),
        event_sink=get_event_sink(),
    )


@lru_cache
def get_stats_service() -> StatsService:
    return StatsService(
        workspaces=get_workspace_definitions_repository(),
        observations=get_file_observations_repository(),
        assets=get_image_assets_repository(),
        pipelines=get_pipeline_definitions_repository(),
        jobs=get_processing_jobs_repository(),
    )


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)


async def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    users: UsersRepository = Depends(get_users_repository),
) -> dict:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = users.get(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
