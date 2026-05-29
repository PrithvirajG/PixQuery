import logging

from src.config import RABBITMQ_QUEUE, RABBITMQ_URL


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


class RabbitPublisher:
    def __init__(self, queue_name=RABBITMQ_QUEUE, rabbitmq_url=RABBITMQ_URL):
        self.queue_name = queue_name
        self.rabbitmq_url = rabbitmq_url

    async def connect(self):
        import aio_pika

        self.connection = await aio_pika.connect_robust(self.rabbitmq_url)
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


class RabbitConsumer:
    def __init__(self, queue_name=RABBITMQ_QUEUE, rabbitmq_url=RABBITMQ_URL):
        self.queue_name = queue_name
        self.rabbitmq_url = rabbitmq_url
        self.logger = logging.getLogger("RabbitConsumer")
        self.logger.info("Initializing RabbitMQ consumer for queue: %s", self.queue_name)

    async def connect(self):
        import aio_pika

        self.connection = await aio_pika.connect_robust(self.rabbitmq_url)
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
