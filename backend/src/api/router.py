from fastapi import APIRouter

from src.api.routes import (
    auth_router,
    images_router,
    jobs_router,
    pipeline_nodes_router,
    pipelines_router,
    search_router,
    stats_router,
    status_router,
    websocket_router,
    workspaces_router,
)

api_router = APIRouter()
api_router.include_router(status_router)
api_router.include_router(auth_router)
api_router.include_router(images_router)
api_router.include_router(jobs_router)
api_router.include_router(search_router)
api_router.include_router(websocket_router)
api_router.include_router(pipeline_nodes_router)
api_router.include_router(pipelines_router)
api_router.include_router(workspaces_router)
api_router.include_router(stats_router)
