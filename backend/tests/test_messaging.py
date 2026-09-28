"""Messaging primitives against fakes of the aio-pika objects they touch."""
import asyncio
import json
import unittest
from types import SimpleNamespace
from unittest import mock

import aio_pika

from src.consumer.events.event_consumer import EventConsumer
from src.domain_events import Event
from src.infrastructure.messaging import rabbitmq_connection
from src.infrastructure.messaging.rabbitmq_consumer import RabbitConsumer
from src.infrastructure.messaging.rabbitmq_publisher import RabbitPublisher
from src.logging_config import request_scope
from src.publisher.events import event_publisher as event_publisher_mod
from src.publisher.events.event_publisher import EventPublisher


class FakeExchange:
    def __init__(self, fail_times=0):
        self.published = []
        self.fail_times = fail_times

    async def publish(self, message, routing_key):
        if self.fail_times:
            self.fail_times -= 1
            raise ConnectionError("broker hiccup")
        self.published.append((message, routing_key))


class FakeQueue:
    def __init__(self):
        self.consumed = None
        self.bound = None

    async def consume(self, callback, no_ack):
        self.consumed = (callback, no_ack)

    async def bind(self, exchange):
        self.bound = exchange


class FakeChannel:
    def __init__(self):
        self.default_exchange = FakeExchange()
        self.exchange = FakeExchange()
        self.queue = FakeQueue()
        self.qos = None
        self.declared_queues = []
        self.declared_exchanges = []

    async def set_qos(self, prefetch_count):
        self.qos = prefetch_count

    async def declare_queue(self, name, **kwargs):
        self.declared_queues.append((name, kwargs))
        return self.queue

    async def declare_exchange(self, name, kind, durable):
        self.declared_exchanges.append((name, kind, durable))
        return self.exchange


class FakeConnection:
    def __init__(self):
        self.chan = FakeChannel()
        self.closed = False

    async def channel(self):
        return self.chan

    async def close(self):
        self.closed = True


def run(coro):
    return asyncio.run(coro)


class ConnectWithRetryTests(unittest.TestCase):
    def test_retries_until_the_broker_is_ready(self):
        conn = FakeConnection()
        attempts = [OSError("refused"), OSError("refused"), conn]

        async def connect_robust(url):
            outcome = attempts.pop(0)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        with mock.patch("aio_pika.connect_robust", connect_robust), \
                mock.patch.object(rabbitmq_connection.asyncio, "sleep", mock.AsyncMock()) as sleep:
            self.assertIs(run(rabbitmq_connection._connect_with_retry("amqp://x", timeout=60)), conn)
        self.assertEqual([c.args[0] for c in sleep.call_args_list], [1.0, 2.0])  # exponential backoff

    def test_gives_up_after_the_deadline(self):
        async def connect_robust(url):
            raise OSError("refused")

        with mock.patch("aio_pika.connect_robust", connect_robust):
            with self.assertRaises(OSError):
                run(rabbitmq_connection._connect_with_retry("amqp://x", timeout=0))


class RabbitPublisherTests(unittest.TestCase):
    def _publisher(self):
        pub = RabbitPublisher(queue_name="q", rabbitmq_url="amqp://x")
        pub.channel = FakeChannel()
        return pub

    def test_publish_carries_the_ambient_request_id(self):
        pub = self._publisher()

        async def go():
            with request_scope("trace-1"):
                await pub.publish("job-1")

        run(go())
        message, routing_key = pub.channel.default_exchange.published[0]
        self.assertEqual((message.body, routing_key, message.correlation_id), (b"job-1", "q", "trace-1"))
        self.assertEqual(message.delivery_mode, aio_pika.DeliveryMode.PERSISTENT)

    def test_explicit_correlation_id_wins(self):
        pub = self._publisher()

        async def go():
            with request_scope("ambient"):
                await pub.publish("m", correlation_id="explicit")

        run(go())
        self.assertEqual(pub.channel.default_exchange.published[0][0].correlation_id, "explicit")

    def test_connect_declares_a_durable_queue(self):
        pub = RabbitPublisher(queue_name="q", rabbitmq_url="amqp://x")
        conn = FakeConnection()
        with mock.patch("src.infrastructure.messaging.rabbitmq_publisher._connect_with_retry", mock.AsyncMock(return_value=conn)):
            run(pub.connect())
        self.assertEqual(conn.chan.declared_queues, [("q", {"durable": True})])
        run(pub.close())
        self.assertTrue(conn.closed)


class RabbitConsumerTests(unittest.TestCase):
    def test_connect_sets_prefetch_and_durable_queue_then_consumes_with_ack(self):
        consumer = RabbitConsumer(queue_name="q", rabbitmq_url="amqp://x")
        conn = FakeConnection()
        with mock.patch("src.infrastructure.messaging.rabbitmq_consumer._connect_with_retry", mock.AsyncMock(return_value=conn)):
            run(consumer.connect())
        run(consumer.start_consuming())
        self.assertEqual(conn.chan.qos, 1)
        self.assertEqual(conn.chan.declared_queues, [("q", {"durable": True})])
        self.assertEqual(conn.chan.queue.consumed, (consumer.on_message, False))


class EventPublisherTests(unittest.TestCase):
    def test_unconnected_emit_is_a_silent_no_op(self):
        EventPublisher(url="amqp://x").emit(Event(type="t"))  # must not raise

    def test_emitted_events_are_published_non_persistent_to_the_fanout(self):
        conn = FakeConnection()
        pub = EventPublisher(url="amqp://x", exchange_name="ex")

        async def go():
            with mock.patch.object(event_publisher_mod, "_connect_with_retry", mock.AsyncMock(return_value=conn)):
                await pub.connect()
            pub.emit(Event(type="pipeline.state", workspace_id="w1"))
            await asyncio.sleep(0.05)
            await pub.close()

        run(go())
        self.assertEqual(conn.chan.declared_exchanges, [("ex", aio_pika.ExchangeType.FANOUT, True)])
        message, routing_key = conn.chan.exchange.published[0]
        self.assertEqual(json.loads(message.body)["workspace_id"], "w1")
        self.assertEqual(message.delivery_mode, aio_pika.DeliveryMode.NOT_PERSISTENT)
        self.assertTrue(conn.closed)

    def test_a_failed_publish_does_not_stop_later_events(self):
        conn = FakeConnection()
        conn.chan.exchange = FakeExchange(fail_times=1)
        pub = EventPublisher(url="amqp://x")

        async def go():
            with mock.patch.object(event_publisher_mod, "_connect_with_retry", mock.AsyncMock(return_value=conn)):
                await pub.connect()
            pub.emit(Event(type="first"))
            pub.emit(Event(type="second"))
            await asyncio.sleep(0.05)
            await pub.close()

        run(go())
        self.assertEqual([json.loads(m.body)["type"] for m, _ in conn.chan.exchange.published], ["second"])

    def test_full_queue_drops_instead_of_raising(self):
        queue = asyncio.Queue(maxsize=1)
        queue.put_nowait(Event(type="a"))
        EventPublisher._offer(queue, Event(type="b"))  # must not raise
        self.assertEqual(queue.qsize(), 1)


class EventConsumerTests(unittest.TestCase):
    def _message(self, body):
        return SimpleNamespace(body=body if isinstance(body, bytes) else body.encode())

    def test_connect_binds_an_exclusive_auto_delete_queue_and_consumes_without_ack(self):
        consumer = EventConsumer(url="amqp://x", exchange_name="ex")
        conn = FakeConnection()
        with mock.patch("src.consumer.events.event_consumer._connect_with_retry", mock.AsyncMock(return_value=conn)):
            run(consumer.connect())
        run(consumer.start_consuming())
        self.assertEqual(conn.chan.declared_queues, [("", {"exclusive": True, "auto_delete": True})])
        self.assertIs(conn.chan.queue.bound, conn.chan.exchange)
        self.assertEqual(conn.chan.queue.consumed[1], True)

    def test_event_fans_out_to_every_listener(self):
        consumer = EventConsumer(url="amqp://x")

        async def go():
            with consumer.listen() as a, consumer.listen() as b:
                await consumer.on_message(self._message(Event(type="t", workspace_id="w").to_json()))
                return a.get_nowait().workspace_id, b.get_nowait().workspace_id

        self.assertEqual(run(go()), ("w", "w"))

    def test_malformed_message_is_discarded(self):
        # Review Focus #5
        consumer = EventConsumer(url="amqp://x")

        async def go():
            with consumer.listen() as q:
                await consumer.on_message(self._message("{not json"))
                await consumer.on_message(self._message("[1, 2]"))
                return q.qsize()

        self.assertEqual(run(go()), 0)

    def test_a_full_listener_does_not_starve_the_others(self):
        # Review Focus #5
        consumer = EventConsumer(url="amqp://x")

        async def go():
            with consumer.listen() as slow, consumer.listen() as fast:
                while not slow.full():
                    slow.put_nowait(Event(type="backlog"))
                await consumer.on_message(self._message(Event(type="new").to_json()))
                return fast.get_nowait().type

        self.assertEqual(run(go()), "new")

    def test_listener_is_unregistered_on_exit(self):
        consumer = EventConsumer(url="amqp://x")

        async def go():
            with consumer.listen():
                pass
            return len(consumer._listeners)

        self.assertEqual(run(go()), 0)


if __name__ == "__main__":
    unittest.main()
