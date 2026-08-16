---
project: PixQuery
type: decision-note
created: 2026-05-30
status: implemented
---

# ADR — Workspace Sharing, RBAC & Per-Workspace Processing

**Date:** 2026-05-30
**Status:** Implemented (Stages 1 & 2)
**Related:** [[Architecture Reality Map]] · [[Implementation Task Backlog]] · [[Current Implementation Audit]] · [[Processing and Search Flow.excalidraw|Processing & Search Flow]]
**Code-level reference:** `technical-requirement-doc.md` §10.1 (single source of truth for schema + mechanics).

> Note: This delivers part of what the [[Implementation Task Backlog]] deferred as "Phase 5–6 RBAC/teams." Workspace-level sharing with roles now exists; org-wide teams/tenancy remain future work.

## Context / Problem

The original model keyed an image **asset** on a globally-unique `content_sha256` and granted access through a single `owner_id` on that asset. Once a workspace could belong to — or be shared with — different people, two problems surfaced:

1. **No processing isolation.** Identical bytes in two workspaces produced *one* asset, *one* job, *one* set of outputs/vectors. A workspace "for me" and one "for someone else" would share derived data, and the dedup created a cross-tenant existence side-channel.
2. **First-writer-wins ownership bug.** `upsert_asset` set `owner_id` only if unset, while the asset was global-unique on `content_sha256`. Whoever ingested an image *first* owned it; a second user with the same bytes silently lost it from their owner-scoped listings/stats. This contradicted the "Partially implemented" user-isolation status noted in [[Architecture Reality Map]] §2.

## Decision

**The workspace is the unit of tenancy.** Access is by **workspace membership**, not by the asset's owner or by the acting user directly.

- **Sharing + RBAC.** `workspace_definitions.members[]` holds `{user_id, role, added_at}`; the creator is `owner`. Roles: **viewer** (read/search), **editor** (+ edit/scan), **owner** (+ manage members, delete). Invites are **immediate-grant** (no accept step) via username autocomplete; we chose this over a pending-invite handshake to match the "type → select → done" UX and keep scope small.
- **Per-workspace processing.** Asset identity becomes `(workspace_id, content_sha256)` and the job key includes `workspace_id`. The same image in two workspaces is processed and stored **twice**, independently. Dedup still applies *within* a workspace.

### Why workspace-level (not owner-level) tenancy

We considered keying isolation on `owner_id` (per-user). Rejected because **a workspace can be shared with multiple people** — owner-keying would reprocess a shared workspace once per member. Workspace-keying processes a shared workspace once (all members see it) while still isolating different workspaces. See the reasoning trail in `technical-requirement-doc.md` §10.1.1–10.1.3.

## Consequences

- **Access scoping** runs through three repo helpers — `accessible_workspace_ids`, `accessible_asset_ids`, `can_access_asset` — driven off `file_observations` (which always carried `workspace_id`). **Search needed no changes**; it already routed through `list_active_assets`.
- **No data migration required**: scoping via `file_observations` keeps legacy assets (without a `workspace_id` tag) visible.
- **Cascade delete** of a workspace removes its observations and any now-orphaned assets/jobs/outputs/runs — no reference counting. Orphaned Weaviate vectors are inert (semantic hits resolve back through Mongo and skip missing assets).
- **Operational:** restart backend processes after deploying so `ensure_indexes()` drops the old global-unique `content_sha256_1` index; a one-time re-scan splits pre-existing shared assets into per-workspace copies.
- **Fixes** the first-writer-wins bug (access no longer rides on the asset's `owner_id`).

## Scope delivered

- **Stage 1** — membership model, RBAC enforcement in `WorkspaceService`, member + `/user-search` endpoints, frontend `MembersModal` with debounced username autocomplete and role-gated controls.
- **Stage 2** — workspace-scoped asset/job uniqueness, reconciler + worker carry `workspace_id`, access scoping for images/stats/jobs, cascade delete, Weaviate `workspace_id` property.
- **Related fix** — RabbitMQ connections now retry with backoff (`RABBITMQ_CONNECT_TIMEOUT`), so process start order no longer crashes ingestion/worker.
- **Schema foundation (added 2026-05-30, after a DB reset)** — every collection is now a **Pydantic v2 model** in `backend/src/models/` (repo builds docs via `to_doc()`), and a lightweight **migration runner** (`backend/src/migrations/`, `schema_migrations` collection, `python -m src.migrations`, baseline = `0001_baseline`) versions schema changes going forward. `pydantic>=2.7` promoted to a core dependency. See `technical-requirement-doc.md` §10.2. Code-review fix #4 (member null-deref race) also applied.

## Known follow-ups (from code review)

- ~~`_member_view(None)` can 500 on a workspace-deleted-mid-call race.~~ **Fixed 2026-05-30** (add/remove member guard for `None` → 404).
- Narrow the `except Exception` in `_drop_index_if_exists` so a real index-drop failure isn't silently swallowed. *(Moot after the DB reset — no legacy index to drop — but still worth tightening.)*
- `can_access_asset` ignores observation `status` while listings require `active` — minor visibility inconsistency.
- Cache `accessible_asset_ids` per request (search invokes the scan twice).
