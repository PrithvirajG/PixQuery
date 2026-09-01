"""
Multi-workspace filesystem monitor.

At startup and every WORKSPACE_REFRESH_INTERVAL seconds the monitor:
  1. Reads all active workspace_definitions from MongoDB.
  2. Starts a watchdog Observer for each newly seen workspace.
  3. Stops observers for workspaces that have been deleted or deactivated.

Manual re-scans (the workspace's "Scan" button) arrive over RabbitMQ instead of
the filesystem — see ``scan_command_consumer.ScanCommandConsumer``, which calls
back into ``WorkspaceWatcher.reconcile_workspace`` below.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from src.errors.files import FileNotStableError
from src.infrastructure.messaging import EventSink, RabbitPublisher
from src.logging_config import get_logger, request_scope
from src.repositories.file_observations_repository import FileObservationsRepository
from src.repositories.image_assets_repository import ImageAssetsRepository
from src.repositories.pipeline_definitions_repository import PipelineDefinitionsRepository
from src.repositories.processing_jobs_repository import ProcessingJobsRepository
from src.repositories.workspace_definitions_repository import WorkspaceDefinitionsRepository
from src.services.reconciliation_service import ReconciliationService

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Per-workspace event handler
# ---------------------------------------------------------------------------

class ImageEventHandler(FileSystemEventHandler):
    def __init__(self, reconciler: ReconciliationService, loop: asyncio.AbstractEventLoop):
        self.reconciler = reconciler
        self.loop = loop

    def on_created(self, event):
        self._schedule(event)

    def on_modified(self, event):
        self._schedule(event)

    def on_moved(self, event):
        if not event.is_directory:
            self._schedule_path(event.dest_path)

    def _schedule(self, event):
        if not event.is_directory:
            self._schedule_path(event.src_path)

    def _schedule_path(self, src_path: str):
        path = Path(src_path)
        if path.suffix.lower() not in self.reconciler.extensions:
            return
        asyncio.run_coroutine_threadsafe(self._observe(path), self.loop)

    async def _observe(self, path: Path):
        # Not triggered by any inbound request — bind a fresh id so this
        # file's ingest-through-processing chain is still traceable as one unit.
        with request_scope():
            try:
                await self.reconciler.observe_file(path)
            except FileNotStableError:
                logger.info("Postponing unstable file: %s", path)
            except Exception:
                logger.exception("Failed to observe %s", path)


# ---------------------------------------------------------------------------
# Active-workspace registry
# ---------------------------------------------------------------------------

class WorkspaceWatcher:
    """Tracks one watchdog Observer per workspace."""

    def __init__(
        self,
        *,
        workspaces: WorkspaceDefinitionsRepository,
        assets: ImageAssetsRepository,
        observations: FileObservationsRepository,
        jobs: ProcessingJobsRepository,
        pipelines: PipelineDefinitionsRepository,
        publisher: RabbitPublisher,
        loop: asyncio.AbstractEventLoop,
        event_sink: EventSink | None = None,
    ):
        self.workspaces = workspaces
        self.assets = assets
        self.observations = observations
        self.jobs = jobs
        self.pipelines = pipelines
        self.publisher = publisher
        self.loop = loop
        self.event_sink = event_sink
        # workspace_id → (Observer, ReconciliationService)
        self._watchers: dict[str, tuple[Observer, ReconciliationService]] = {}
        # workspace_id → definition signature, to detect edits (path/pipelines/
        # extensions) that require rebuilding the reconciler.
        self._signatures: dict[str, tuple] = {}

    # ------------------------------------------------------------------
    @staticmethod
    def _get_path(ws: dict) -> str:
        """Read workspace_path, falling back to the legacy watch_root field."""
        return ws.get("workspace_path") or ws["watch_root"]

    @classmethod
    def _signature(cls, ws: dict) -> tuple:
        return (
            cls._get_path(ws),
            tuple(ws.get("pipeline_ids") or []),
            tuple(sorted(ws.get("extensions") or [])),
        )

    def _make_reconciler(self, ws: dict) -> ReconciliationService:
        extensions = set(ws.get("extensions") or [".jpg", ".jpeg", ".png", ".webp"])
        # Run each pipeline the workspace assigns. When none are attached the
        # reconciler still ingests files (assets + observations) but creates no
        # processing jobs — there is no implicit default pipeline.
        pipeline_ids = ws.get("pipeline_ids") or []
        return ReconciliationService(
            assets=self.assets,
            observations=self.observations,
            jobs=self.jobs,
            pipelines=self.pipelines,
            publisher=self.publisher,
            workspace_path=self._get_path(ws),
            workspace_id=ws["_id"],
            pipeline_ids=pipeline_ids,
            extensions=extensions,
            event_sink=self.event_sink,
        )

    def _start_one(self, ws: dict) -> None:
        ws_id = ws["_id"]
        root = Path(self._get_path(ws)).expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
        reconciler = self._make_reconciler(ws)
        observer = Observer()
        observer.schedule(
            ImageEventHandler(reconciler, self.loop),
            str(root),
            recursive=True,
        )
        observer.start()
        self._watchers[ws_id] = (observer, reconciler)
        self._signatures[ws_id] = self._signature(ws)
        logger.info("Started watching workspace '%s' at %s", ws.get("name"), root)
        if not reconciler.pipelines_to_run:
            logger.info(
                "Workspace '%s' has no pipelines attached — files will be ingested but not processed",
                ws.get("name"),
            )

    def _stop_one(self, ws_id: str) -> None:
        observer, _ = self._watchers.pop(ws_id)
        self._signatures.pop(ws_id, None)
        observer.stop()
        observer.join()
        logger.info("Stopped watching workspace %s", ws_id)

    # ------------------------------------------------------------------
    async def sync(self) -> None:
        """Reconcile running observers with what's in the database."""
        # One id for this whole sync pass — not triggered by any inbound
        # request, so it's the only thing tying its log lines together.
        with request_scope():
            active_workspaces = self.workspaces.list_all_active()
            active_ids = {ws["_id"] for ws in active_workspaces}

            # Stop removed / deactivated workspaces
            for ws_id in list(self._watchers):
                if ws_id not in active_ids:
                    self._stop_one(ws_id)

            # Restart workspaces whose definition changed (path, pipelines, extensions)
            for ws in active_workspaces:
                ws_id = ws["_id"]
                if ws_id in self._watchers and self._signatures.get(ws_id) != self._signature(ws):
                    logger.info("Workspace '%s' definition changed — rebuilding watcher", ws.get("name"))
                    self._stop_one(ws_id)

            # Start newly added workspaces + run initial reconcile
            for ws in active_workspaces:
                if ws["_id"] not in self._watchers:
                    self._start_one(ws)
                    await self.reconcile_workspace(ws["_id"])

    async def reconcile_workspace(self, workspace_id: str, *, redispatch_failed: bool = False) -> int:
        """Run an immediate full reconcile for one workspace.

        ``redispatch_failed`` distinguishes an automatic reconcile (the
        periodic refresh loop, a newly-started watcher) from a manual one (a
        user hitting the workspace's "Scan" button, via `ScanCommandConsumer`)
        — only the latter retries jobs that previously failed.
        """
        # Re-read the definition so a scan issued right after an edit (e.g.
        # attaching a pipeline) uses the current pipeline list, not a cached one.
        ws = self.workspaces.get(workspace_id)
        if ws and workspace_id in self._watchers and self._signatures.get(workspace_id) != self._signature(ws):
            logger.info("Workspace '%s' definition changed — rebuilding watcher", ws.get("name"))
            self._stop_one(workspace_id)
            self._start_one(ws)
        if workspace_id not in self._watchers:
            logger.warning("reconcile requested for unknown workspace %s", workspace_id)
            return 0
        _, reconciler = self._watchers[workspace_id]
        try:
            queued = await reconciler.reconcile(redispatch_failed=redispatch_failed)
            logger.info("Reconcile workspace %s → queued %d jobs", workspace_id, len(queued))
            return len(queued)
        except Exception:
            logger.exception("Reconcile failed for workspace %s", workspace_id)
            return 0

    async def reconcile_all(self) -> None:
        # Periodic, unattended refresh — never retries a failed job on its own.
        # One id for the whole pass, same reasoning as sync().
        with request_scope():
            for ws_id in list(self._watchers):
                await self.reconcile_workspace(ws_id)

    def stop_all(self) -> None:
        for ws_id in list(self._watchers):
            self._stop_one(ws_id)