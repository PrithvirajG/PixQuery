"""Consumer for the live-events fanout — the API process's half of the pipe.

``EventPublisher`` (``publisher/events/event_publisher.py``) is the publish side,
used by whichever process raises a domain event (worker, monitor, or the API
itself). ``EventConsumer`` is the consume side: it binds its own exclusive,
auto-delete queue to the same fanout exchange, so every API process instance
gets its own full copy of every event, then fans each one out to the
WebSocket connections open in this process — see
``src/api/routes/ws/events_socket.py``'s ``events_socket``, the only caller.

Subclasses ``RabbitConsumer`` for the shared connect/consume/close contract and
logger convention, but overrides ``connect()``/``start_consuming()`` outright:
this is fanout pub/sub against an anonymous, exclusive, auto-delete queue bound
to an exchange (``no_ack=True`` — a missed notification just costs a UI
refetch, never correctness), not the named durable work queue
``RabbitConsumer.connect()`` sets up for competing consumers. Calling
``super().connect()`` would declare the wrong kind of queue (a durable one
literally named after the exchange), so this replaces it rather than extending
it — the point of subclassing here is a consistent interface, not shared
connect logic.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import Iterator

from src.config import EVENTS_EXCHANGE, RABBITMQ_URL
from src.domain_events import Event
from src.infrastructure.messaging.rabbitmq_connection import _connect_with_retry
from src.infrastructure.messaging.rabbitmq_consumer import RabbitConsumer
from src.logging_config import get_logger

# Bound so a wedged listener costs bounded memory instead of growing until the
# process dies.
_MAX_PENDING_PER_LISTENER = 500


class EventConsumer(RabbitConsumer):
    """Receives every event and fans it out to in-process listeners.

    One AMQP consumer serves all the WebSockets in an API process; each socket
    registers its own bounded queue via :meth:`listen`.
    """

    def __init__(self, url: str = RABBITMQ_URL, exchange_name: str = EVENTS_EXCHANGE):
        super().__init__(queue_name=exchange_name, rabbitmq_url=url)
        self.logger = get_logger(__name__)
        self.exchange_name = exchange_name
        self._listeners: set[asyncio.Queue] = set()

    async def connect(self) -> None:
        self.connection = await _connect_with_retry(self.rabbitmq_url)
        self.channel = await self.connection.channel()
        import aio_pika

        exchange = await self.channel.declare_exchange(
            self.exchange_name, aio_pika.ExchangeType.FANOUT, durable=True
        )
        # Exclusive + auto-delete + server-named: this process's private mailbox,
        # cleaned up by the broker when the connection drops.
        self.queue = await self.channel.declare_queue("", exclusive=True, auto_delete=True)
        await self.queue.bind(exchange)
        self.logger.info("Connected to RabbitMQ and bound to exchange '%s'", self.exchange_name)

    async def start_consuming(self) -> None:
        await self.queue.consume(self.on_message, no_ack=True)

    async def on_message(self, message) -> None:
        try:
            event = Event.from_json(message.body)
        except Exception:
            self.logger.warning("Discarding malformed event message")
            return
        for queue in list(self._listeners):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                # This listener is not keeping up; skipping is correct — it will
                # refetch and converge rather than fall further behind.
                self.logger.debug("Listener queue full — dropping %s event", event.type)

    @contextlib.contextmanager
    def listen(self) -> Iterator[asyncio.Queue]:
        """Register a listener queue for the duration of the ``with`` block."""
        queue: asyncio.Queue = asyncio.Queue(maxsize=_MAX_PENDING_PER_LISTENER)
        self._listeners.add(queue)
        try:
            yield queue
        finally:
            self._listeners.discard(queue)

    async def close(self) -> None:
        self._listeners.clear()
        await super().close()
