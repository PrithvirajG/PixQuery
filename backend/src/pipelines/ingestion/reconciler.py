from __future__ import annotations

import asyncio
import hashlib
import json
import mimetypes
import os
from pathlib import Path
from typing import Any, Protocol

from src.config import (
    DEFAULT_IMAGE_EXTENSIONS,
    DEFAULT_PIPELINE_ID,
    DEFAULT_PIPELINE_VERSION,
    PIPELINE_OUTPUT_DIRNAME,
)


class Publisher(Protocol):
    async def publish(self, message: str) -> None:
        ...


class FileNotStableError(RuntimeError):
    pass


# On a re-scan, an existing job in one of these terminal states is requeued and
# re-dispatched (a failed job should retry when you scan again). Jobs that are
# ``completed`` (already done) or in-flight (``queued``/``processing``) are left
# alone so a scan never duplicates active work.
_REDISPATCH_STATUSES = {"failed"}


class FilesystemReconciler:
    def __init__(
        self,
        *,
        repository,
        publisher: Publisher | None,
        workspace_path: str,
        workspace_id: str,
        pipeline_id: str | None = None,
        pipeline_version: str | None = None,
        pipeline_ids: list[str] | None = None,
        extensions: set[str] | None = None,
        stable_interval_seconds: float = 2.0,
        stable_timeout_seconds: float = 60.0,
    ):
        self.repository = repository
        self.publisher = publisher
        self.workspace_path = Path(workspace_path).expanduser().resolve()
        self.workspace_id = workspace_id
        # Each entry is (pipeline_id, pipeline_version|None). A None version is
        # resolved from the stored pipeline definition at job-creation time, so
        # editing a pipeline produces a new version and triggers reprocessing.
        # No pipelines assigned means files are still ingested (assets +
        # observations recorded) but no processing jobs are created — there is
        # deliberately no fallback to a built-in default pipeline.
        if pipeline_ids:
            self.pipelines: list[tuple[str, str | None]] = [(pid, None) for pid in pipeline_ids]
        elif pipeline_id:
            self.pipelines = [(pipeline_id, pipeline_version or DEFAULT_PIPELINE_VERSION)]
        else:
            self.pipelines = []
        self.extensions = extensions or DEFAULT_IMAGE_EXTENSIONS
        self.stable_interval_seconds = stable_interval_seconds
        self.stable_timeout_seconds = stable_timeout_seconds

    async def reconcile(self) -> list[str]:
        active_paths: set[str] = set()
        queued_job_ids: list[str] = []
        for path in self.iter_image_files():
            relative_path = self.relative_path(path)
            active_paths.add(relative_path)
            queued_job_ids.extend(await self.observe_file(path))
        self.repository.mark_missing_observations(self.workspace_id, active_paths)
        return queued_job_ids

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

    async def observe_file(self, path: str | Path) -> list[str]:
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
        asset = self.repository.upsert_asset(
            content_sha256=content_sha256,
            mime_type=mime_type,
            size_bytes=stat.st_size,
            current_path=str(path),
            workspace_id=self.workspace_id,
        )
        self.repository.upsert_file_observation(
            asset_id=asset["_id"],
            workspace_id=self.workspace_id,
            relative_path=self.relative_path(path),
            absolute_path=str(path),
            content_sha256=content_sha256,
        )
        # One job per assigned pipeline so each runs against the asset. A brand-new
        # job is dispatched; an existing job that previously FAILED is requeued and
        # re-dispatched so a re-scan retries it. Completed / in-flight jobs are left
        # untouched.
        queued_job_ids: list[str] = []
        for pipeline_id, pipeline_version in self.pipelines:
            version = pipeline_version or self._resolve_pipeline_version(pipeline_id)
            job, created = self.repository.ensure_processing_job(
                asset_id=asset["_id"],
                pipeline_id=pipeline_id,
                pipeline_version=version,
                workspace_id=self.workspace_id,
            )
            dispatch = created
            if not created and job.get("status") in _REDISPATCH_STATUSES:
                self.repository.requeue_job(job["_id"])
                dispatch = True
            if dispatch and self.publisher:
                await self.publisher.publish(job["_id"])
                queued_job_ids.append(job["_id"])
        return queued_job_ids

    def _resolve_pipeline_version(self, pipeline_id: str) -> str:
        """Derive a job's pipeline_version from the stored definition.

        Hashing the node list + per-node config means any pipeline edit yields a
        new version, so ``ensure_processing_job`` (unique on
        asset+pipeline+version) creates a fresh job and the asset is reprocessed.
        """
        if pipeline_id == DEFAULT_PIPELINE_ID:
            return DEFAULT_PIPELINE_VERSION
        definition = self.repository.get_pipeline(pipeline_id)
        if not definition or not definition.get("nodes"):
            return DEFAULT_PIPELINE_VERSION
        return pipeline_version_hash(definition["nodes"], definition.get("edges", []))

    def relative_path(self, path: str | Path) -> str:
        return os.path.relpath(Path(path).resolve(), self.workspace_path).replace(os.sep, "/")


async def wait_for_stable_file(
    path: Path,
    *,
    checks_required: int = 2,
    interval_seconds: float = 2.0,
    timeout_seconds: float = 60.0,
) -> None:
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    stable_checks = 0
    previous: tuple[int, int] | None = None
    while asyncio.get_running_loop().time() <= deadline:
        stat = path.stat()
        current = (stat.st_size, stat.st_mtime_ns)
        if current == previous:
            stable_checks += 1
            if stable_checks >= checks_required:
                return
        else:
            stable_checks = 0
            previous = current
        await asyncio.sleep(interval_seconds)
    raise FileNotStableError(f"File is still changing after {timeout_seconds} seconds: {path}")


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_obj:
        for chunk in iter(lambda: file_obj.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pipeline_version_hash(
    nodes: list[dict[str, Any]], edges: list[dict[str, Any]] | None = None
) -> str:
    """Stable short version string derived from a pipeline's nodes, wiring + config.

    Includes ``edges`` so re-wiring the graph (not just editing a node) yields a new
    version and reprocesses affected assets.
    """
    node_payload = sorted(
        (
            {
                "node_id": node.get("node_id"),
                "pipeline_node_id": node.get("pipeline_node_id"),
                "config_overrides": node.get("config_overrides", {}),
            }
            for node in nodes
        ),
        key=lambda n: (n["node_id"] or "", n["pipeline_node_id"] or ""),
    )
    edge_payload = sorted(
        (
            {
                "from_node_id": edge.get("from_node_id"),
                "to_node_id": edge.get("to_node_id"),
                "from_output": edge.get("from_output"),
                "to_input": edge.get("to_input"),
            }
            for edge in (edges or [])
        ),
        key=lambda e: (e["from_node_id"] or "", e["to_node_id"] or ""),
    )
    digest = hashlib.sha256(
        json.dumps(
            {"nodes": node_payload, "edges": edge_payload}, sort_keys=True, default=str
        ).encode("utf-8")
    ).hexdigest()
    return f"p-{digest[:12]}"
