import {
  subscribeToEvents,
  setEventToken,
  __resetEventSocket,
} from './eventSocket';

// Minimal stand-in for the browser WebSocket: enough surface to drive open,
// message, and close, plus a registry so a test can reach the live instance.
class FakeSocket {
  static instances = [];

  constructor(url) {
    this.url = url;
    this.readyState = FakeSocket.CONNECTING;
    this.onopen = null;
    this.onmessage = null;
    this.onclose = null;
    this.onerror = null;
    this.closed = false;
    FakeSocket.instances.push(this);
  }

  open() {
    this.readyState = FakeSocket.OPEN;
    this.onopen?.();
  }

  send(data) {
    this.onmessage?.({ data: typeof data === 'string' ? data : JSON.stringify(data) });
  }

  close() {
    this.closed = true;
    this.readyState = FakeSocket.CLOSED;
    this.onclose?.();
  }

  static get last() {
    return FakeSocket.instances.at(-1);
  }
}
FakeSocket.CONNECTING = 0;
FakeSocket.OPEN = 1;
FakeSocket.CLOSING = 2;
FakeSocket.CLOSED = 3;

beforeEach(() => {
  jest.useFakeTimers();
  FakeSocket.instances = [];
  global.WebSocket = FakeSocket;
  __resetEventSocket();
});

afterEach(() => {
  __resetEventSocket();
  jest.useRealTimers();
});

describe('connection lifecycle', () => {
  test('does not connect without a token', () => {
    subscribeToEvents(() => {});
    expect(FakeSocket.instances).toHaveLength(0);
  });

  test('connects once a token and a subscriber both exist', () => {
    setEventToken('tok-1');
    subscribeToEvents(() => {});
    expect(FakeSocket.instances).toHaveLength(1);
    expect(FakeSocket.last.url).toContain('/ws/events?token=tok-1');
  });

  test('carries the token as a query parameter, url-encoded', () => {
    setEventToken('a b&c');
    subscribeToEvents(() => {});
    expect(FakeSocket.last.url).toContain('token=a%20b%26c');
  });

  test('several subscribers share one connection', () => {
    setEventToken('tok-1');
    subscribeToEvents(() => {});
    subscribeToEvents(() => {});
    subscribeToEvents(() => {});
    expect(FakeSocket.instances).toHaveLength(1);
  });

  test('closes when the last subscriber leaves', () => {
    setEventToken('tok-1');
    const off1 = subscribeToEvents(() => {});
    const off2 = subscribeToEvents(() => {});

    off1();
    expect(FakeSocket.last.closed).toBe(false);
    off2();
    expect(FakeSocket.last.closed).toBe(true);
  });

  test('a new token reconnects with the new credentials', () => {
    setEventToken('tok-1');
    subscribeToEvents(() => {});
    setEventToken('tok-2');

    expect(FakeSocket.instances).toHaveLength(2);
    expect(FakeSocket.last.url).toContain('token=tok-2');
  });

  test('logging out closes the socket and does not reopen it', () => {
    setEventToken('tok-1');
    subscribeToEvents(() => {});
    const socket = FakeSocket.last;

    setEventToken(null);

    expect(socket.closed).toBe(true);
    expect(FakeSocket.instances).toHaveLength(1);
  });
});

describe('delivery', () => {
  test('parsed events reach every subscriber', () => {
    const a = jest.fn();
    const b = jest.fn();
    setEventToken('tok-1');
    subscribeToEvents(a);
    subscribeToEvents(b);
    FakeSocket.last.open();

    FakeSocket.last.send({ type: 'pipeline_state', data: { state: 'queued' } });

    expect(a).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'pipeline_state' })
    );
    expect(b).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'pipeline_state' })
    );
  });

  test('keepalives and the handshake are not delivered as domain events', () => {
    const handler = jest.fn();
    setEventToken('tok-1');
    subscribeToEvents(handler);
    FakeSocket.last.open();
    handler.mockClear();

    FakeSocket.last.send({ type: 'ping', data: {} });
    FakeSocket.last.send({ type: 'ready', data: {} });

    expect(handler).not.toHaveBeenCalled();
  });

  test('malformed frames are dropped rather than thrown', () => {
    const handler = jest.fn();
    setEventToken('tok-1');
    subscribeToEvents(handler);
    FakeSocket.last.open();
    handler.mockClear();

    expect(() => FakeSocket.last.send('}{ not json')).not.toThrow();
    expect(handler).not.toHaveBeenCalled();
  });

  test('one throwing subscriber does not starve the others', () => {
    const good = jest.fn();
    jest.spyOn(console, 'error').mockImplementation(() => {});
    setEventToken('tok-1');
    subscribeToEvents(() => {
      throw new Error('subscriber bug');
    });
    subscribeToEvents(good);
    FakeSocket.last.open();

    FakeSocket.last.send({ type: 'pipeline_state', data: {} });

    expect(good).toHaveBeenCalled();
    console.error.mockRestore();
  });

  test('a subscriber joining an already-open socket is told it is live', () => {
    setEventToken('tok-1');
    subscribeToEvents(() => {});
    FakeSocket.last.open();

    const late = jest.fn();
    subscribeToEvents(late);

    // Without this replay a view mounted after connect would believe it has no
    // live updates and fall back to polling forever.
    expect(late).toHaveBeenCalledWith(expect.objectContaining({ type: '_open' }));
  });
});

describe('reconnection', () => {
  test('an unexpected close is retried', () => {
    setEventToken('tok-1');
    subscribeToEvents(() => {});
    FakeSocket.last.open();

    FakeSocket.last.close();
    expect(FakeSocket.instances).toHaveLength(1);

    jest.advanceTimersByTime(1000);
    expect(FakeSocket.instances).toHaveLength(2);
  });

  test('subscribers are told when the connection drops and returns', () => {
    const handler = jest.fn();
    setEventToken('tok-1');
    subscribeToEvents(handler);
    FakeSocket.last.open();
    expect(handler).toHaveBeenCalledWith(expect.objectContaining({ type: '_open' }));

    FakeSocket.last.close();
    expect(handler).toHaveBeenCalledWith(expect.objectContaining({ type: '_close' }));

    jest.advanceTimersByTime(1000);
    FakeSocket.last.open();
    expect(
      handler.mock.calls.filter(([e]) => e.type === '_open')
    ).toHaveLength(2);
  });

  test('repeated failures back off instead of hammering the server', () => {
    setEventToken('tok-1');
    subscribeToEvents(() => {});

    FakeSocket.last.close();
    jest.advanceTimersByTime(1000);
    expect(FakeSocket.instances).toHaveLength(2);

    FakeSocket.last.close();
    // The second retry waits longer than the first, so a down backend isn't
    // hit every second forever.
    jest.advanceTimersByTime(1000);
    expect(FakeSocket.instances).toHaveLength(2);
    jest.advanceTimersByTime(1000);
    expect(FakeSocket.instances).toHaveLength(3);
  });

  test('a deliberate teardown is not retried', () => {
    setEventToken('tok-1');
    const off = subscribeToEvents(() => {});
    FakeSocket.last.open();

    off();
    jest.advanceTimersByTime(60000);

    expect(FakeSocket.instances).toHaveLength(1);
  });
});
