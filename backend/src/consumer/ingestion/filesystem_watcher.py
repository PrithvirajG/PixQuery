"""
Multi-workspace filesystem monitor.

At startup and every WORKSPACE_REFRESH_INTERVAL seconds the monitor:
  1. Reads all active workspace_definitions from MongoDB.
  2. Starts a watchdog Observer for each newly seen workspace.
  3. Stops observers for workspaces that have been deleted or deactivated.

This process only *detects* — a live filesystem event or the periodic safety
net both just publish a ``{workspace_id, path, redispatch_failed}`` message to
``FILE_OBSERVATION_QUEUE``. It never hashes a file, never touches
``image_assets``/``file_observations``/``processing_jobs``, and is not where a
job gets created — that's the pipeline-worker's ``FileObservationConsumer``
(see its module docstring). This process only needs ``assets``/``observations``
for ``ReconciliationService.scan()``'s deletion-detection half (listing +
``mark_missing``) — it has no dependency on ``jobs``/``pipelines`` at all.

The manual "Scan" button is a separate, independent trigger now (the API's
``/scan`` route lists the workspace itself and publishes to the same queue) —
it does not depend on this process running.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from src.logging_config import get_logger, request_scope
from src.repositories.file_observations_repository import FileObservationsRepository
from src.repositories.image_assets_repository import ImageAssetsRepository
from src.repositories.workspace_definitions_repository import WorkspaceDefinitionsRepository
from src.services.reconciliation_service import ReconciliationService

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Per-workspace event handler
# ---------------------------------------------------------------------------

class ImageEventHandler(FileSystemEventHandler):
    """Publishes a raw observation for each matching file-system event.

    Deliberately thin: no hashing, no stability-wait, no Mongo access at all —
    those happen downstream in the pipeline-worker, once per observation,
    regardless of whether it came from here or from a manual Scan.
    """

    def __init__(self, workspace_id: str, extensions: set[str], publisher, loop: asyncio.AbstractEventLoop):
        self.workspace_id = workspace_id
        self.extensions = extensions
        self.publisher = publisher
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
        if path.suffix.lower() not in self.extensions:
            return
        asyncio.run_coroutine_threadsafe(self._observe(path), self.loop)

    async def _observe(self, path: Path):
        # Not triggered by any inbound request — bind a fresh id so this
        # observation is still traceable as one unit across the queue hop.
        with request_scope():
            try:
                await self.publisher.publish(json.dumps({
                    "workspace_id": self.workspace_id,
                    "path": str(path),
                    # A live-detected change never redispatches a previously
                    # failed job — see ReconciliationService.observe_file's
                    # docstring on why that's opt-in, manual-scan-only.
                    "redispatch_failed": False,
                }))
            except Exception:
                logger.exception("Failed to publish observation for %s", path)


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
        publisher,
        loop: asyncio.AbstractEventLoop,
    ):
        self.workspaces = workspaces
        self.assets = assets
        self.observations = observations
        self.publisher = publisher
        self.loop = loop
        # workspace_id → (Observer, ReconciliationService) — the service here is
        # used only for its scan() half (listing + mark_missing); it's never
        # constructed with jobs/pipelines, since this process never creates jobs.
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
        return ReconciliationService(
            assets=self.assets,
            observations=self.observations,
            workspace_path=self._get_path(ws),
            workspace_id=ws["_id"],
            extensions=extensions,
        )

    def _start_one(self, ws: dict) -> None:
        ws_id = ws["_id"]
        root = Path(self._get_path(ws)).expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
        reconciler = self._make_reconciler(ws)
        observer = Observer()
        observer.schedule(
            ImageEventHandler(ws_id, reconciler.extensions, self.publisher, self.loop),
            str(root),
            recursive=True,
        )
        observer.start()
        self._watchers[ws_id] = (observer, reconciler)
        self._signatures[ws_id] = self._signature(ws)
        logger.info("Started watching workspace '%s' at %s", ws.get("name"), root)
        if not ws.get("pipeline_ids"):
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
        """List this workspace now and publish an observation for each file found.

        This is the watcher's own periodic safety net (catches files present
        before the watcher started, or a dropped OS event) — NOT the manual
        "Scan" button's path anymore, which lives entirely in the API route and
        doesn't touch this process. ``redispatch_failed`` stays False for every
        caller of this method (the periodic loop); it exists as a parameter
        only so the semantics match ``ReconciliationService.observe_file``'s,
        for anyone reading the two side by side.

        Returns the number of files *observed and published*, not jobs queued —
        job creation happens later, in a different process, so this process
        can no longer know that count.
        """
        # Re-read the definition so this uses the current pipeline list/extensions,
        # not a cached one.
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
            found = reconciler.scan()
            for path in found:
                await self.publisher.publish(json.dumps({
                    "workspace_id": workspace_id,
                    "path": str(path),
                    "redispatch_failed": redispatch_failed,
                }))
            logger.info("Reconcile workspace %s → observed %d file(s)", workspace_id, len(found))
            return len(found)
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
