# PixQuery — Technical Requirements & Architecture

## 1. Introduction

### 1.1 Purpose

PixQuery is an AI-powered personal photo management system designed to run locally (self-hosted) or on-premise. It automatically ingests, analyses, and indexes images from watched folders using user-configured processing pipelines, then exposes a natural-language and vector search API over the indexed library. This document describes the current architecture following the pipeline and workspace refactor.

### 1.2 Scope

PixQuery provides:

- **Workspace management** — arbitrary watched directories, each independently configured with file-extension filters and one or more processing pipelines.
- **Pipeline system** — composable, sequential chains of AI nodes (object detection, captioning, CLIP embedding, CV ops, etc.) replacing the previous hardcoded `DefaultImageAnalysisPipeline`.
- **Multi-modal search** — keyword (caption/path substring), semantic (CLIP vector via Weaviate), and hybrid (merged + re-ranked) modes.
- **Shared workspaces with role-based access** — a workspace can be shared with other users (Viewer / Editor roles); the creator is the owner. Data visibility is scoped by **workspace membership**, not by a single `owner_id` (see §10.1).
- **Per-workspace processing isolation** — the same image content in two different workspaces is processed and stored independently, so workspaces shared with different people stay fully separated (see §10.1).
- **REST API + WebSocket** — FastAPI backend with JWT authentication.
- **React SPA** — dark glassmorphic UI built with Tailwind CSS.

### 1.3 Deployment Model

| Mode | Description |
|---|---|
| **Local** | Single user, single machine. MongoDB + RabbitMQ + Weaviate run in Docker Compose. Default mode. |
| **On-Premise** | Multi-user organisation deployment. Same Docker topology, multiple user accounts, `owner_id`-scoped queries. |
| **Multi-Tenant Cloud** | Deferred. Architectural scaffolding (owner scoping, JWT auth) is in place. |

---

## 2. System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  React SPA (Tailwind CSS)                                        │
│  Search · Pipeline Manager · Workspace Manager · Statistics      │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP + WebSocket
┌────────────────────────────▼────────────────────────────────────┐
│  FastAPI  (api_main.py)                                          │
│  /auth  /images  /jobs  /search                                  │
│  /pipeline-nodes  /pipelines  /workspaces  /stats               │
└───────┬──────────────┬──────────────────────────────────────────┘
        │              │
┌───────▼──────┐ ┌─────▼───────────────────────────────────────┐
│  MongoDB     │ │  RabbitMQ  (image_task queue)               │
│  pixquery db │ └─────────────────────────┬───────────────────┘
└───────┬──────┘                           │
        │                         ┌────────▼─────────────┐
        │                         │  Worker Process      │
        │                         │  (pipeline_worker_main.py)    │
        │                         │  Pipeline executor   │
        │                         └────────┬─────────────┘
        │                                  │
        │                         ┌────────▼─────────────┐
        │                         │  Weaviate            │
        │◄────── asset / job ─────│  (vector store)      │
        │        metadata         └──────────────────────┘
        │
┌───────▼─────────────────────────────────────────────────────────┐
│  Filesystem Watcher  (file_watcher_main.py)                        │
│  Reconciler — scans workspace paths, publishes jobs to RabbitMQ  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. MongoDB Schema

> **Source of truth:** every collection is defined as a **Pydantic v2 model** in `backend/src/models/` (`documents.py`). The repository builds documents via `Model(...).to_doc()` instead of hand-assembled dicts, so the shapes below are typed and validated in code, not just prose. Models are tolerant on read (`extra="ignore"`) so documents written under an older schema still parse; the `schema_migrations` collection (see §10.2) tracks applied migrations.

### 3.1 Existing Collections

**`image_assets`**
```
_id (uuid), content_sha256, workspace_id, mime_type, size_bytes
first_seen_at, latest_seen_at, active (bool), current_path, owner_id, metadata
```
> **Uniqueness is `(workspace_id, content_sha256)`** — assets are scoped per workspace, so identical bytes in two workspaces become two independent asset rows. (Prior schema enforced a single global-unique `content_sha256`; that index is dropped on startup — see §10.1.)

**`file_observations`**
```
_id (uuid), asset_id, watch_root_id, relative_path, absolute_path
content_sha256, status (active|missing), first_seen_at, last_seen_at, missing_since
```

**`processing_jobs`**
```
_id (uuid), workspace_id, asset_id, pipeline_id, pipeline_version, status (queued|processing|completed|failed)
attempt_count, next_attempt_at, last_error, created_at, updated_at
```
> **Uniqueness is `(workspace_id, asset_id, pipeline_id, pipeline_version)`** — one job per asset per pipeline version per workspace. Because `asset_id` is already per-workspace, every job, run, and output downstream inherits workspace isolation automatically.

**`pipeline_runs`** — one run record per job execution attempt

**`model_outputs`** — output payload per model per run (detections, captions, embeddings); tagged with `workspace_id`

**`users`** — username + hashed_password

### 3.2 New Collections

**`pipeline_nodes`** — the reusable node library (system-defined + user-defined)
```
_id (uuid), name, description, owner_id ("system" for built-ins), created_at
node_type: "object_detection" | "face_detection" | "segmentation" |
           "classification" | "captioning" | "embedding" |
           "grayscale" | "compress" | "crop" | "resize" | "draw_boxes" | ...
context_inputs:  ["image"]          # keys this node reads from context
context_outputs: ["detections"]     # keys this node writes to context
config_schema:   {...}              # JSON Schema for editable config fields
default_config:  {...}              # sensible defaults
```

**`pipeline_definitions`** — a named, ordered chain of pipeline nodes
```
_id (uuid), name, description, owner_id, created_at, updated_at
nodes: [
  {
    node_id:          uuid,          # unique within this pipeline
    pipeline_node_id: uuid,          # ref → pipeline_nodes._id
    order:            int,           # 0-indexed execution order (source of truth)
    config_overrides: {...},         # per-instance overrides of node default_config
    prev_node_id:     uuid | null,   # doubly-linked list for fast UI traversal
    next_node_id:     uuid | null,
  }, ...
]
```

**`workspace_definitions`** — watched folder + pipeline assignment + sharing
```
_id (uuid), name, workspace_path (abs path), owner_id
active (bool), pipeline_ids [str], extensions [str], created_at
members: [
  { user_id: uuid, role: "viewer" | "editor", added_at: datetime }, ...
]
```
> `owner_id` is the creator (implicit `owner` role). `members` holds users the workspace is shared with. A user can access a workspace if they are the owner or appear in `members` — this is the basis of all data-visibility scoping (see §10.1).

---

## 4. Pipeline Execution Model

Nodes execute **strictly sequentially**. Each node receives the accumulated **context object** from all preceding nodes and appends its own output keys.

```
image → [Node 0: Object Detection]  → { image, detections }
      → [Node 1: Captioning]        → { image, detections, caption }
      → [Node 2: CLIP Embed]        → { image, detections, caption, embeddings }
      → Storage (Weaviate + MongoDB)
```

Each `pipeline_node` declares:
- `context_inputs` — keys it reads from context (e.g. `["image", "detections"]`)
- `context_outputs` — keys it adds (e.g. `["image"]` for CV ops, `["caption"]` for BLIP)

The Pipeline Manager UI validates chain compatibility: if a node's required `context_inputs` key is not yet produced by any preceding node, a red warning badge is shown.

---

## 5. API Reference

### Authentication
| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/register` | Create account |
| POST | `/auth/login` | Obtain JWT |
| GET | `/auth/me` | Current user info |

### Images
| Method | Path | Description |
|--------|------|-------------|
| GET | `/images` | List active image assets |
| GET | `/images/{id}` | Get image asset |
| GET | `/images/{id}/thumbnail` | Serve image file |

### Search
| Method | Path | Description |
|--------|------|-------------|
| GET | `/search` | Search with `?query=&mode=keyword\|semantic\|hybrid&top_k=&threshold=&workspace_id=` |

### Pipeline Nodes
| Method | Path | Description |
|--------|------|-------------|
| GET | `/pipeline-nodes` | List all nodes (system + user) |
| POST | `/pipeline-nodes` | Create custom node |
| PUT | `/pipeline-nodes/{id}` | Update user node |
| DELETE | `/pipeline-nodes/{id}` | Delete user node |

### Pipelines
| Method | Path | Description |
|--------|------|-------------|
| GET | `/pipelines` | List user's pipelines |
| POST | `/pipelines` | Create pipeline |
| GET | `/pipelines/{id}` | Get pipeline with nodes |
| PUT | `/pipelines/{id}` | Update pipeline |
| DELETE | `/pipelines/{id}` | Delete pipeline |

### Workspaces
| Method | Path | Description |
|--------|------|-------------|
| GET | `/workspaces` | List user's workspaces |
| POST | `/workspaces` | Create workspace |
| GET | `/workspaces/{id}` | Get workspace |
| PUT | `/workspaces/{id}` | Update workspace (owner/editor) |
| DELETE | `/workspaces/{id}` | Delete workspace + cascade its data (owner only) |
| POST | `/workspaces/{id}/scan` | Trigger immediate reconcile (owner/editor) |
| GET | `/workspaces/{id}/user-search?q=` | Username prefix autocomplete for invites (owner only); excludes self + existing members |
| GET | `/workspaces/{id}/members` | List members with roles |
| POST | `/workspaces/{id}/members` | Add member `{username, role}` (owner only) |
| PATCH | `/workspaces/{id}/members/{user_id}` | Change a member's role (owner only) |
| DELETE | `/workspaces/{id}/members/{user_id}` | Revoke access (owner only) |

> Role enforcement: `403` when the caller lacks the required role, `400` on invalid input (unknown username, bad role, inviting the owner), `404` when the workspace is not visible to the caller.

### Jobs
| Method | Path | Description |
|--------|------|-------------|
| GET | `/jobs` | List jobs (optional `?status=`) |
| POST | `/jobs/{id}/requeue` | Requeue failed job |

### Statistics
| Method | Path | Description |
|--------|------|-------------|
| GET | `/stats/overview` | Aggregated counts per user |
| GET | `/stats/jobs/recent` | Last N jobs (`?limit=50`) |

### Status / WebSocket
| Method | Path | Description |
|--------|------|-------------|
| GET | `/status` | Health check |
| WS | `/ws` | Real-time job status updates |

---

## 6. Service Layer

| Service | Responsibilities |
|---------|-----------------|
| `ImageService` | List / retrieve image assets |
| `JobService` | List jobs, requeue via RabbitMQ |
| `SearchService` | Keyword / semantic / hybrid search; workspace-scoped filtering |
| `PipelineService` | CRUD for pipeline nodes and pipeline definitions; builds doubly-linked node chain |
| `WorkspaceService` | CRUD for workspace definitions; **RBAC enforcement** (owner/editor/viewer); member add/remove/role + username search |
| `StatsService` | Aggregate counts + recent jobs (scoped to the caller's accessible workspaces) |

---

## 7. Frontend Views

All views share the **dark glassmorphic theme**: `bg-slate-950` base, violet/blue gradient accents, `bg-slate-900/60 backdrop-blur border-slate-800` glass cards, pure Tailwind CSS (no MUI components in new views).

### 7.1 Search View (`ImageQueryView.js`)
- Full-width search bar with violet glow on focus
- Collapsible **Advanced Options** glass panel:
  - Mode selector: Keyword / Semantic / Hybrid
  - Confidence threshold slider (active for semantic/hybrid only)
  - Workspace filter dropdown
  - Top-K result count stepper
- Responsive masonry-style result grid of `ImageCard` components

### 7.2 Pipeline Manager (`ModelManagementView.js`)
- **Two tabs**: Pipelines | Node Library
- **Pipelines tab** — two-panel layout:
  - Left panel (`w-72`): pipeline list + "New Pipeline" button
  - Right panel: in-place name/description edit, sequential node chain editor
    - Node cards with category badges (color-coded by type)
    - Context key flow shown between nodes (`in: image → out: detections`)
    - Compatibility validation: red warning badge if required context key is missing
    - Move up/down buttons, edit config icon, delete icon
    - "Add Node" modal with search, grouped by type
    - Config drawer (JSON override editor)
- **Node Library tab**: grid of all nodes with create / delete for user-owned nodes

### 7.3 Workspace Manager (`ImageUploadView.js`)
- Card grid; active workspaces have violet top-border glow
- Each card shows: name, path, status badge, **role badge** (for shared workspaces where you are not the owner), linked pipeline chips, extensions, Scan Now button
- **Role-gated controls**: viewers see no edit/scan/delete; editors can edit + scan; only the owner sees delete and member management
- Create/Edit right-side drawer with blurred backdrop:
  - Name, directory path, extension multi-select, pipeline multi-select, active toggle
- **Members modal** (people icon on each card):
  - Owner-only invite box: debounced **username autocomplete** (`/user-search`) with a suggestions dropdown and a Viewer/Editor role selector; selecting a suggestion grants access immediately
  - Member list with inline role change (Viewer/Editor) and a revoke (✕) button; the owner row is read-only
  - Visible read-only to members; management controls render only for the owner

### 7.4 Statistics View (`ProgressTrackingView.js`)
- **Stat cards row**: Total Images | Active Workspaces | Pipelines Defined | Jobs Completed | Jobs Failed | Processing Now
- **Recent Jobs table**: sortable by status / updated_at; status pills (violet=processing, green=completed, red=failed, slate=queued); Requeue button on failed rows
- Auto-refreshes every 15 s while jobs are active

---

## 8. Infrastructure

### 8.1 Docker Services

| Service | Image | Default Port |
|---------|-------|-------------|
| MongoDB | `mongo:7` | 27017 |
| RabbitMQ | `rabbitmq:3-management` | 5672 / 15672 |
| Weaviate | `semitechnologies/weaviate` | 8080 |

`docker-compose.infra.yml` starts the above three services for local development.  
`docker-compose.yml` adds the API, worker, and monitor processes.

### 8.2 Backend Processes

| Entry Point | Role |
|-------------|------|
| `api_main.py` | FastAPI HTTP server (uvicorn) |
| `pipeline_worker_main.py` | RabbitMQ consumer; executes pipeline nodes per job |
| `file_watcher_main.py` | Filesystem watcher + reconciler; publishes jobs |

### 8.3 Configuration (Environment Variables)

| Variable | Default | Description |
|----------|---------|-------------|
| `MONGO_URI` | `mongodb://localhost:27017` | MongoDB connection string |
| `MONGO_DB_NAME` | `pixquery` | Database name |
| `RABBITMQ_URL` | `amqp://guest:guest@localhost/` | RabbitMQ AMQP URL |
| `RABBITMQ_QUEUE` | `image_task` | Queue name |
| `RABBITMQ_CONNECT_TIMEOUT` | `60` | Seconds to retry broker connection on startup before giving up (§10.1.7) |
| `RUN_MIGRATIONS_ON_STARTUP` | `true` | Apply pending DB migrations when the API starts; set `false` to run `python -m src.migrations` explicitly (§10.2) |
| `WEAVIATE_URL` | `http://localhost:8080` | Weaviate REST base URL |
| `WATCH_ROOT` | `~/pixquery_photos` | Legacy default watch path (superseded by workspaces) |
| `WATCH_ROOT_ID` | `default` | Legacy watch root identifier |
| `SECRET_KEY` | — | JWT signing secret (required in production) |

---

## 9. Search Modes

| Mode | Implementation |
|------|---------------|
| `keyword` | Substring match on `current_path` + caption text from `model_outputs` |
| `semantic` | CLIP text → vector, searched against Weaviate `ImageEmbedding` class; falls back to keyword if CLIP unavailable |
| `hybrid` | Keyword results + deduplicated semantic results, merged list re-ranked by score, trimmed to `top_k` |

Optional parameters: `threshold` (minimum score, only meaningful for semantic/hybrid), `workspace_id` (filters assets by `watch_root_id` from `file_observations`).

---

## 10. Security

- JWT-based authentication (`python-jose` + `bcrypt` password hashing)
- All API routes except `/auth/register` and `/auth/login` require a valid Bearer token
- **Workspace-membership scoping** on data operations: a user can only read assets/jobs/stats for workspaces they own or are a member of, and only the owner can manage membership or delete a workspace (see §10.1). This replaces the earlier single-`owner_id`-per-asset model.
- CORS origin currently set to `http://localhost:3000`; update `allow_origins` in `app.py` for production

---

## 10.1 Access Control, Sharing & Workspace-Scoped Processing (2026 refactor)

This section documents the multi-tenancy refactor in detail: the problem, the model we chose, the mechanics, and the migration consequences.

### 10.1.1 Motivation

The original design keyed an image **asset** on a globally-unique `content_sha256` and granted access via a single `owner_id` on that asset. Two problems followed once workspaces could belong to (or be shared with) different people:

1. **No processing isolation.** Identical bytes in two workspaces produced *one* asset, *one* job, and *one* set of outputs/vectors. A workspace meant "for me" and another meant "for someone else" would share derived data. The dedup also created a cross-tenant existence side-channel (a second uploader's job completing instantly reveals the content already exists).
2. **First-writer-wins ownership bug.** `upsert_asset` set `owner_id` only if not already set, and the asset was global-unique on `content_sha256`. So whoever ingested a given image *first* owned it; a second user with the same bytes silently lost it from their owner-scoped listings/stats.

**Requirement that fixed the design:** a workspace can be **shared with multiple people**, and the same image in two *different* workspaces must be processed and stored twice. Therefore the unit of isolation is the **workspace**, and access is **workspace membership** — not the user, and not the asset's owner.

### 10.1.2 Membership & RBAC model

`workspace_definitions.members[]` holds `{user_id, role, added_at}`; the creator is tracked by `owner_id` with the implicit `owner` role. Roles:

| Capability | Owner | Editor | Viewer |
|---|---|---|---|
| View / search images in the workspace | ✅ | ✅ | ✅ |
| Edit workspace settings + pipelines, trigger scans | ✅ | ✅ | ❌ |
| Add / remove members, change roles, delete workspace | ✅ | ❌ | ❌ |

Enforcement lives in `WorkspaceService` (`role_for()` + `_can_view/_can_edit/_can_manage`). Invites are **immediate-grant** (no accept step): the owner types a username, the `/user-search` endpoint suggests matches (case-insensitive prefix, excluding self and existing members), and selecting one adds the member right away.

### 10.1.3 Per-workspace processing & dedup

Asset identity changed from `content_sha256` to **`(workspace_id, content_sha256)`**, and the job key includes `workspace_id`. The cascade is automatic:

```
same bytes in workspace A and workspace B
        │
        ├─ upsert_asset(workspace_id=A) → asset Aʹ   (distinct _id)
        └─ upsert_asset(workspace_id=B) → asset Bʹ   (distinct _id)
                │                                │
        ensure_processing_job(Aʹ)        ensure_processing_job(Bʹ)   → two jobs
                │                                │
        model_outputs + Weaviate(Aʹ)     model_outputs + Weaviate(Bʹ) → two of everything
```

Within a single workspace, dedup still holds: the same content at two paths, or a re-scan, resolves to one asset (the `(workspace_id, content_sha256)` lookup) and one job per pipeline version. Editing a pipeline changes its `pipeline_version` hash, which creates a fresh job and reprocesses — unchanged from before.

### 10.1.4 Access-scoping mechanics

Three repository helpers replace `owner_id`-based filtering:

- `accessible_workspace_ids(user_id)` — workspaces owned or joined (`list_workspaces` now returns owner **or** member via `{$or: [{owner_id}, {members.user_id}]}`).
- `accessible_asset_ids(user_id)` — asset IDs that have an **active `file_observation`** in an accessible workspace. Driving access off `file_observations` (which always carried `workspace_id`) means **no data migration is required** — legacy assets without a `workspace_id` tag stay visible.
- `can_access_asset(user_id, asset_id)` — single-asset gate for `/images/{id}`.

These feed `list_active_assets`, `ImageService.get_image`, `get_stats_overview`, and `list_recent_jobs`. **Search needed no changes** — it already routed through `list_active_assets` / `_allowed_asset_ids`.

### 10.1.5 Cascade delete

Deleting a workspace removes its `file_observations`, then any asset left with no observation in another workspace — along with that asset's jobs, `model_outputs`, and `pipeline_runs`. Because everything keys on a per-workspace `asset_id`, this is a clean cascade with **no reference counting**. Orphaned Weaviate vectors are intentionally left: semantic search resolves each hit back through MongoDB and skips assets that no longer exist, so stale vectors are inert (a future enhancement could prune them).

### 10.1.6 Migration & operational notes

- **Restart all backend processes after deploying.** `ensure_indexes()` runs on repository init and is what **drops the old global-unique `content_sha256_1` index** and creates the compound `(workspace_id, content_sha256)` index. Until the old index is gone, a second workspace's identical content would be rejected by the surviving uniqueness constraint.
- **One-time reprocessing wave.** Pre-existing assets/jobs lack `workspace_id`. A re-scan creates per-workspace assets (the `(workspace_id, sha)` lookup won't match the legacy `workspace_id: null` row) and new jobs, so each affected image is reprocessed once into its workspace-scoped form. Legacy rows become inert and are removed when their workspace is deleted.
- **Weaviate** `ImageEmbedding` / `TextEmbedding` classes gained a declared `workspace_id` property; access is still enforced Mongo-side via `accessible_asset_ids`, so this is forward-looking metadata rather than the access boundary.

### 10.1.7 RabbitMQ startup resilience (related fix)

The ingestion/worker processes previously crashed if started before RabbitMQ finished booting (`AMQPConnectionError: Server connection unexpectedly closed`). Connections now retry with exponential backoff (`_connect_with_retry`, 1 s → 5 s cap) up to `RABBITMQ_CONNECT_TIMEOUT` (default 60 s), so process start order no longer matters.

---

## 10.2 Database Models & Migrations

Introduced alongside the access-control refactor to make the schema explicit and evolvable.

### 10.2.1 Pydantic document models (`backend/src/models/`)

Every collection has a Pydantic v2 model (`User`, `ImageAsset`, `FileObservation`, `ProcessingJob`, `PipelineRun`, `ModelOutput`, `WorkspaceDefinition` + embedded `WorkspaceMember`, `PipelineNode`, `PipelineDefinition`). All top-level documents extend `BaseDocument`, which maps `id ↔ _id` and exposes `to_doc()` (dumps with the `_id` alias). The repository constructs documents from these models, replacing ~10 inline dict literals — so field names, defaults, and types live in one validated place. Models are intentionally `extra="ignore"` on read so legacy documents still load.

> Dependency note: `pydantic>=2.7` is now a **core** dependency (was only transitively present via FastAPI). It's been added to `pyproject.toml` `[project.dependencies]` and to `requirements.txt` / `requirements.pipeline-worker.txt` / `requirements.file-watcher.txt`, because the worker and monitor import the repository and therefore the models.

### 10.2.2 Migration runner (`backend/src/migrations/`)

A lightweight, dependency-free runner:

- **`schema_migrations` collection** records applied migration ids (`{_id, description, applied_at}`).
- **`MIGRATIONS`** is an append-only, ordered list of `Migration(id, description, upgrade)`; `run_migrations(db)` applies any not yet recorded, in order, exactly once.
- **`0001_baseline`** establishes the current schema by instantiating the repository (which idempotently creates indexes — including the workspace-scoped ones and the legacy-index drop — and seeds system nodes), so index definitions stay in one place.

**Running migrations**
```bash
python -m src.migrations            # apply pending migrations
python -m src.migrations --status   # list applied / pending
```
By default the API also applies pending migrations on startup (`RUN_MIGRATIONS_ON_STARTUP=true`); set it to `false` to run them only as an explicit deploy step.

**Adding a migration:** append a new `Migration("0002_…", "…", upgrade_fn)` to `MIGRATIONS`; never edit or reorder a released one. `upgrade(db)` receives the raw database handle and performs the data/schema transformation (e.g. add + backfill a field).

---

## 11. Technical Requirements

### Hardware
| Tier | Spec |
|------|------|
| Minimum | 8 GB RAM, x86-64 CPU, 20 GB storage |
| Recommended | 16 GB RAM, NVIDIA GPU (6 GB+ VRAM) for model inference |

### Software
- Python 3.11+
- Node.js 18+ (frontend)
- Docker & Docker Compose (infrastructure)

### Performance Targets
| Metric | Target |
|--------|--------|
| Image indexing throughput | ≥ 1 image/s (GPU), ≥ 0.2 image/s (CPU) |
| Search latency (keyword) | < 500 ms for 50 k assets |
| Search latency (semantic) | < 2 s for 50 k embeddings |
| API p95 response time | < 200 ms (non-search endpoints) |

---

## 12. Development Commands

```bash
# Infrastructure (MongoDB, RabbitMQ, Weaviate)
docker compose -f docker-compose.infra.yml up -d

# Database migrations (idempotent; API also auto-runs these on startup)
cd backend && python -m src.migrations

# Backend API
cd backend && pip install -r requirements.txt
uvicorn api_main:app --reload --port 8000

# Worker
cd backend && python pipeline_worker_main.py

# Filesystem monitor
cd backend && python file_watcher_main.py

# Frontend
cd frontend && npm install && npm start

# Tests
cd backend && python -m unittest discover tests
cd frontend && npm test
```

---

## 13. Future Enhancements

- **Multi-tenant cloud** — tenant isolation, S3/GCS asset storage, horizontal worker scaling
- **Video support** — keyframe extraction, per-frame pipeline execution
- **Custom model upload** — user-uploadable ONNX/TorchScript models registered as pipeline node types
- **Anomaly detection** — threshold-based alerting for CCTV / monitoring workspaces
- **Pipeline versioning** — immutable pipeline snapshots linked to job history for reproducibility
- **Human-in-the-loop feedback** — caption / detection correction stored back to `model_outputs`
