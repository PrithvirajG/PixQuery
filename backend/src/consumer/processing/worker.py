import asyncio

from src.consumer.processing import ImageProcessorConsumer


async def start_pipeline_worker():
    consumer = ImageProcessorConsumer()
    await consumer.connect()
    await consumer.start_consuming()

    try:
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        print("Shutting down consumer...")
    finally:
        await consumer.close()
