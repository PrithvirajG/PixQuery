"""
Multi-workspace filesystem monitor.

At startup and every WORKSPACE_REFRESH_INTERVAL seconds the monitor:
  1. Reads all active workspace_definitions from MongoDB.
  2. Starts a watchdog Observer for each newly seen workspace.
  3. Stops observers for workspaces that have been deleted or deactivated.

The scan_commands RabbitMQ queue accepts messages of the form:
    <workspace_id>
When received, an immediate reconcile is triggered for that workspace.
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from src.config import (
    EVENTS_ENABLED,
    MONGO_DB_NAME,
    MONGO_URI,
    RABBITMQ_URL,
    SCAN_COMMAND_QUEUE,
    WORKSPACE_REFRESH_INTERVAL,
)
from src.infrastructure.messaging import EventBus, RabbitPublisher
from src.pipelines.ingestion.reconciler import FileNotStableError, FilesystemReconciler
from src.repositories import MongoPipelineRepository

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("FilesystemMonitor")


# ---------------------------------------------------------------------------
# Per-workspace event handler
# ---------------------------------------------------------------------------

class ImageEventHandler(FileSystemEventHandler):
    def __init__(self, reconciler: FilesystemReconciler, loop: asyncio.AbstractEventLoop):
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
        repository: MongoPipelineRepository,
        publisher: RabbitPublisher,
        loop: asyncio.AbstractEventLoop,
    ):
        self.repository = repository
        self.publisher = publisher
        self.loop = loop
        # workspace_id → (Observer, FilesystemReconciler)
        self._watchers: dict[str, tuple[Observer, FilesystemReconciler]] = {}
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

    def _make_reconciler(self, ws: dict) -> FilesystemReconciler:
        extensions = set(ws.get("extensions") or [".jpg", ".jpeg", ".png", ".webp"])
        # Run each pipeline the workspace assigns. When none are attached the
        # reconciler still ingests files (assets + observations) but creates no
        # processing jobs — there is no implicit default pipeline.
        pipeline_ids = ws.get("pipeline_ids") or []
        return FilesystemReconciler(
            repository=self.repository,
            publisher=self.publisher,
            workspace_path=self._get_path(ws),
            workspace_id=ws["_id"],
            pipeline_ids=pipeline_ids,
            extensions=extensions,
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
        if not reconciler.pipelines:
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
        active_workspaces = self.repository.list_workspaces_all_active()
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

    async def reconcile_workspace(self, workspace_id: str) -> int:
        """Run an immediate full reconcile for one workspace."""
        # Re-read the definition so a scan issued right after an edit (e.g.
        # attaching a pipeline) uses the current pipeline list, not a cached one.
        ws = self.repository.get_workspace(workspace_id)
        if ws and workspace_id in self._watchers and self._signatures.get(workspace_id) != self._signature(ws):
            logger.info("Workspace '%s' definition changed — rebuilding watcher", ws.get("name"))
            self._stop_one(workspace_id)
            self._start_one(ws)
        if workspace_id not in self._watchers:
            logger.warning("reconcile requested for unknown workspace %s", workspace_id)
            return 0
        _, reconciler = self._watchers[workspace_id]
        try:
            queued = await reconciler.reconcile()
            logger.info("Reconcile workspace %s → queued %d jobs", workspace_id, len(queued))
            return len(queued)
        except Exception:
            logger.exception("Reconcile failed for workspace %s", workspace_id)
            return 0

    async def reconcile_all(self) -> None:
        for ws_id in list(self._watchers):
            await self.reconcile_workspace(ws_id)

    def stop_all(self) -> None:
        for ws_id in list(self._watchers):
            self._stop_one(ws_id)


# ---------------------------------------------------------------------------
# Scan-command consumer
# ---------------------------------------------------------------------------

async def consume_scan_commands(
    watcher: WorkspaceWatcher,
    rabbitmq_url: str,
    queue_name: str,
) -> None:
    """Listen on the scan_commands queue; each message is a workspace_id."""
    import aio_pika

    connection = await aio_pika.connect_robust(rabbitmq_url)
    channel = await connection.channel()
    queue = await channel.declare_queue(queue_name, durable=True)
    logger.info("Listening for scan commands on '%s'", queue_name)

    async with queue.iterator() as q:
        async for message in q:
            async with message.process():
                workspace_id = message.body.decode().strip()
                logger.info("Received scan command for workspace %s", workspace_id)
                await watcher.reconcile_workspace(workspace_id)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def start_monitoring() -> None:
    """Start the multi-workspace monitor driven entirely by workspace_definitions in MongoDB."""
    repository = MongoPipelineRepository.from_uri(MONGO_URI, MONGO_DB_NAME)
    publisher = RabbitPublisher()
    await publisher.connect()

    # The monitor is where a newly-discovered image first becomes a queued job, so
    # it emits the transition that makes an image appear as "Queued" in an open UI.
    bus = None
    if EVENTS_ENABLED:
        try:
            bus = await EventBus().start()
            repository.set_event_sink(bus.emit)
        except Exception as exc:
            logger.warning("Live events disabled in monitor: %s", exc)

    loop = asyncio.get_running_loop()
    watcher = WorkspaceWatcher(repository, publisher, loop)

    # Initial sync
    await watcher.sync()

    # Start scan-command listener as a background task
    scan_task = asyncio.create_task(
        consume_scan_commands(watcher, RABBITMQ_URL, SCAN_COMMAND_QUEUE)
    )

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
        scan_task.cancel()
        watcher.stop_all()
        await publisher.close()
        if bus:
            repository.set_event_sink(None)
            await bus.close()


