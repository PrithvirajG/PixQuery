---
project: PixQuery
type: decision-note
created: 2026-08-27
status: planned
---

# ADR — Remote Access via Tailscale

**Date:** 2026-08-26
**Status:** Planned — approach chosen, not yet implemented.
**Related:** [[Cloud SaaS & On-Prem — Scope Exploration]]

## Context / Problem

The user wants to reach their locally-run PixQuery instance (frontend + API on their Windows PC) from outside their home network, securely.

## Decision

**Tailscale** (private WireGuard mesh VPN) — install on the PC and on the phone/laptop that needs access; the remote device gets a private IP that reaches the PC as if on the same LAN.

## Why not the alternatives

PixQuery watches folders on the user's PC — the server can't move off the machine without solving photo storage first (see [[Cloud SaaS & On-Prem — Scope Exploration]]). So this is a tunneling problem, not a deployment problem, which rules out "just deploy it to the cloud."

| Option | Verdict |
|---|---|
| **Tailscale** | **Chosen.** Free, zero public attack surface — nothing is ever listening on the open internet, so there's nothing to scan or brute-force. |
| Cloudflare Tunnel | Good runner-up if a plain shareable `https://` link matters (e.g. for someone without Tailscale installed). Still no open inbound port; can layer Cloudflare Access as a second auth gate in front of the app's own JWT login. |
| Router port-forward + DDNS + reverse proxy | Weakest option — directly exposes the home IP; many ISPs (mobile, some cable) block it outright via CGNAT anyway. |
| Cloud VPS deployment | Wrong tool — solves a different problem. The VPS wouldn't have access to the local photo folders PixQuery watches. |

## Follow-ups before wider exposure (not yet done)

- Update CORS `allow_origins` / `allow_origin_regex` in `backend/src/api/app.py` for the tunnel's origin.
- Consider switching the frontend from `npm start` (webpack-dev-server — not hardened for untrusted networks) to a production build served statically, before relying on this beyond casual personal use.
