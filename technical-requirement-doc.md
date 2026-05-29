# PixQuery — Technical Requirements & Architecture

## 1. Introduction

### 1.1 Purpose

PixQuery is an AI-powered personal photo management system designed to run locally (self-hosted) or on-premise. It automatically ingests, analyses, and indexes images from watched folders using user-configured processing pipelines, then exposes a natural-language and vector search API over the indexed library. This document describes the current architecture following the pipeline and workspace refactor.

### 1.2 Scope

PixQuery provides:

- **Workspace management** — arbitrary watched directories, each independently configured with file-extension filters and one or more processing pipelines.
- **Pipeline system** — composable, sequential chains of AI nodes (object detection, captioning, CLIP embedding, CV ops, etc.) replacing the previous hardcoded `DefaultImageAnalysisPipeline`.
- **Multi-modal search** — keyword (caption/path substring), semantic (CLIP vector via Weaviate), and hybrid (merged + re-ranked) modes.
- **Per-user data isolation** — all collections are scoped by `owner_id`.
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
        │                         │  (worker_main.py)    │
        │                         │  Pipeline executor   │
        │                         └────────┬─────────────┘
        │                                  │
        │                         ┌────────▼─────────────┐
        │                         │  Weaviate            │
        │◄────── asset / job ─────│  (vector store)      │
        │        metadata         └──────────────────────┘
        │
┌───────▼─────────────────────────────────────────────────────────┐
│  Filesystem Watcher  (monitoring_main.py)                        │
│  Reconciler — scans workspace paths, publishes jobs to RabbitMQ  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. MongoDB Schema

### 3.1 Existing Collections

**`image_assets`**
```
_id (uuid), content_sha256 (unique), mime_type, size_bytes
first_seen_at, latest_seen_at, active (bool), current_path, owner_id, metadata
```

**`file_observations`**
```
_id (uuid), asset_id, watch_root_id, relative_path, absolute_path
content_sha256, status (active|missing), first_seen_at, last_seen_at, missing_since
```

**`processing_jobs`**
```
_id (uuid), asset_id, pipeline_id, pipeline_version, status (queued|processing|completed|failed)
attempt_count, next_attempt_at, last_error, created_at, updated_at
```

**`pipeline_runs`** — one run record per job execution attempt

**`model_outputs`** — output payload per model per run (detections, captions, embeddings)

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

**`workspace_definitions`** — watched folder + pipeline assignment
```
_id (uuid), name, watch_root (abs path), watch_root_id (uuid), owner_id
active (bool), pipeline_ids [str], extensions [str], created_at
```

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
| PUT | `/workspaces/{id}` | Update workspace |
| DELETE | `/workspaces/{id}` | Delete workspace |
| POST | `/workspaces/{id}/scan` | Trigger immediate reconcile |

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
| `WorkspaceService` | CRUD for workspace definitions |
| `StatsService` | Aggregate counts + recent jobs |

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
- Each card shows: name, path, status badge, linked pipeline chips, extensions, Scan Now button
- Create/Edit right-side drawer with blurred backdrop:
  - Name, directory path, extension multi-select, pipeline multi-select, active toggle

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
| `worker_main.py` | RabbitMQ consumer; executes pipeline nodes per job |
| `monitoring_main.py` | Filesystem watcher + reconciler; publishes jobs |

### 8.3 Configuration (Environment Variables)

| Variable | Default | Description |
|----------|---------|-------------|
| `MONGO_URI` | `mongodb://localhost:27017` | MongoDB connection string |
| `MONGO_DB_NAME` | `pixquery` | Database name |
| `RABBITMQ_URL` | `amqp://guest:guest@localhost/` | RabbitMQ AMQP URL |
| `RABBITMQ_QUEUE` | `image_task` | Queue name |
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
- `owner_id` scoping on all query/mutation operations (users can only read/write their own data)
- CORS origin currently set to `http://localhost:3000`; update `allow_origins` in `app.py` for production

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

# Backend API
cd backend && pip install -r requirements.txt
uvicorn api_main:app --reload --port 8000

# Worker
cd backend && python worker_main.py

# Filesystem monitor
cd backend && python monitoring_main.py

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
