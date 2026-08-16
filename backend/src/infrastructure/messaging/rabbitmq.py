import asyncio
import logging
import time

from src.config import RABBITMQ_CONNECT_TIMEOUT, RABBITMQ_QUEUE, RABBITMQ_URL


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

_logger = logging.getLogger("RabbitMQ")


async def _connect_with_retry(rabbitmq_url, timeout=RABBITMQ_CONNECT_TIMEOUT):
    """Connect to RabbitMQ, retrying until the broker is ready or ``timeout`` elapses.

    A freshly started broker accepts the TCP socket before it can speak AMQP and
    drops the handshake ("Read 0 bytes but 1 bytes expected"). Retrying with
    backoff lets startup order be arbitrary instead of crashing the process.
    """
    import aio_pika
    from aio_pika.exceptions import AMQPError

    deadline = time.monotonic() + timeout
    delay = 1.0
    attempt = 0
    while True:
        attempt += 1
        try:
            return await aio_pika.connect_robust(rabbitmq_url)
        except (AMQPError, OSError) as exc:
            if time.monotonic() >= deadline:
                _logger.error(
                    "Could not connect to RabbitMQ after %.0fs (%d attempts): %s",
                    timeout,
                    attempt,
                    exc,
                )
                raise
            _logger.warning(
                "RabbitMQ not ready (attempt %d): %s — retrying in %.1fs",
                attempt,
                exc,
                delay,
            )
            await asyncio.sleep(delay)
            delay = min(delay * 2, 5.0)


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


class RabbitConsumer:
    def __init__(self, queue_name=RABBITMQ_QUEUE, rabbitmq_url=RABBITMQ_URL):
        self.queue_name = queue_name
        self.rabbitmq_url = rabbitmq_url
        self.logger = logging.getLogger("RabbitConsumer")
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
