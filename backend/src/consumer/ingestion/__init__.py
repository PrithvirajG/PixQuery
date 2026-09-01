"""Filesystem ingestion entry point."""

from typing import TYPE_CHECKING

from src.errors.files import FileNotStableError
from src.services.pipeline_versioning import pipeline_version_hash
from src.services.reconciliation_service import Publisher, ReconciliationService
from src.utils.files import sha256_file, wait_for_stable_file

if TYPE_CHECKING:
    from src.consumer.ingestion.filesystem_watcher import ImageEventHandler, WorkspaceWatcher
    from src.consumer.ingestion.scan_command_consumer import ScanCommandConsumer
    from src.consumer.ingestion.worker import start_monitoring

__all__ = [
    "FileNotStableError",
    "ImageEventHandler",
    "Publisher",
    "ReconciliationService",
    "ScanCommandConsumer",
    "WorkspaceWatcher",
    "pipeline_version_hash",
    "sha256_file",
    "start_monitoring",
    "wait_for_stable_file",
]


def __getattr__(name):
    if name == "ImageEventHandler":
        from src.consumer.ingestion.filesystem_watcher import ImageEventHandler

        return ImageEventHandler
    if name == "WorkspaceWatcher":
        from src.consumer.ingestion.filesystem_watcher import WorkspaceWatcher

        return WorkspaceWatcher
    if name == "ScanCommandConsumer":
        from src.consumer.ingestion.scan_command_consumer import ScanCommandConsumer

        return ScanCommandConsumer
    if name == "start_monitoring":
        from src.consumer.ingestion.worker import start_monitoring

        return start_monitoring
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
