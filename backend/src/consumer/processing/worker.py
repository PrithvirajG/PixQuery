import asyncio

from src.consumer.processing import ImageProcessorConsumer
from src.logging_config import get_logger

logger = get_logger(__name__)


async def start_pipeline_worker():
    consumer = ImageProcessorConsumer()
    await consumer.connect()
    await consumer.start_consuming()

    try:
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        logger.info("Shutting down consumer...")
    finally:
        await consumer.close()
