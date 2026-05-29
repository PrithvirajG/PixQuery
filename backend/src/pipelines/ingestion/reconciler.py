from __future__ import annotations

import asyncio
import hashlib
import mimetypes
import os
from pathlib import Path
from typing import Protocol

from src.config import (
    DEFAULT_IMAGE_EXTENSIONS,
    DEFAULT_PIPELINE_ID,
    DEFAULT_PIPELINE_VERSION,
)


class Publisher(Protocol):
    async def publish(self, message: str) -> None:
        ...


class FileNotStableError(RuntimeError):
    pass


class FilesystemReconciler:
    def __init__(
        self,
        *,
        repository,
        publisher: Publisher | None,
        workspace_path: str,
        workspace_id: str,
        pipeline_id: str = DEFAULT_PIPELINE_ID,
        pipeline_version: str = DEFAULT_PIPELINE_VERSION,
        extensions: set[str] | None = None,
        stable_interval_seconds: float = 2.0,
        stable_timeout_seconds: float = 60.0,
    ):
        self.repository = repository
        self.publisher = publisher
        self.workspace_path = Path(workspace_path).expanduser().resolve()
        self.workspace_id = workspace_id
        self.pipeline_id = pipeline_id
        self.pipeline_version = pipeline_version
        self.extensions = extensions or DEFAULT_IMAGE_EXTENSIONS
        self.stable_interval_seconds = stable_interval_seconds
        self.stable_timeout_seconds = stable_timeout_seconds

    async def reconcile(self) -> list[str]:
        active_paths: set[str] = set()
        queued_job_ids: list[str] = []
        for path in self.iter_image_files():
            relative_path = self.relative_path(path)
            active_paths.add(relative_path)
            job_id = await self.observe_file(path)
            if job_id:
                queued_job_ids.append(job_id)
        self.repository.mark_missing_observations(self.workspace_id, active_paths)
        return queued_job_ids

    def iter_image_files(self):
        if not self.workspace_path.exists():
            return
        for path in self.workspace_path.rglob("*"):
            if path.is_file() and path.suffix.lower() in self.extensions:
                yield path

    async def observe_file(self, path: str | Path) -> str | None:
        path = Path(path).expanduser().resolve()
        if path.suffix.lower() not in self.extensions or not path.exists():
            return None
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
        )
        self.repository.upsert_file_observation(
            asset_id=asset["_id"],
            workspace_id=self.workspace_id,
            relative_path=self.relative_path(path),
            absolute_path=str(path),
            content_sha256=content_sha256,
        )
        job, created = self.repository.ensure_processing_job(
            asset_id=asset["_id"],
            pipeline_id=self.pipeline_id,
            pipeline_version=self.pipeline_version,
        )
        if created and self.publisher:
            await self.publisher.publish(job["_id"])
            return job["_id"]
        return None

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
