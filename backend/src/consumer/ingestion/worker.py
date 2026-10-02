"""Filesystem monitoring worker entry point.

Runs ``WorkspaceWatcher`` only — live file-system events plus the periodic
safety-net reconcile. The manual "Scan" button no longer has any consumer
here: the API's ``/scan`` route lists the workspace and publishes observations
itself (see ``api/routes/rest/workspaces.py``), so Scan works whenever the API
and pipeline-worker are running, independent of this process. This process is
now purely a *detector*: it never touches ``image_assets``/
``file_observations``/``processing_jobs``.
"""
from __future__ import annotations

import asyncio

from src.config import MONGO_DB_NAME, MONGO_URI, WORKSPACE_REFRESH_INTERVAL
from src.consumer.ingestion.filesystem_watcher import WorkspaceWatcher
from src.infrastructure.messaging import RabbitPublisher
from src.logging_config import get_logger
from src.repositories.bootstrap import ensure_schema
from src.repositories.file_observations_repository import FileObservationsRepository
from src.repositories.image_assets_repository import ImageAssetsRepository
from src.repositories.workspace_definitions_repository import WorkspaceDefinitionsRepository

logger = get_logger(__name__)


async def start_file_watcher() -> None:
    """Start the multi-workspace monitor driven entirely by workspace_definitions in MongoDB."""
    # One live connection, shared by every repository below — bootstrapped once
    # here (index creation, system-node seeding), same as api/dependencies.py.
    from pymongo import MongoClient

    database = MongoClient(MONGO_URI)[MONGO_DB_NAME]
    ensure_schema(database)
    workspaces = WorkspaceDefinitionsRepository(database)
    assets = ImageAssetsRepository(database)
    observations = FileObservationsRepository(database)

    publisher = RabbitPublisher()
    await publisher.connect()

    loop = asyncio.get_running_loop()
    watcher = WorkspaceWatcher(
        workspaces=workspaces,
        assets=assets,
        observations=observations,
        publisher=publisher,
        loop=loop,
    )

    # Initial sync
    await watcher.sync()

    logger.info(
        "Monitor running. Workspace refresh every %ds.", WORKSPACE_REFRESH_INTERVAL
    )

    try:
        while True:
            await asyncio.sleep(WORKSPACE_REFRESH_INTERVAL)
            # Re-read workspace definitions and start/stop observers as needed
            await watcher.sync()
            # Periodic full reconcile for all active workspaces
            await watcher.reconcile_all()
    finally:
        watcher.stop_all()
        await publisher.close()
