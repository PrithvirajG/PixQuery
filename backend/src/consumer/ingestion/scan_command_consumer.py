"""RabbitMQ consumer for manual workspace re-scans.

Published only by the workspace's manual "Scan" API call (never by the monitor
process itself), so a redispatch of previously-failed jobs is exactly what a
user asking to re-check the workspace wants — see
``WorkspaceWatcher.reconcile_workspace``'s ``redispatch_failed`` flag.
"""

from __future__ import annotations

from src.config import RABBITMQ_URL, SCAN_COMMAND_QUEUE
from src.consumer.ingestion.filesystem_watcher import WorkspaceWatcher
from src.infrastructure.messaging import RabbitConsumer
from src.logging_config import get_logger, request_scope


class ScanCommandConsumer(RabbitConsumer):
    """Listens on the scan_commands queue; each message is a workspace_id."""

    def __init__(
        self,
        watcher: WorkspaceWatcher,
        *,
        queue_name: str = SCAN_COMMAND_QUEUE,
        rabbitmq_url: str = RABBITMQ_URL,
    ):
        super().__init__(queue_name=queue_name, rabbitmq_url=rabbitmq_url)
        self.logger = get_logger(__name__)
        self.watcher = watcher

    async def on_message(self, message):
        async with message.process():
            workspace_id = message.body.decode().strip()
            with request_scope(message.correlation_id):
                self.logger.info("Received scan command for workspace %s", workspace_id)
                await self.watcher.reconcile_workspace(workspace_id, redispatch_failed=True)
