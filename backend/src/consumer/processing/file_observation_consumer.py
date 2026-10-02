"""Consumes file_observations — turns one raw {workspace_id, path} into reality.

Published by two independent, deliberately lightweight sources — the API's
manual "Scan" route and the live filesystem watcher's per-event handler (see
``consumer/ingestion/filesystem_watcher.py``) — neither of which hashes files
or touches ``image_assets``/``file_observations``/``processing_jobs``; they
only list/detect and publish. This consumer is the one place that does the
real ingestion work for a single file: wait-for-stable, SHA-256, upsert the
asset/observation, create/dispatch its job — via
``ReconciliationService.observe_file``, the exact same logic the file-watcher
process used to run in-process before this split.

Deletion detection (``mark_missing``) is NOT this consumer's job — it needs the
complete current file listing in one pass, which only the lister (API/watcher)
has; see ``ReconciliationService.scan()``.
"""

from __future__ import annotations

import json

from src.config import EVENTS_ENABLED, FILE_OBSERVATION_QUEUE, MONGO_DB_NAME, MONGO_URI
from src.errors.files import FileNotStableError
from src.infrastructure.messaging import EventSink, RabbitConsumer, RabbitPublisher
from src.logging_config import get_logger, request_scope
from src.publisher.events import EventPublisher
from src.repositories.bootstrap import ensure_schema
from src.repositories.file_observations_repository import FileObservationsRepository
from src.repositories.image_assets_repository import ImageAssetsRepository
from src.repositories.pipeline_definitions_repository import PipelineDefinitionsRepository
from src.repositories.processing_jobs_repository import ProcessingJobsRepository
from src.repositories.workspace_definitions_repository import WorkspaceDefinitionsRepository
from src.services.reconciliation_service import ReconciliationService

_DEFAULT_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


class FileObservationConsumer(RabbitConsumer):
    def __init__(self):
        super().__init__(queue_name=FILE_OBSERVATION_QUEUE)
        self.logger = get_logger(__name__)
        # One live connection, shared by every repository below — bootstrapped
        # once here, same as ImageProcessorConsumer / api/dependencies.py.
        from pymongo import MongoClient

        database = MongoClient(MONGO_URI)[MONGO_DB_NAME]
        ensure_schema(database)
        self.workspaces = WorkspaceDefinitionsRepository(database)
        self.assets = ImageAssetsRepository(database)
        self.observations = FileObservationsRepository(database)
        self.jobs = ProcessingJobsRepository(database)
        self.pipelines = PipelineDefinitionsRepository(database)
        # A dispatched job's id is published here — the SAME image_task queue
        # ImageProcessorConsumer already consumes, so job execution is
        # unaffected by this split; only how a job gets *created* changed.
        self.image_task_publisher = RabbitPublisher()
        self.event_sink = EventSink()
        self.event_bus: EventPublisher | None = None

    async def connect(self):
        await super().connect()
        await self.image_task_publisher.connect()
        if not EVENTS_ENABLED:
            return
        try:
            bus = EventPublisher()
            await bus.connect()
            self.event_bus = bus
            self.event_sink.set(bus.emit)
        except Exception as exc:
            self.logger.warning("Live events disabled in file-observation consumer: %s", exc)

    async def on_message(self, message):
        async with message.process():
            payload = json.loads(message.body)
            workspace_id = payload["workspace_id"]
            path = payload["path"]
            redispatch_failed = bool(payload.get("redispatch_failed", False))
            with request_scope(message.correlation_id):
                workspace = self.workspaces.get(workspace_id)
                if not workspace:
                    self.logger.warning(
                        "Observation for unknown workspace_id=%s, dropping path=%s",
                        workspace_id, path,
                    )
                    return
                reconciler = ReconciliationService(
                    assets=self.assets,
                    observations=self.observations,
                    jobs=self.jobs,
                    pipelines=self.pipelines,
                    publisher=self.image_task_publisher,
                    workspace_path=workspace.get("workspace_path") or workspace.get("watch_root"),
                    workspace_id=workspace_id,
                    pipeline_ids=workspace.get("pipeline_ids") or [],
                    extensions=set(workspace.get("extensions") or _DEFAULT_EXTENSIONS),
                    event_sink=self.event_sink,
                )
                try:
                    queued = await reconciler.observe_file(path, redispatch_failed=redispatch_failed)
                    if queued:
                        self.logger.info("Observed %s -> queued job(s) %s", path, queued)
                except FileNotStableError:
                    self.logger.info("Postponing unstable file: %s", path)
                except Exception:
                    self.logger.exception("Failed to observe %s", path)

    async def close(self):
        await super().close()
        await self.image_task_publisher.close()
        if self.event_bus:
            self.event_sink.set(None)
            await self.event_bus.close()
