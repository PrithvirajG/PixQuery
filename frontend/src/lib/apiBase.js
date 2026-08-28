// Single source of truth for the backend's base URL.
//
// Computed from window.location.hostname rather than hardcoded, so the same
// build works whether the page was loaded via localhost, a LAN IP, or (later)
// a real domain — the browser always calls back the host it was served from.
export const API_BASE = `http://${window.location.hostname}:8000`;

// Same host, WebSocket scheme — derived from API_BASE so the two can never drift.
export const WS_BASE = API_BASE.replace(/^http/, 'ws');
