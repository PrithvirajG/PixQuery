"""Live-events publisher: the worker/monitor/API's side of the fanout."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.publisher.events.event_publisher import EventPublisher

__all__ = [
    "EventPublisher",
]


def __getattr__(name):
    if name == "EventPublisher":
        from src.publisher.events.event_publisher import EventPublisher

        return EventPublisher
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
