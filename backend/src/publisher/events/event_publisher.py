"""Publisher for the live-events fanout — the worker/monitor/API's half of the pipe.

The three PixQuery processes are separate: ``worker_main`` runs pipelines,
``monitoring_main`` dispatches jobs, and ``api_main`` is the one holding the
browser's WebSocket. An event raised in the worker therefore has to cross a
process boundary before it can reach a UI.

RabbitMQ is already a hard dependency, so events ride a **fanout** exchange:
every subscriber declares its own exclusive queue bound to the exchange and so
receives *every* event. (A single shared queue would round-robin one copy between
API processes, and a browser connected to the "wrong" one would go silent.)
``EventPublisher`` below is the publish side, used by whichever process raises
an event; the consume side — binding a queue to this exchange and fanning
messages out to WebSockets — is ``EventConsumer``, in
``src/consumer/events/event_consumer.py`` (it's a consumer, so it lives with
the rest of them; this is a publisher, so it lives here with the rest of those).

Delivery is deliberately best-effort — messages are non-persistent, the queues are
auto-delete, and a broker outage drops events rather than blocking a pipeline run.
Clients recover by refetching, so a missed event costs a delay, never correctness.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging

from src.config import EVENTS_EXCHANGE, RABBITMQ_URL
from src.domain_events import Event
from src.infrastructure.messaging.rabbitmq_connection import _connect_with_retry
from src.infrastructure.messaging.rabbitmq_publisher import RabbitPublisher

_logger = logging.getLogger("pixquery.events")

# Bound so a wedged publish loop or a broker outage costs bounded memory
# instead of growing until the process dies.
_MAX_PENDING_PUBLISH = 2000


class EventPublisher(RabbitPublisher):
    """Fire-and-forget publisher, safe to call from any thread.

    Domain code (repositories, the pipeline executor) is synchronous, and in the
    worker it runs inside ``asyncio.to_thread`` — so it cannot ``await`` a publish.
    ``emit`` therefore only hands the event to the owning event loop and returns
    immediately; a background task does the actual AMQP write.

    A publisher that was never connected silently drops events. That is what lets
    the same repository code run in tests, in the monitor, and in a process where
    events are switched off, without any of them growing a conditional.

    Subclasses ``RabbitPublisher`` for the shared connect/close contract, but
    overrides ``connect()`` outright: this publishes to a fanout **exchange** via
    an internal queue + background drain task (so ``emit()`` can be called
    synchronously, even from a worker thread), not ``RabbitPublisher``'s direct
    ``publish()`` of one message to a named durable queue. Same reasoning as
    ``EventConsumer`` overriding ``connect()`` on the consume side.
    """

    def __init__(self, url: str = RABBITMQ_URL, exchange_name: str = EVENTS_EXCHANGE):
        super().__init__(queue_name=exchange_name, rabbitmq_url=url)
        self.exchange_name = exchange_name
        self._loop: asyncio.AbstractEventLoop | None = None
        self._queue: asyncio.Queue | None = None
        self._task: asyncio.Task | None = None
        self._exchange = None

    async def connect(self) -> None:
        self.connection = await _connect_with_retry(self.rabbitmq_url)
        self.channel = await self.connection.channel()
        self._loop = asyncio.get_running_loop()
        self._queue = asyncio.Queue(maxsize=_MAX_PENDING_PUBLISH)
        import aio_pika

        self._exchange = await self.channel.declare_exchange(
            self.exchange_name, aio_pika.ExchangeType.FANOUT, durable=True
        )
        self._task = asyncio.create_task(self._drain())
        _logger.info("Event publisher publishing to exchange '%s'", self.exchange_name)

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
        await super().close()
