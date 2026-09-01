"""Shared AMQP connection helper for every publisher and consumer in ``messaging/``."""

import asyncio
import logging
import time

from src.config import RABBITMQ_CONNECT_TIMEOUT

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
