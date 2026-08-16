from functools import lru_cache
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from src.config import MONGO_DB_NAME, MONGO_URI
from src.infrastructure.messaging import RabbitPublisher
from src.repositories import MongoPipelineRepository
from src.services import ImageService, JobService, PipelineService, SearchService, StatsService, WorkspaceService
from src.api.security import decode_access_token


@lru_cache
def get_pipeline_repository() -> MongoPipelineRepository:
    return MongoPipelineRepository.from_uri(MONGO_URI, MONGO_DB_NAME)


def get_image_service() -> ImageService:
    return ImageService(get_pipeline_repository())


def get_job_service() -> JobService:
    return JobService(get_pipeline_repository(), publisher_factory=RabbitPublisher)


@lru_cache
def get_search_service() -> SearchService:
    return SearchService(get_pipeline_repository())


def get_pipeline_service() -> PipelineService:
    return PipelineService(get_pipeline_repository())


def get_workspace_service() -> WorkspaceService:
    return WorkspaceService(get_pipeline_repository())


def get_stats_service() -> StatsService:
    return StatsService(get_pipeline_repository())


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)


async def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    repo: MongoPipelineRepository = Depends(get_pipeline_repository)
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
    user = repo.get_user(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
