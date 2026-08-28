"""Cross-process transport for domain events.

The three PixQuery processes are separate: ``worker_main`` runs pipelines,
``monitoring_main`` dispatches jobs, and ``api_main`` is the one holding the
browser's WebSocket. An event raised in the worker therefore has to cross a
process boundary before it can reach a UI.

RabbitMQ is already a hard dependency, so events ride a **fanout** exchange:
every subscriber declares its own exclusive queue bound to the exchange and so
receives *every* event. (A single shared queue would round-robin one copy between
API processes, and a browser connected to the "wrong" one would go silent.)

Delivery is deliberately best-effort — messages are non-persistent, the queues are
auto-delete, and a broker outage drops events rather than blocking a pipeline run.
Clients recover by refetching, so a missed event costs a delay, never correctness.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import AsyncIterator, Iterator

from src.config import EVENTS_EXCHANGE, RABBITMQ_URL
from src.events import Event
from src.infrastructure.messaging.rabbitmq import _connect_with_retry

_logger = logging.getLogger("pixquery.events")

# Bound both directions so a wedged consumer or a broker outage costs bounded
# memory instead of growing until the process dies.
_MAX_PENDING_PUBLISH = 2000
_MAX_PENDING_PER_LISTENER = 500


class EventBus:
    """Fire-and-forget publisher, safe to call from any thread.

    Domain code (repositories, the pipeline executor) is synchronous, and in the
    worker it runs inside ``asyncio.to_thread`` — so it cannot ``await`` a publish.
    ``emit`` therefore only hands the event to the owning event loop and returns
    immediately; a background task does the actual AMQP write.

    A bus that was never started silently drops events. That is what lets the same
    repository code run in tests, in the monitor, and in a process where events are
    switched off, without any of them growing a conditional.
    """

    def __init__(self, url: str = RABBITMQ_URL, exchange_name: str = EVENTS_EXCHANGE):
        self._url = url
        self._exchange_name = exchange_name
        self._loop: asyncio.AbstractEventLoop | None = None
        self._queue: asyncio.Queue | None = None
        self._task: asyncio.Task | None = None
        self._connection = None
        self._exchange = None

    async def start(self) -> "EventBus":
        self._loop = asyncio.get_running_loop()
        self._queue = asyncio.Queue(maxsize=_MAX_PENDING_PUBLISH)
        self._connection = await _connect_with_retry(self._url)
        channel = await self._connection.channel()
        import aio_pika

        self._exchange = await channel.declare_exchange(
            self._exchange_name, aio_pika.ExchangeType.FANOUT, durable=True
        )
        self._task = asyncio.create_task(self._drain())
        _logger.info("Event bus publishing to exchange '%s'", self._exchange_name)
        return self

    def emit(self, event: Event) -> None:
        """Queue an event for publication. Never blocks, never raises."""
        loop, queue = self._loop, self._queue
        if loop is None or queue is None or loop.is_closed():
            return
        try:
            loop.call_soon_threadsafe(self._offer, queue, event)
        except RuntimeError:
            # Loop shut down between the check and the call — nothing to do.
            pass

    @staticmethod
    def _offer(queue: asyncio.Queue, event: Event) -> None:
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            _logger.warning("Event queue full — dropping %s event", event.type)

    async def _drain(self) -> None:
        import aio_pika

        while True:
            event = await self._queue.get()
            try:
                await self._exchange.publish(
                    aio_pika.Message(
                        body=event.to_json().encode(),
                        # UI notifications: worthless once stale, so don't pay to
                        # persist them or replay them after a broker restart.
                        delivery_mode=aio_pika.DeliveryMode.NOT_PERSISTENT,
                        content_type="application/json",
                    ),
                    routing_key="",
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                # Never let a broker hiccup escape into pipeline execution.
                _logger.warning("Could not publish %s event: %s", event.type, exc)
            finally:
                self._queue.task_done()

    async def close(self) -> None:
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        if self._connection:
            await self._connection.close()
            self._connection = None


class EventSubscriber:
    """Receives every event and fans it out to in-process listeners.

    One AMQP consumer serves all the WebSockets in an API process; each socket
    registers its own bounded queue via :meth:`listen`.
    """

    def __init__(self, url: str = RABBITMQ_URL, exchange_name: str = EVENTS_EXCHANGE):
        self._url = url
        self._exchange_name = exchange_name
        self._connection = None
        self._listeners: set[asyncio.Queue] = set()

    async def start(self) -> "EventSubscriber":
        self._connection = await _connect_with_retry(self._url)
        channel = await self._connection.channel()
        import aio_pika

        exchange = await channel.declare_exchange(
            self._exchange_name, aio_pika.ExchangeType.FANOUT, durable=True
        )
        # Exclusive + auto-delete + server-named: this process's private mailbox,
        # cleaned up by the broker when the connection drops.
        queue = await channel.declare_queue("", exclusive=True, auto_delete=True)
        await queue.bind(exchange)
        await queue.consume(self._on_message, no_ack=True)
        _logger.info("Event subscriber bound to exchange '%s'", self._exchange_name)
        return self

    async def _on_message(self, message) -> None:
        try:
            event = Event.from_json(message.body)
        except Exception:
            _logger.warning("Discarding malformed event message")
            return
        for queue in list(self._listeners):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                # This listener is not keeping up; skipping is correct — it will
                # refetch and converge rather than fall further behind.
                _logger.debug("Listener queue full — dropping %s event", event.type)

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
        if self._connection:
            await self._connection.close()
            self._connection = None


@contextlib.asynccontextmanager
async def event_bus(url: str = RABBITMQ_URL) -> AsyncIterator[EventBus]:
    """Start a bus for the lifetime of the block, degrading to a no-op bus.

    A process whose broker is unreachable should still do its real work — it just
    won't push live updates — so a failed start is logged, not raised.
    """
    bus = EventBus(url)
    try:
        await bus.start()
    except Exception as exc:
        _logger.warning("Live events disabled — could not reach the broker: %s", exc)
    try:
        yield bus
    finally:
        await bus.close()
