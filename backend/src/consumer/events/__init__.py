"""Live-events consumer: the API process's fanout subscriber."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.consumer.events.event_consumer import EventConsumer

__all__ = [
    "EventConsumer",
]


def __getattr__(name):
    if name == "EventConsumer":
        from src.consumer.events.event_consumer import EventConsumer

        return EventConsumer
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
