"""Generic file I/O helpers: hashing and stability polling.

Moved out of ``services/reconciliation_service.py`` — neither function has any
ingestion-specific knowledge, they just happen to have been written there first.
"""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

from src.errors.files import FileNotStableError


async def wait_for_stable_file(
    path: Path,
    *,
    checks_required: int = 2,
    interval_seconds: float = 2.0,
    timeout_seconds: float = 60.0,
) -> None:
    """Block until ``path``'s size/mtime stop changing, or raise after a timeout.

    A file mid-copy/mid-write looks the same as a finished one at any single
    instant, so this waits for ``checks_required`` consecutive stat reads to
    agree before treating the file as done.
    """
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
