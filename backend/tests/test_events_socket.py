"""/ws/events: auth handshake, per-tenant filtering, and subscriber lifecycle."""
import asyncio
import contextlib
import unittest
from unittest import mock

from starlette.websockets import WebSocketDisconnect

from src.api import dependencies as deps
from src.api.routes.ws import events_socket as es
from src.api.security import create_access_token
from src.domain_events import Event
from tests.api_client import build_client, make_user


class FakeSubscriber:
    def __init__(self, events):
        self.events = events

    @contextlib.contextmanager
    def listen(self):
        queue = asyncio.Queue()
        for event in self.events:
            queue.put_nowait(event)
        yield queue


class AccessGateTests(unittest.TestCase):
    def setUp(self):
        _, self.r = build_client()
        self.user = make_user(self.r, "alice")
        self.mine = self.r.workspaces.create(owner_id=self.user["_id"], name="M", workspace_path="/m", pipeline_ids=[], extensions=[], active=True)

    def _allows(self, gate, workspace_id):
        async def go():
            return gate.allows(workspace_id)

        return asyncio.run(go())

    def test_event_without_workspace_is_never_forwarded(self):
        # Review Focus #4
        self.assertFalse(self._allows(es._AccessGate(self.r.workspaces, self.user["_id"]), None))

    def test_own_workspace_allowed_other_tenants_not(self):
        gate = es._AccessGate(self.r.workspaces, self.user["_id"])
        self.assertTrue(self._allows(gate, self.mine["_id"]))
        self.assertFalse(self._allows(gate, "someone-elses-ws"))

    def test_new_membership_is_picked_up_after_the_refresh_window(self):
        other = self.r.workspaces.create(owner_id="bob", name="B", workspace_path="/b", pipeline_ids=[], extensions=[], active=True)
        gate = es._AccessGate(self.r.workspaces, self.user["_id"])
        self.assertFalse(self._allows(gate, other["_id"]))
        self.r.workspaces.add_member(other["_id"], self.user["_id"], "viewer")
        self.assertFalse(self._allows(gate, other["_id"]))  # still cached
        gate._checked_at = -1e9  # force the refresh window to have elapsed
        self.assertTrue(self._allows(gate, other["_id"]))


class EventsSocketTests(unittest.TestCase):
    def setUp(self):
        self.client, self.r = build_client()
        self.user = make_user(self.r, "alice")
        self.mine = self.r.workspaces.create(owner_id=self.user["_id"], name="M", workspace_path="/m", pipeline_ids=[], extensions=[], active=True)
        self.token = create_access_token({"sub": self.user["_id"]})
        for name, value in (
            ("get_users_repository", lambda: self.r.users),
            ("get_workspace_definitions_repository", lambda: self.r.workspaces),
        ):
            p = mock.patch.object(deps, name, value)
            p.start()
            self.addCleanup(p.stop)
        p = mock.patch.object(es, "_KEEPALIVE_SECONDS", 0.05)
        p.start()
        self.addCleanup(p.stop)

    def _with_subscriber(self, subscriber):
        p = mock.patch.object(es, "get_subscriber", mock.AsyncMock(return_value=subscriber))
        p.start()
        self.addCleanup(p.stop)

    def test_missing_or_bad_token_gets_error_then_1008(self):
        for url in ("/ws/events", "/ws/events?token=garbage"):
            with self.subTest(url=url):
                with self.client.websocket_connect(url) as ws:
                    self.assertEqual(ws.receive_json()["type"], "error")
                    with self.assertRaises(WebSocketDisconnect) as ctx:
                        ws.receive_json()
                    self.assertEqual(ctx.exception.code, 1008)

    def test_no_subscriber_reports_unavailable_then_1011(self):
        self._with_subscriber(None)
        with self.client.websocket_connect(f"/ws/events?token={self.token}") as ws:
            self.assertEqual(ws.receive_json()["type"], "unavailable")
            with self.assertRaises(WebSocketDisconnect) as ctx:
                ws.receive_json()
            self.assertEqual(ctx.exception.code, 1011)

    def test_only_this_users_workspace_events_are_forwarded(self):
        # Review Focus #4
        self._with_subscriber(FakeSubscriber([
            Event(type="leak", workspace_id="other-tenant"),
            Event(type="orphan", workspace_id=None),
            Event(type="mine", workspace_id=self.mine["_id"]),
        ]))
        with self.client.websocket_connect(f"/ws/events?token={self.token}") as ws:
            ready = ws.receive_json()
            self.assertEqual(ready, {"type": "ready", "data": {"user_id": self.user["_id"]}})
            forwarded = ws.receive_json()
            self.assertEqual((forwarded["type"], forwarded["workspace_id"]), ("mine", self.mine["_id"]))
            self.assertEqual(ws.receive_json()["type"], "ping")  # keepalive, nothing leaked in between


class SubscriberLifecycleTests(unittest.TestCase):
    def test_disabled_events_mean_no_subscriber(self):
        with mock.patch.object(es, "EVENTS_ENABLED", False):
            self.assertIsNone(asyncio.run(es.get_subscriber()))

    def test_subscriber_is_created_once_and_reset_closes_it(self):
        original_subscriber = es._subscriber
        original_lock = es._subscriber_lock

        def _restore():
            es._subscriber = original_subscriber
            es._subscriber_lock = original_lock

        self.addCleanup(_restore)

        created = []

        class Consumer:
            def __init__(self):
                created.append(self)
                self.closed = False

            async def connect(self):
                pass

            async def start_consuming(self):
                pass

            async def close(self):
                self.closed = True

        async def go():
            es._subscriber = None
            es._subscriber_lock = asyncio.Lock()
            with mock.patch.object(es, "EVENTS_ENABLED", True), \
                    mock.patch("src.consumer.events.EventConsumer", Consumer):
                first = await es.get_subscriber()
                second = await es.get_subscriber()
                await es.reset_subscriber()
            return first, second

        first, second = asyncio.run(go())
        self.assertIs(first, second)
        self.assertEqual(len(created), 1)
        self.assertTrue(first.closed)
        self.assertIsNone(es._subscriber)


if __name__ == "__main__":
    unittest.main()
