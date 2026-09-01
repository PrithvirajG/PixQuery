from src.config import RABBITMQ_QUEUE, RABBITMQ_URL
from src.infrastructure.messaging.rabbitmq_connection import _connect_with_retry
from src.logging_config import get_logger


class RabbitConsumer:
    def __init__(self, queue_name=RABBITMQ_QUEUE, rabbitmq_url=RABBITMQ_URL):
        self.queue_name = queue_name
        self.rabbitmq_url = rabbitmq_url
        self.logger = get_logger(__name__)
        self.logger.info("Initializing RabbitMQ consumer for queue: %s", self.queue_name)

    async def connect(self):
        self.connection = await _connect_with_retry(self.rabbitmq_url)
        self.channel = await self.connection.channel()
        await self.channel.set_qos(prefetch_count=1)
        self.queue = await self.channel.declare_queue(self.queue_name, durable=True)
        self.logger.info("Connected to RabbitMQ and declared queue: %s", self.queue_name)

    async def start_consuming(self):
        await self.queue.consume(self.on_message, no_ack=False)

    async def on_message(self, message):
        self.logger.info("Received message: %s", message.body.decode())

    async def close(self):
        await self.connection.close()
