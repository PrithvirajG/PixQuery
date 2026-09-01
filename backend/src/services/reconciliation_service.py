"""Filesystem ingestion: turning files on disk into assets, observations, and jobs.

Renamed from ``FilesystemReconciler`` — the class was already shaped like a
service (injected repository + publisher, no transport knowledge of its own),
so this is a rename in place, not a restructuring. File-stability polling and
the redispatch-on-manual-scan policy move with it as ingestion policy, the same
way retry policy moved into ``PipelineExecutionService``.
"""

from __future__ import annotations

import mimetypes
import os
from pathlib import Path
from typing import Protocol

from src.config import (
    DEFAULT_IMAGE_EXTENSIONS,
    DEFAULT_PIPELINE_ID,
    DEFAULT_PIPELINE_VERSION,
    PIPELINE_OUTPUT_DIRNAME,
)
from src.domain_events import pipeline_state_event
from src.infrastructure.messaging import EventSink
from src.repositories.image_assets_repository import ImageAssetsRepository
from src.repositories.file_observations_repository import FileObservationsRepository
from src.repositories.pipeline_definitions_repository import PipelineDefinitionsRepository
from src.repositories.processing_jobs_repository import ProcessingJobsRepository
from src.services.pipeline_versioning import pipeline_version_hash
from src.utils.files import sha256_file, wait_for_stable_file


class Publisher(Protocol):
    async def publish(self, message: str) -> None:
        ...


# A failed job in one of these terminal states may be redispatched — but only
# when the caller opts in via ``redispatch_failed`` (see ``observe_file``).
# Jobs that are ``completed`` (already done) or in-flight
# (``queued``/``processing``) are never touched either way, so a scan never
# duplicates active work.
_REDISPATCH_STATUSES = {"failed"}


class ReconciliationService:
    def __init__(
        self,
        *,
        assets: ImageAssetsRepository,
        observations: FileObservationsRepository,
        jobs: ProcessingJobsRepository,
        pipelines: PipelineDefinitionsRepository,
        publisher: Publisher | None,
        workspace_path: str,
        workspace_id: str,
        pipeline_id: str | None = None,
        pipeline_version: str | None = None,
        pipeline_ids: list[str] | None = None,
        extensions: set[str] | None = None,
        stable_interval_seconds: float = 2.0,
        stable_timeout_seconds: float = 60.0,
        event_sink: EventSink | None = None,
    ):
        self.assets = assets
        self.observations = observations
        self.jobs = jobs
        self.pipelines = pipelines
        self.publisher = publisher
        self.event_sink = event_sink
        self.workspace_path = Path(workspace_path).expanduser().resolve()
        self.workspace_id = workspace_id
        # Each entry is (pipeline_id, pipeline_version|None). A None version is
        # resolved from the stored pipeline definition at job-creation time, so
        # editing a pipeline produces a new version and triggers reprocessing.
        # No pipelines assigned means files are still ingested (assets +
        # observations recorded) but no processing jobs are created — there is
        # deliberately no fallback to a built-in default pipeline.
        if pipeline_ids:
            self.pipelines_to_run: list[tuple[str, str | None]] = [(pid, None) for pid in pipeline_ids]
        elif pipeline_id:
            self.pipelines_to_run = [(pipeline_id, pipeline_version or DEFAULT_PIPELINE_VERSION)]
        else:
            self.pipelines_to_run = []
        self.extensions = extensions or DEFAULT_IMAGE_EXTENSIONS
        self.stable_interval_seconds = stable_interval_seconds
        self.stable_timeout_seconds = stable_timeout_seconds

    async def reconcile(self, *, redispatch_failed: bool = False) -> list[str]:
        active_paths: set[str] = set()
        queued_job_ids: list[str] = []
        for path in self.iter_image_files():
            relative_path = self.relative_path(path)
            active_paths.add(relative_path)
            queued_job_ids.extend(await self.observe_file(path, redispatch_failed=redispatch_failed))
        self.observations.mark_missing(self.workspace_id, active_paths)
        self._refresh_asset_activity()
        return queued_job_ids

    def _refresh_asset_activity(self) -> None:
        """Recompute every asset's ``active`` flag from current observations.

        Global, not scoped to this workspace — an asset shared across
        workspaces (legacy data) only goes inactive once its last observation
        anywhere is gone, so this has to look at every asset, matching the old
        god-repository's own ``refresh_asset_activity``.
        """
        active_asset_ids = self.observations.distinct_active_asset_ids()
        for asset_id in self.assets.list_all_ids():
            self.assets.set_active(asset_id, asset_id in active_asset_ids)

    def iter_image_files(self):
        if not self.workspace_path.exists():
            return
        for path in self.workspace_path.rglob("*"):
            # Skip the pipeline's own output folder so images written by an
            # ``image_write`` node are never re-ingested as new source files
            # (which would loop: process → write → ingest → process → …).
            if PIPELINE_OUTPUT_DIRNAME in path.relative_to(self.workspace_path).parts:
                continue
            if path.is_file() and path.suffix.lower() in self.extensions:
                yield path

    async def observe_file(self, path: str | Path, *, redispatch_failed: bool = False) -> list[str]:
        path = Path(path).expanduser().resolve()
        if path.suffix.lower() not in self.extensions or not path.exists():
            return []
        await wait_for_stable_file(
            path,
            interval_seconds=self.stable_interval_seconds,
            timeout_seconds=self.stable_timeout_seconds,
        )
        content_sha256 = sha256_file(path)
        mime_type = mimetypes.guess_type(path.name)[0]
        stat = path.stat()
        asset = self.assets.upsert(
            content_sha256=content_sha256,
            mime_type=mime_type,
            size_bytes=stat.st_size,
            current_path=str(path),
            workspace_id=self.workspace_id,
        )
        self.observations.upsert(
            asset_id=asset["_id"],
            workspace_id=self.workspace_id,
            relative_path=self.relative_path(path),
            absolute_path=str(path),
            content_sha256=content_sha256,
        )
        # One job per assigned pipeline so each runs against the asset. A brand-new
        # job is always dispatched. An existing job that previously FAILED is only
        # requeued when `redispatch_failed` is set — automatic entry points
        # (the live filesystem watcher, the periodic full-workspace reconcile)
        # leave a failed job alone so a deterministic failure doesn't retry
        # forever unattended; a manual rescan (the workspace's own "Scan" button)
        # opts in, since a human explicitly asking to re-check the workspace is
        # exactly when retrying something that failed makes sense. Completed /
        # in-flight jobs are never touched either way.
        queued_job_ids: list[str] = []
        for pipeline_id, pipeline_version in self.pipelines_to_run:
            version = pipeline_version or self._resolve_pipeline_version(pipeline_id)
            job, created = self.jobs.get_or_create(
                asset_id=asset["_id"],
                pipeline_id=pipeline_id,
                pipeline_version=version,
                workspace_id=self.workspace_id,
            )
            # A brand-new job is already "queued" — tell the UI now so an image
            # picked up by the monitor lights up without waiting for a poll.
            if created:
                self._emit_state(job, "queued")
            dispatch = created
            if not created and redispatch_failed and job.get("status") in _REDISPATCH_STATUSES:
                job = self.jobs.requeue(job["_id"])
                self._emit_state(job, "queued")
                dispatch = True
            if dispatch and self.publisher:
                await self.publisher.publish(job["_id"])
                queued_job_ids.append(job["_id"])
        return queued_job_ids

    def _emit_state(self, job: dict, state: str) -> None:
        if self.event_sink is None:
            return
        self.event_sink.emit(
            pipeline_state_event(
                workspace_id=job.get("workspace_id"),
                asset_id=job.get("asset_id"),
                pipeline_id=job.get("pipeline_id"),
                state=state,
                job_id=job.get("_id"),
                error=job.get("last_error"),
            )
        )

    def _resolve_pipeline_version(self, pipeline_id: str) -> str:
        """Derive a job's pipeline_version from the stored definition.

        Hashing the node list + per-node config means any pipeline edit yields a
        new version, so ``ensure_processing_job`` (unique on
        asset+pipeline+version) creates a fresh job and the asset is reprocessed.
        """
        if pipeline_id == DEFAULT_PIPELINE_ID:
            return DEFAULT_PIPELINE_VERSION
        definition = self.pipelines.get(pipeline_id)
        if not definition or not definition.get("nodes"):
            return DEFAULT_PIPELINE_VERSION
        return pipeline_version_hash(definition["nodes"], definition.get("edges", []))

    def relative_path(self, path: str | Path) -> str:
        return os.path.relpath(Path(path).resolve(), self.workspace_path).replace(os.sep, "/")
