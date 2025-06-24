import asyncio

from rq import Worker, Queue
from redis import Redis
from rmq_processor import ImageProcessorConsumer


def start_worker(queue_name='photos'):
    redis_conn = Redis(host="localhost", port=6379)
    queue = Queue(name=queue_name, connection=redis_conn)
    worker = Worker(queues=[queue], connection=redis_conn)
    worker.work()

async def start_rmq_worker(queue_name='photos'):
    consumer = ImageProcessorConsumer()
    await consumer.connect()
    await consumer.start_consuming()  # <- non-blocking, sets up callback

    # Keep the event loop alive
    try:
        while True:
            await asyncio.sleep(3600)  # sleep 1 hour (effectively forever)
    except KeyboardInterrupt:
        print("Shutting down consumer...")

if __name__ == '__main__':
    asyncio.run(start_rmq_worker())
