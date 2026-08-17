from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.api.errors import register_error_handlers
from src.api.router import api_router
from src.config import MONGO_DB_NAME, MONGO_URI, RUN_MIGRATIONS_ON_STARTUP, WATCH_ROOT

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


def create_app() -> FastAPI:
    app = FastAPI(title="PixQuery API")

    if RUN_MIGRATIONS_ON_STARTUP:
        app.add_event_handler("startup", _run_startup_migrations)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
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

