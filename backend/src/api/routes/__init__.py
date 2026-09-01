"""HTTP and WebSocket route modules — see rest/ and ws/."""

from src.api.routes.rest.auth import router as auth_router
from src.api.routes.rest.images import router as images_router
from src.api.routes.rest.jobs import router as jobs_router
from src.api.routes.rest.pipeline_nodes import router as pipeline_nodes_router
from src.api.routes.rest.pipelines import router as pipelines_router
from src.api.routes.rest.search import router as search_router
from src.api.routes.rest.stats import router as stats_router
from src.api.routes.rest.status import router as status_router
from src.api.routes.rest.workspaces import router as workspaces_router
from src.api.routes.ws.events_socket import router as websocket_router

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
