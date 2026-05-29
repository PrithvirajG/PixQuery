"""HTTP route modules."""

from src.api.routes.auth import router as auth_router
from src.api.routes.images import router as images_router
from src.api.routes.jobs import router as jobs_router
from src.api.routes.pipeline_nodes import router as pipeline_nodes_router
from src.api.routes.pipelines import router as pipelines_router
from src.api.routes.search import router as search_router
from src.api.routes.stats import router as stats_router
from src.api.routes.status import router as status_router
from src.api.routes.websocket import router as websocket_router
from src.api.routes.workspaces import router as workspaces_router

__all__ = [
    "auth_router",
    "images_router",
    "jobs_router",
    "pipeline_nodes_router",
    "pipelines_router",
    "search_router",
    "stats_router",
    "status_router",
    "websocket_router",
    "workspaces_router",
]
