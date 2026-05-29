import asyncio

from src.pipelines.processing import ImageProcessorConsumer


async def start_worker():
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
