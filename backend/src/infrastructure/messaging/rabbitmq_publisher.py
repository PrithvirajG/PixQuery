from src.config import RABBITMQ_QUEUE, RABBITMQ_URL
from src.infrastructure.messaging.rabbitmq_connection import _connect_with_retry


class RabbitPublisher:
    def __init__(self, queue_name=RABBITMQ_QUEUE, rabbitmq_url=RABBITMQ_URL):
        self.queue_name = queue_name
        self.rabbitmq_url = rabbitmq_url

    async def connect(self):
        self.connection = await _connect_with_retry(self.rabbitmq_url)
        self.channel = await self.connection.channel()
        self.queue = await self.channel.declare_queue(self.queue_name, durable=True)

    async def publish(self, message: str):
        import aio_pika

        await self.channel.default_exchange.publish(
            aio_pika.Message(
                body=message.encode(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            ),
            routing_key=self.queue_name,
        )

    async def close(self):
        await self.connection.close()
