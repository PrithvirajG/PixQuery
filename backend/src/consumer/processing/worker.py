import asyncio
import sys

from src.consumer.processing import FileObservationConsumer, ImageProcessorConsumer
from src.logging_config import get_logger

logger = get_logger(__name__)


async def start_pipeline_worker():
    """Run both of the pipeline-worker process's consumers.

    ``ImageProcessorConsumer`` executes dispatched jobs (``image_task``).
    ``FileObservationConsumer`` is what creates those jobs in the first place —
    turning a raw ``{workspace_id, path}`` observation (from the API's manual
    Scan route or the live filesystem watcher) into a hashed/upserted/dispatched
    job via ``ReconciliationService.observe_file``. Both live in this one
    process because "ingest a file" and "execute its pipeline" are the same
    underlying concern — only *listing* (deciding what might need ingesting)
    lives elsewhere, in the API and the watcher.
    """
    image_consumer = ImageProcessorConsumer()
    await image_consumer.connect()
    await image_consumer.start_consuming()

    file_observation_consumer = FileObservationConsumer()
    await file_observation_consumer.connect()
    await file_observation_consumer.start_consuming()

    exit_code = 0
    try:
        # Runs until Ctrl-C, or until a CUDA failure leaves the GPU unusable.
        await image_consumer.fatal.wait()
        logger.critical("GPU unusable after a CUDA error — exiting; restart the worker")
        exit_code = 3
    except KeyboardInterrupt:
        logger.info("Shutting down consumer...")
    finally:
        await image_consumer.close()
        await file_observation_consumer.close()
    if exit_code:
        sys.exit(exit_code)
