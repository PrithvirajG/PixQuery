"""Centralized logging setup: one configuration point for every process.

Every module gets its logger via ``get_logger(__name__)`` rather than calling
``logging.getLogger`` directly, so the logger name always mirrors the package
path (``src.services.image_service`` -> ``pixquery.services.image_service``).
That hierarchy is what makes per-layer control possible: setting a level on
``pixquery.repositories`` (via the ``LOG_LEVELS`` env var) governs every
repository logger at once, without touching the ones underneath that already
carry their own override — standard ``logging`` propagation, nothing custom.

Call :func:`configure_logging` exactly once, at each process's entry point
(``api_main.py``, ``pipeline_worker_main.py``, ``file_watcher_main.py``,
``src/migrations/__main__.py``), before anything else logs.

Request tracing
----------------
:func:`bind_request_id` / :func:`request_scope` put a short id into a
``contextvars.ContextVar`` that every log line renders via ``%(request_id)s``.
Binding it once at the edge of a process — the API's HTTP middleware, or a
consumer's ``on_message`` reading the incoming AMQP message's
``correlation_id`` — makes every log line downstream of that call, across
however many services and repositories it passes through, carry the same id.
Publishing a message with ``correlation_id=get_request_id()`` (the default in
``RabbitPublisher.publish``) is what carries the id across the process
boundary, so one workspace scan is traceable end-to-end: API → scan_commands
→ file-watcher → image_task → pipeline-worker.
"""
from __future__ import annotations

import contextvars
import logging
import logging.handlers
import os
import sys
import uuid
from contextlib import contextmanager
from typing import Iterator

from src.config import (
    LOG_COLOR,
    LOG_DATE_FORMAT,
    LOG_DIR,
    LOG_FILE_BACKUP_COUNT,
    LOG_FILE_MAX_BYTES,
    LOG_FORMAT,
    LOG_LEVEL,
    LOG_LEVELS,
    LOG_TO_FILE,
)

_ROOT_NAME = "pixquery"
_configured = False

_request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default="-"
)


# ──────────────────────────────────────────────────────────────────────────
# Logger factory
# ──────────────────────────────────────────────────────────────────────────

def get_logger(name: str) -> logging.Logger:
    """Return a logger namespaced under ``pixquery``, mirroring the caller's module path.

    Call as ``get_logger(__name__)``. ``src.services.image_service`` becomes
    ``pixquery.services.image_service``, so its level can be controlled on its
    own, as part of the whole ``pixquery.services`` layer, or app-wide via
    ``pixquery`` — see ``LOG_LEVELS`` in ``config.py``.
    """
    if name.startswith("src."):
        name = name[len("src."):]
    elif name in ("src", "__main__"):
        name = "main"
    return logging.getLogger(f"{_ROOT_NAME}.{name}")


# ──────────────────────────────────────────────────────────────────────────
# Request tracing
# ──────────────────────────────────────────────────────────────────────────

def new_request_id() -> str:
    return uuid.uuid4().hex[:12]


def get_request_id() -> str:
    """The id bound in the current context, or ``"-"`` if nothing bound it."""
    return _request_id_var.get()


def bind_request_id(request_id: str | None = None) -> tuple[str, contextvars.Token]:
    """Bind ``request_id`` (or a freshly generated one) into the current context.

    Returns ``(value, token)`` — pass the token to :func:`reset_request_id` to
    restore whatever was bound before. Prefer :func:`request_scope` unless you
    need the two steps split apart (e.g. across an HTTP middleware's
    try/finally).
    """
    value = (request_id or "").strip()[:64] or new_request_id()
    token = _request_id_var.set(value)
    return value, token


def reset_request_id(token: contextvars.Token) -> None:
    _request_id_var.reset(token)


@contextmanager
def request_scope(request_id: str | None = None) -> Iterator[str]:
    """Bind a request id for the duration of the ``with`` block, then restore it.

    ``request_id=None`` generates a fresh one — use that at the start of any
    trigger chain that doesn't already carry one in (a filesystem event, a
    periodic reconcile tick), so its logs are still traceable as one unit.
    """
    value, token = bind_request_id(request_id)
    try:
        yield value
    finally:
        reset_request_id(token)


class _RequestIdFilter(logging.Filter):
    """Attaches the ambient request id to every record passing through a handler.

    Attached to handlers, not to the ``pixquery`` logger itself — a filter on a
    logger only runs for records logged directly through it, not ones
    propagating up from a descendant (``services.image_service``, etc.), and
    nearly every log call in this codebase goes through a descendant.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _request_id_var.get()
        return True


# ──────────────────────────────────────────────────────────────────────────
# Setup
# ──────────────────────────────────────────────────────────────────────────

class _ColorFormatter(logging.Formatter):
    """ANSI-colorizes the level name. Only ever installed on a TTY stream."""

    _COLORS = {
        logging.DEBUG: "\x1b[36m",      # cyan
        logging.INFO: "\x1b[32m",       # green
        logging.WARNING: "\x1b[33m",    # yellow
        logging.ERROR: "\x1b[31m",      # red
        logging.CRITICAL: "\x1b[97m\x1b[41m",  # white on red
    }
    _RESET = "\x1b[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self._COLORS.get(record.levelno, "")
        original = record.levelname
        if color:
            record.levelname = f"{color}{original}{self._RESET}"
        try:
            return super().format(record)
        finally:
            record.levelname = original


def _make_console_handler() -> logging.Handler:
    handler = logging.StreamHandler(sys.stdout)
    use_color = LOG_COLOR and hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
    formatter_cls = _ColorFormatter if use_color else logging.Formatter
    handler.setFormatter(formatter_cls(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))
    handler.addFilter(_RequestIdFilter())
    return handler


def _make_file_handler(process_name: str) -> logging.Handler:
    os.makedirs(LOG_DIR, exist_ok=True)
    path = os.path.join(LOG_DIR, f"{process_name}.log")
    handler = logging.handlers.RotatingFileHandler(
        path,
        maxBytes=LOG_FILE_MAX_BYTES,
        backupCount=LOG_FILE_BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))
    handler.addFilter(_RequestIdFilter())
    return handler


def _apply_level_overrides(raw: str) -> None:
    """Parse ``LOG_LEVELS`` (``"logger.name=LEVEL,other.name=LEVEL"``) and apply each."""
    root = logging.getLogger(_ROOT_NAME)
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry or "=" not in entry:
            continue
        name, level = (part.strip() for part in entry.split("=", 1))
        try:
            logging.getLogger(name).setLevel(level.upper())
        except (ValueError, TypeError):
            root.warning("Ignoring invalid LOG_LEVELS entry %r", entry)


def configure_logging(process_name: str = "app") -> None:
    """Wire up the ``pixquery`` logger tree. Call once, at process startup.

    Idempotent — a second call (e.g. a test importing two entry points in one
    process) is a no-op, so handlers are never duplicated.
    """
    global _configured
    if _configured:
        return
    _configured = True

    root = logging.getLogger(_ROOT_NAME)
    root.setLevel(LOG_LEVEL.upper())
    root.propagate = False  # don't also hand records to the stdlib root logger
    root.handlers.clear()
    root.addHandler(_make_console_handler())
    if LOG_TO_FILE:
        root.addHandler(_make_file_handler(process_name))

    if LOG_LEVELS:
        _apply_level_overrides(LOG_LEVELS)
