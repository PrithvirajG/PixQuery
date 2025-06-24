import asyncio
import aio_pika

RABBITMQ_URL = "amqp://guest:guest@localhost/"
QUEUE_NAME = "image_tasks"

class RabbitPublisher:
    def __init__(self, queue_name=QUEUE_NAME):
        self.queue_name = queue_name

    async def connect(self):
        self.connection = await aio_pika.connect_robust(RABBITMQ_URL)
        self.channel = await self.connection.channel()
        self.queue = await self.channel.declare_queue(self.queue_name, durable=True)

    async def publish(self, message: str):
        await self.channel.default_exchange.publish(
            aio_pika.Message(body=message.encode()),
            routing_key=self.queue_name,
        )

    async def close(self):
        await self.connection.close()
