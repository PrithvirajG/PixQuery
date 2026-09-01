"""Messaging adapters.

Neither side of the live-events fanout lives here: the consume side
(``EventConsumer``) is in ``src/consumer/events/``, the publish side
(``EventPublisher``) is in ``src/publisher/events/`` — each with the rest of
its own kind. This package holds only the generic transport primitives they
both build on: ``rabbitmq_publisher.py``'s ``RabbitPublisher``,
``rabbitmq_consumer.py``'s ``RabbitConsumer``, sharing
``rabbitmq_connection.py``'s connect-with-retry, plus ``event_sink.py``'s
``EventSink``.
"""

from src.infrastructure.messaging.event_sink import EventSink
from src.infrastructure.messaging.rabbitmq_consumer import RabbitConsumer
from src.infrastructure.messaging.rabbitmq_publisher import RabbitPublisher

__all__ = [
    "EventSink",
    "RabbitConsumer",
    "RabbitPublisher",
]
