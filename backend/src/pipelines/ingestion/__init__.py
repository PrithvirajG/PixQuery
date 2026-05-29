"""Filesystem ingestion pipeline."""

from typing import TYPE_CHECKING

from src.pipelines.ingestion.reconciler import (
    FileNotStableError,
    FilesystemReconciler,
    Publisher,
    sha256_file,
    wait_for_stable_file,
)

if TYPE_CHECKING:
    from src.pipelines.ingestion.watcher import ImageEventHandler, start_monitoring

__all__ = [
    "FileNotStableError",
    "FilesystemReconciler",
    "ImageEventHandler",
    "Publisher",
    "sha256_file",
    "start_monitoring",
    "wait_for_stable_file",
]


def __getattr__(name):
    if name == "ImageEventHandler":
        from src.pipelines.ingestion.watcher import ImageEventHandler

        return ImageEventHandler
    if name == "start_monitoring":
        from src.pipelines.ingestion.watcher import start_monitoring

        return start_monitoring
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
