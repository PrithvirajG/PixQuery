"""Live event stream for the UI.

One WebSocket per browser tab. The socket is a *notification* channel: it says
which (image, pipeline) pair changed and to what state, and the client refetches
the detail endpoint for the substance. See ``src/events.py`` for why the payloads
are deliberately thin.

Authorization is enforced per event, not just at connect time: an event is
forwarded only if its ``workspace_id`` is one the connected user can reach. The
set is resolved once at connect and refreshed lazily, so being added to a
workspace mid-session starts delivering its events without a reconnect.
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.api.security import decode_access_token
from src.config import EVENTS_ENABLED
from src.repositories import MongoPipelineRepository

router = APIRouter(tags=["websocket"])

logger = logging.getLogger("pixquery.ws")

# Re-resolve the user's workspace list at most this often (seconds). Membership
# changes are rare; this keeps a long-lived socket from hammering Mongo per event.
_ACCESS_REFRESH_SECONDS = 30

# Sent when no traffic has flowed for this long, so proxies (and the browser)
# don't quietly reap an idle connection.
_KEEPALIVE_SECONDS = 25

_subscriber = None
_subscriber_lock = asyncio.Lock()


async def get_subscriber():
    """Lazily start this process's single AMQP consumer, shared by every socket.

    Started on first connect rather than at import so the API still boots when the
    broker is down — sockets then simply fail to attach instead of taking the
    whole app with them.
    """
    global _subscriber
    if not EVENTS_ENABLED:
        return None
    if _subscriber is not None:
        return _subscriber
    async with _subscriber_lock:
        if _subscriber is None:
            from src.infrastructure.messaging import EventSubscriber

            _subscriber = await EventSubscriber().start()
    return _subscriber


async def reset_subscriber() -> None:
    """Drop the shared subscriber (used by tests and on shutdown)."""
    global _subscriber
    if _subscriber is not None:
        await _subscriber.close()
        _subscriber = None


class _AccessGate:
    """Caches which workspaces the connected user may see."""

    def __init__(self, repository, user_id: str):
        self._repository = repository
        self._user_id = user_id
        self._ids: set[str] = set()
        self._checked_at = 0.0

    def allows(self, workspace_id: str | None) -> bool:
        # An event with no workspace can't be attributed to a tenant, so it is
        # never forwarded — failing closed is the safe default here.
        if workspace_id is None:
            return False
        now = asyncio.get_running_loop().time()
        if now - self._checked_at > _ACCESS_REFRESH_SECONDS:
            try:
                self._ids = set(self._repository.accessible_workspace_ids(self._user_id))
            except Exception:
                logger.debug("Could not refresh workspace access", exc_info=True)
            self._checked_at = now
        return workspace_id in self._ids


def _authenticate(token: str | None, repository) -> dict | None:
    """Resolve a user from a token passed as a query parameter.

    The browser WebSocket API cannot set an Authorization header, so the token
    travels as ``?token=``. It is the same short-lived JWT the REST API uses.
    """
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload:
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    return repository.get_user(user_id)


@router.websocket("/ws/events")
async def events_socket(websocket: WebSocket, token: str | None = None):
    from src.api.dependencies import get_pipeline_repository

    repository: MongoPipelineRepository = get_pipeline_repository()
    user = _authenticate(token, repository)
    if not user:
        # 1008 = policy violation; closing before accept would give the client no
        # way to tell "unauthorized" apart from "server unreachable".
        await websocket.accept()
        await websocket.send_json({"type": "error", "data": {"message": "Unauthorized"}})
        await websocket.close(code=1008)
        return

    await websocket.accept()

    subscriber = None
    try:
        subscriber = await get_subscriber()
    except Exception as exc:
        logger.warning("Event subscriber unavailable: %s", exc)

    if subscriber is None:
        await websocket.send_json(
            {"type": "unavailable", "data": {"message": "Live events are not available"}}
        )
        await websocket.close(code=1011)
        return

    gate = _AccessGate(repository, user["_id"])
    await websocket.send_json({"type": "ready", "data": {"user_id": user["_id"]}})

    with subscriber.listen() as queue:
        # A reader task exists only to notice the client going away: without it a
        # disconnect is invisible until the next send, which for an idle tab could
        # be minutes.
        reader = asyncio.create_task(_drain_incoming(websocket))
        try:
            while True:
                if reader.done():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=_KEEPALIVE_SECONDS)
                except asyncio.TimeoutError:
                    await websocket.send_json({"type": "ping", "data": {}})
                    continue
                if not gate.allows(event.workspace_id):
                    continue
                await websocket.send_json(event.to_dict())
        except (WebSocketDisconnect, RuntimeError):
            pass
        except Exception:
            logger.debug("Event socket closed unexpectedly", exc_info=True)
        finally:
            reader.cancel()


async def _drain_incoming(websocket: WebSocket) -> None:
    """Consume client frames so a disconnect is detected promptly.

    Clients have nothing to say — filtering happens server-side, from the JWT —
    so anything received is discarded.
    """
    try:
        while True:
            await websocket.receive_text()
    except Exception:
        return
