"""A mutable, swappable event sink shared by services.

Processes build their services before the event bus exists — the bus needs the
asyncio loop, services are constructed at import or first-request time — so the
sink has to be attached after the fact, the same way the old god-repository's
``set_event_sink`` worked. Services hold a reference to one shared
:class:`EventSink` and call ``.emit()`` on it; wiring up the real bus later (or
leaving it disconnected — tests, migrations, one-shot scripts) is just
``.set()``.
"""

from __future__ import annotations

from typing import Callable

from src.domain_events import Event
from src.logging_config import get_logger

_logger = get_logger(__name__)


class EventSink:
    def __init__(self):
        self._sink: Callable[[Event], None] | None = None

    def set(self, sink: Callable[[Event], None] | None) -> None:
        self._sink = sink

    def emit(self, event: Event) -> None:
        """Publish, swallowing anything that goes wrong.

        Emitting must never be able to fail a request: live updates are a
        convenience layered on top of data that is already durably written.
        """
        sink = self._sink
        if sink is None:
            return
        try:
            sink(event)
        except Exception:
            _logger.debug("Event sink raised; ignoring", exc_info=True)
