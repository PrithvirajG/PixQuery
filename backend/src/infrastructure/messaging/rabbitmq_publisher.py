from src.config import RABBITMQ_QUEUE, RABBITMQ_URL
from src.infrastructure.messaging.rabbitmq_connection import _connect_with_retry
from src.logging_config import get_logger, get_request_id

_logger = get_logger(__name__)


class RabbitPublisher:
    def __init__(self, queue_name=RABBITMQ_QUEUE, rabbitmq_url=RABBITMQ_URL):
        self.queue_name = queue_name
        self.rabbitmq_url = rabbitmq_url

    async def connect(self):
        self.connection = await _connect_with_retry(self.rabbitmq_url)
        self.channel = await self.connection.channel()
        self.queue = await self.channel.declare_queue(self.queue_name, durable=True)

    async def publish(self, message: str, *, correlation_id: str | None = None):
        """Publish ``message`` to this publisher's queue.

        ``correlation_id`` defaults to whatever request id is bound in the
        current context (see ``logging_config.request_scope``), so a message
        published while handling a traced request carries that trace across
        the process boundary without every call site remembering to pass it —
        the receiving consumer's ``on_message`` reads it back off
        ``message.correlation_id`` and rebinds it before doing any work.
        """
        import aio_pika

        cid = correlation_id or get_request_id()
        await self.channel.default_exchange.publish(
            aio_pika.Message(
                body=message.encode(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                correlation_id=cid,
            ),
            routing_key=self.queue_name,
        )
        _logger.debug("Published to %s: %s [%s]", self.queue_name, message, cid)

    async def close(self):
        await self.connection.close()
