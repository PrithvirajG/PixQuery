// Live event stream from the backend.
//
// One WebSocket for the whole app, not one per component: several views can care
// about pipeline progress at once, and a socket per subscriber would multiply
// connections (and reconnect storms) for no benefit. Components subscribe to the
// shared stream and filter locally.
//
// The socket carries *notifications*, never data. An event says which
// (image, pipeline) pair changed and to what state; subscribers refetch through
// the normal REST endpoints to get the substance. That keeps one authorization
// path and one serialization path, and makes a dropped connection cost latency
// rather than correctness — see backend `src/events.py`.

import { WS_BASE } from './apiBase';

// Backoff for reconnects: quick at first (a dev-server restart is usually back in
// a second) then backing off so a genuinely-down backend isn't hammered.
const RETRY_DELAYS = [1000, 2000, 5000, 10000, 30000];

let socket = null;
let token = null;
let retry = 0;
let reconnectTimer = null;
let closedByUs = false;
const subscribers = new Set();

function notify(event) {
  subscribers.forEach((fn) => {
    try {
      fn(event);
    } catch (err) {
      // One bad subscriber must not stop the others from seeing the event.
      console.error('Event subscriber threw', err);
    }
  });
}

function scheduleReconnect() {
  if (closedByUs || reconnectTimer || !subscribers.size) return;
  const delay = RETRY_DELAYS[Math.min(retry, RETRY_DELAYS.length - 1)];
  retry += 1;
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    open();
  }, delay);
}

function open() {
  if (!token || socket) return;
  // The browser WebSocket API can't send an Authorization header, so the JWT
  // travels as a query parameter over the same connection the REST API uses.
  const ws = new WebSocket(`${WS_BASE}/ws/events?token=${encodeURIComponent(token)}`);
  socket = ws;

  ws.onopen = () => {
    retry = 0;
    notify({ type: '_open', data: {} });
  };

  ws.onmessage = (message) => {
    let event;
    try {
      event = JSON.parse(message.data);
    } catch {
      return;
    }
    // Keepalives and the connect handshake are transport chatter, not domain events.
    if (event.type === 'ping' || event.type === 'ready') return;
    notify(event);
  };

  ws.onclose = () => {
    socket = null;
    notify({ type: '_close', data: {} });
    scheduleReconnect();
  };

  // 'error' is always followed by 'close', which owns the reconnect — so this
  // handler exists only to keep the failure from surfacing as an unhandled event.
  ws.onerror = () => {};
}

/** Point the shared socket at a (new) auth token, reconnecting if it changed. */
export function setEventToken(next) {
  if (next === token) return;
  token = next;
  closedByUs = false;
  if (socket) {
    const old = socket;
    socket = null;
    old.onclose = null;
    old.close();
  }
  if (token && subscribers.size) open();
}

/**
 * Subscribe to live events. Returns an unsubscribe function.
 *
 * The connection is opened on the first subscriber and closed when the last one
 * leaves, so a logged-in user idling on a static page holds no socket.
 */
export function subscribeToEvents(handler) {
  subscribers.add(handler);
  closedByUs = false;
  if (token && !socket) {
    open();
  } else if (socket && socket.readyState === WebSocket.OPEN) {
    // The connection predates this subscriber, so it already missed the '_open'
    // that tells it we're live. Replay one — otherwise a view mounted after the
    // socket connected would sit there believing it has no live updates.
    try {
      handler({ type: '_open', data: {} });
    } catch (err) {
      console.error('Event subscriber threw', err);
    }
  }
  return () => {
    subscribers.delete(handler);
    if (!subscribers.size) {
      closedByUs = true;
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
      if (socket) {
        const old = socket;
        socket = null;
        old.onclose = null;
        old.close();
      }
    }
  };
}

/** Test seam: drop all state so each test starts from a clean socket. */
export function __resetEventSocket() {
  subscribers.clear();
  if (reconnectTimer) clearTimeout(reconnectTimer);
  reconnectTimer = null;
  if (socket) {
    const old = socket;
    socket = null;
    old.onclose = null;
    old.close();
  }
  token = null;
  retry = 0;
  closedByUs = false;
}
