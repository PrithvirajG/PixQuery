import asyncio
import logging
from datetime import datetime, timezone

from src.config import MONGO_DB_NAME, MONGO_URI
from src.infrastructure.messaging import RabbitConsumer
from src.infrastructure.vector_store import WeaviateEmbeddingStore
from src.repositories import MongoPipelineRepository

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


class ImageProcessorConsumer(RabbitConsumer):
    def __init__(self):
        super().__init__()
        from src.pipelines.processing import DefaultImageAnalysisPipeline

        self.logger = logging.getLogger("ImageProcessorConsumer")
        self.repository = MongoPipelineRepository.from_uri(MONGO_URI, MONGO_DB_NAME)
        self.embedding_store = WeaviateEmbeddingStore()
        self.pipeline = DefaultImageAnalysisPipeline(embedding_store=self.embedding_store)

    async def on_message(self, message):
        async with message.process(requeue=False):
            job_id = message.body.decode().strip()
            self.logger.info("Processing job_id=%s", job_id)
            try:
                await asyncio.to_thread(self.pipeline.run_job, self.repository, job_id)
            except Exception:
                self.logger.exception("Failed job_id=%s", job_id)
                job = self.repository.get_job(job_id)
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
        self.embedding_store.close()
