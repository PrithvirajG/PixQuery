from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.api.errors import register_error_handlers
from src.api.router import api_router
from src.config import (
    EVENTS_ENABLED,
    MONGO_DB_NAME,
    MONGO_URI,
    RUN_MIGRATIONS_ON_STARTUP,
    WATCH_ROOT,
)

logger = logging.getLogger("pixquery.api")

# Fail fast at startup rather than waiting out pymongo's 30s default so an
# operator sees the problem immediately instead of after a long hang.
_STARTUP_MONGO_TIMEOUT_MS = 3000


def _run_startup_migrations() -> None:
    from pymongo import MongoClient
    from pymongo.errors import PyMongoError

    from src.migrations import run_migrations

    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=_STARTUP_MONGO_TIMEOUT_MS)
    try:
        run_migrations(client[MONGO_DB_NAME])
    except PyMongoError as exc:
        # A clean, actionable message beats a 60-line pymongo traceback. Raising
        # RuntimeError still aborts startup (the API is useless without Mongo),
        # but Starlette logs just this line.
        raise RuntimeError(
            f"Cannot reach MongoDB at {MONGO_URI}. Is the infrastructure running? "
            "Start it with: docker compose -f docker-compose.infra.yml up -d "
            f"(pymongo: {exc.__class__.__name__})"
        ) from None
    finally:
        client.close()


async def _start_event_bus() -> None:
    """Let API-side mutations broadcast too.

    Deleting outputs or hitting Reprocess changes state just as much as the worker
    does; without this the acting tab would update while every other open tab sat
    stale until its next refetch.

    Every API-process service emits through the shared ``EventSink`` (see
    dependencies.py's ``get_event_sink()``), so only that one needs arming here.
    The worker and monitor processes each hold and arm their own ``EventSink``
    the same way — see ``consumer/processing/image_task_consumer.py`` and
    ``consumer/ingestion/worker.py``.
    """
    if not EVENTS_ENABLED:
        return
    from src.api.dependencies import get_event_sink
    from src.publisher.events import EventPublisher

    try:
        bus = EventPublisher()
        await bus.connect()
    except Exception as exc:
        logger.warning("Live events disabled in API: %s", exc)
        return
    _state["event_bus"] = bus
    get_event_sink().set(bus.emit)


async def _stop_event_bus() -> None:
    from src.api.routes.ws.events_socket import reset_subscriber

    bus = _state.pop("event_bus", None)
    if bus:
        await bus.close()
    await reset_subscriber()


# Process-wide handles that outlive a request but aren't per-request state.
_state: dict = {}


def create_app() -> FastAPI:
    app = FastAPI(title="PixQuery API")

    if RUN_MIGRATIONS_ON_STARTUP:
        app.add_event_handler("startup", _run_startup_migrations)
    app.add_event_handler("startup", _start_event_bus)
    app.add_event_handler("shutdown", _stop_event_bus)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        # LAN access: any private-network device hitting the dev server on :3000
        # (e.g. http://192.168.1.4:3000). Kept as a regex (not "*") so it still
        # works with allow_credentials=True, which the wildcard forbids.
        allow_origin_regex=r"http://(192\.168|10\.\d{1,3}|172\.(1[6-9]|2\d|3[01]))\.\d{1,3}\.\d{1,3}:3000",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_error_handlers(app)

    photo_dir = Path(WATCH_ROOT)
    photo_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/images_source", StaticFiles(directory=str(photo_dir)), name="images_source")
    app.include_router(api_router)
    return app

