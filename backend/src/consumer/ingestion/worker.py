"""Filesystem monitoring worker entry point.

Consolidates the monitor process's two consumers: ``WorkspaceWatcher``
(filesystem-driven, one watchdog Observer per workspace) and
``ScanCommandConsumer`` (RabbitMQ-driven, one manual re-scan request per
message) — see ``filesystem_watcher.py`` and ``scan_command_consumer.py``.
"""
from __future__ import annotations

import asyncio

from src.config import EVENTS_ENABLED, MONGO_DB_NAME, MONGO_URI, WORKSPACE_REFRESH_INTERVAL
from src.consumer.ingestion.filesystem_watcher import WorkspaceWatcher, logger
from src.consumer.ingestion.scan_command_consumer import ScanCommandConsumer
from src.infrastructure.messaging import EventSink, RabbitPublisher
from src.publisher.events import EventPublisher
from src.repositories.bootstrap import ensure_schema
from src.repositories.file_observations_repository import FileObservationsRepository
from src.repositories.image_assets_repository import ImageAssetsRepository
from src.repositories.pipeline_definitions_repository import PipelineDefinitionsRepository
from src.repositories.processing_jobs_repository import ProcessingJobsRepository
from src.repositories.workspace_definitions_repository import WorkspaceDefinitionsRepository


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
    jobs = ProcessingJobsRepository(database)
    pipelines = PipelineDefinitionsRepository(database)

    publisher = RabbitPublisher()
    await publisher.connect()

    # The monitor is where a newly-discovered image first becomes a queued job, so
    # it emits the transition that makes an image appear as "Queued" in an open UI.
    event_sink = EventSink()
    bus = None
    if EVENTS_ENABLED:
        try:
            candidate = EventPublisher()
            await candidate.connect()
            bus = candidate
            event_sink.set(bus.emit)
        except Exception as exc:
            logger.warning("Live events disabled in monitor: %s", exc)

    loop = asyncio.get_running_loop()
    watcher = WorkspaceWatcher(
        workspaces=workspaces,
        assets=assets,
        observations=observations,
        jobs=jobs,
        pipelines=pipelines,
        publisher=publisher,
        loop=loop,
        event_sink=event_sink,
    )

    # Initial sync
    await watcher.sync()

    # Scan-command consumer registers its on_message callback and returns —
    # same non-blocking connect()/start_consuming() shape as ImageProcessorConsumer,
    # so no extra task is needed to pump it; the refresh loop below keeps the
    # event loop alive for both.
    scan_consumer = ScanCommandConsumer(watcher)
    await scan_consumer.connect()
    await scan_consumer.start_consuming()

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
        await scan_consumer.close()
        watcher.stop_all()
        await publisher.close()
        if bus:
            event_sink.set(None)
            await bus.close()
