import asyncio
import logging
from datetime import datetime, timezone

from src.config import EVENTS_ENABLED, MONGO_DB_NAME, MONGO_URI
from src.infrastructure.messaging import EventSink, RabbitConsumer
from src.publisher.events import EventPublisher
from src.infrastructure.vector_store import WeaviateEmbeddingStore
from src.repositories.bootstrap import ensure_schema
from src.repositories.image_assets_repository import ImageAssetsRepository
from src.repositories.model_outputs_repository import ModelOutputsRepository
from src.repositories.pipeline_definitions_repository import PipelineDefinitionsRepository
from src.repositories.pipeline_nodes_repository import PipelineNodesRepository
from src.repositories.pipeline_runs_repository import PipelineRunsRepository
from src.repositories.processing_jobs_repository import ProcessingJobsRepository
from src.services.pipeline_execution_service import PipelineExecutionService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


class ImageProcessorConsumer(RabbitConsumer):
    def __init__(self):
        super().__init__()

        self.logger = logging.getLogger("ImageProcessorConsumer")
        # One live connection, shared by every repository below — bootstrapped
        # once here (index creation, system-node seeding), same as api/dependencies.py.
        from pymongo import MongoClient

        database = MongoClient(MONGO_URI)[MONGO_DB_NAME]
        ensure_schema(database)
        self.jobs = ProcessingJobsRepository(database)
        self.embedding_store = WeaviateEmbeddingStore()
        self.event_sink = EventSink()
        self.pipeline = PipelineExecutionService(
            jobs=self.jobs,
            runs=PipelineRunsRepository(database),
            outputs=ModelOutputsRepository(database),
            assets=ImageAssetsRepository(database),
            pipelines=PipelineDefinitionsRepository(database),
            nodes=PipelineNodesRepository(database),
            embedding_store=self.embedding_store,
            event_sink=self.event_sink,
        )
        self.event_bus: EventPublisher | None = None

    async def connect(self):
        await super().connect()
        if not EVENTS_ENABLED:
            return
        # Runs pipelines in a worker thread, so the event sink is called
        # off-loop — EventPublisher.emit is thread-safe precisely for this.
        try:
            bus = EventPublisher()
            await bus.connect()
            self.event_bus = bus
            self.event_sink.set(self.event_bus.emit)
        except Exception as exc:
            self.logger.warning("Live events disabled in worker: %s", exc)

    async def on_message(self, message):
        async with message.process(requeue=False):
            job_id = message.body.decode().strip()
            self.logger.info("Processing job_id=%s", job_id)
            try:
                await asyncio.to_thread(self.pipeline.run_job, job_id)
            except Exception:
                self.logger.exception("Failed job_id=%s", job_id)
                job = self.jobs.get(job_id)
                if job and job.get("status") == "queued":
                    asyncio.create_task(self._republish_after_backoff(job_id, job.get("next_attempt_at")))
                return
            self.logger.info("Finished job_id=%s", job_id)

    async def _republish_after_backoff(self, job_id: str, next_attempt_at):
        delay = 0
        if isinstance(next_attempt_at, datetime):
            if next_attempt_at.tzinfo is None:
                now = datetime.utcnow()
            else:
                now = datetime.now(timezone.utc)
            delay = max(0, (next_attempt_at - now).total_seconds())
        if delay:
            await asyncio.sleep(delay)
        import aio_pika

        await self.channel.default_exchange.publish(
            aio_pika.Message(
                body=job_id.encode(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            ),
            routing_key=self.queue_name,
        )
        self.logger.info("Requeued job_id=%s after retry backoff", job_id)

    async def close(self):
        await super().close()
        if self.event_bus:
            self.event_sink.set(None)
            await self.event_bus.close()
        self.embedding_store.close()
