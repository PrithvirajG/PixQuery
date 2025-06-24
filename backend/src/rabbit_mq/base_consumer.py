import asyncio
import logging

import aio_pika

RABBITMQ_URL = "amqp://guest:guest@localhost/"
QUEUE_NAME = "image_task"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

class RabbitConsumer:
    def __init__(self, queue_name=QUEUE_NAME):
        self.queue_name = queue_name
        self.logger = logging.getLogger("RabbitConsumer")
        self.logger.info("Initializing RabbitMQ consumer for queue: %s", self.queue_name)

    async def connect(self):
        self.connection = await aio_pika.connect_robust(RABBITMQ_URL)
        self.channel = await self.connection.channel()
        self.queue = await self.channel.declare_queue(self.queue_name, durable=True)
        self.logger.info("Connected to RabbitMQ and declared queue: %s", self.queue_name)

    async def start_consuming(self):
        await self.queue.consume(self.on_message, no_ack=False)

    async def on_message(self, message: aio_pika.message.AbstractIncomingMessage):
        self.logger.info("Received message: %s", message.body.decode())

    async def close(self):
        await self.connection.close()
