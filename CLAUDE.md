# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

PixQuery is an AI-powered local photo management system. It ingests images from watched directories, runs them through configurable AI pipelines (object detection, captioning, CLIP embedding), stores results in MongoDB + Weaviate, and exposes a natural-language/vector search API consumed by a React SPA.

## Commands

### Infrastructure (required before running backend)
```bash
docker compose -f docker-compose.infra.yml up -d   # MongoDB:27017, RabbitMQ:5672/15672, Weaviate:8080
```

### Backend
```bash
cd backend && pip install -r requirements.txt       # or: pip install -e ".[api,worker,monitor]"
cd backend && uvicorn api_main:app --reload --port 8000   # API server
cd backend && python worker_main.py                 # RabbitMQ consumer / pipeline executor
cd backend && python monitoring_main.py             # filesystem watcher + reconciler
cd backend && python -m src.migrations              # run pending DB migrations manually
```

### Tests
```bash
cd backend && python -m unittest discover tests     # all backend tests
cd backend && python -m unittest tests.test_dynamic_pipeline   # single test file
cd frontend && npm test                             # Jest / React Testing Library
```

### Frontend
```bash
cd frontend && npm install
cd frontend && npm start                            # dev server at http://localhost:3000
cd frontend && npm run build:css                    # regenerate src/output.css from Tailwind
cd frontend && npm run build                        # production build
```

## Architecture

Three independent backend processes communicate through MongoDB and RabbitMQ:

```
monitoring_main.py  →  RabbitMQ (image_task queue)  →  worker_main.py
        ↓                                                      ↓
    MongoDB                                              Weaviate (vectors)
        ↑
  api_main.py  ←→  React SPA (frontend/)
```

- **`api_main.py`** — FastAPI HTTP/WebSocket server. Entry point calls `src.api.create_app()`.
- **`worker_main.py`** — Consumes `image_task` messages; runs `DynamicPipeline` via `src/pipelines/processing/`.
- **`monitoring_main.py`** — Polls workspace definitions from MongoDB, watches filesystem paths, publishes jobs via `FilesystemReconciler`.

### Backend source layout (`backend/src/`)

| Package | Responsibility |
|---|---|
| `api/routes/` | FastAPI route handlers: `auth`, `images`, `jobs`, `search`, `stats`, `status`, `workspaces`, `pipelines`, `pipeline_nodes` |
| `api/security.py` | JWT creation/verification, bcrypt password hashing |
| `api/dependencies.py` | FastAPI dependency injection (DB, current user, services) |
| `services/` | Business logic — `ImageService`, `JobService`, `SearchService`, `PipelineService`, `WorkspaceService`, `StatsService` |
| `models/documents.py` | Pydantic v2 document models — one class per MongoDB collection; **source of truth for schema**. Persist via `Model(...).to_doc()` |
| `migrations/runner.py` | Versioned schema migrations — `run_migrations()`, ordered `MIGRATIONS` list, `schema_migrations` collection |
| `repositories/` | Data access — `mongo_pipeline.py` (production), `memory_pipeline.py` (tests) |
| `pipelines/processing/pipeline.py` | `DynamicPipeline` (active) — DAG executor; `DefaultImageAnalysisPipeline` is retained for legacy compat only |
| `pipelines/processing/executors/` | `registry.py` maps `node_type` strings → cached `BaseNodeExecutor` subclasses; `builtin.py` has implementations for `object_detection`, `face_detection`, `classification`, `captioning`, `embedding`, `resize`, `grayscale`, `image_write`, `ocr` |
| `pipelines/ingestion/` | `FilesystemReconciler` (per-workspace hash dedup, job dispatch), `watcher.py` |
| `infrastructure/messaging/` | RabbitMQ publish/consume via `aio-pika` |
| `infrastructure/vector_store/` | Weaviate upsert/search |
| `config.py` | All env-var defaults in one place |

### Key data flow

1. `monitoring_main.py` scans workspace paths, calls `FilesystemReconciler.reconcile()`.
2. Reconciler computes SHA-256 of each file, upserts `image_assets` + `file_observations` in MongoDB, creates `processing_jobs`, publishes job IDs to RabbitMQ.
3. `worker_main.py` picks up job ID, loads the asset, runs each `ResolvedNode` in the pipeline through its registered executor, stores outputs in `model_outputs`, upserts vectors to Weaviate, marks job `completed`.
4. `api_main.py` serves assets/search/stats to the React frontend. Search supports `keyword` (MongoDB substring), `semantic` (Weaviate vector), and `hybrid` (merged + re-ranked) modes.

**Processing is workspace-scoped.** Assets are unique on `(workspace_id, content_sha256)` and jobs on `(workspace_id, asset_id, pipeline_id, pipeline_version)` — the same image in two workspaces is processed and stored twice, independently. Dedup applies only *within* a workspace.

**DynamicPipeline executor model.** A `PipelineDefinition` is a DAG: `nodes` (vertices, each a `{node_id, pipeline_node_id, config_overrides, position}`) plus `edges` (`{edge_id, from_node_id, to_node_id, from_output?, to_input?}`), built by `PipelineService._build_graph`. A definition with no stored `edges` is treated as a straight chain (`_linear_edges`). `DynamicPipeline._run_graph` topologically sorts the graph (Kahn's algorithm, raises on cycles/unknown edge refs) and runs each node once: with no port mapping a node inherits its parent's full context (so a straight chain threads `image` through unchanged); `from_output`/`to_input` pulls a single named value, used to disambiguate fan-in. Each node gets its own context copy, so divergent branches don't clobber each other; the final context is merged in topological order (last write wins). Executors are resolved via `get_executor(node_type)` from the registry; `_PERSIST_SKIP_KEYS = {"image", "asset", "embeddings", "text_embedding"}` are working state and are not written to `model_outputs`. To add a new node type: create a `BaseNodeExecutor` subclass in `builtin.py` and register it in `_EXECUTOR_CLASSES` in `registry.py`. Metadata extraction (EXIF/GPS/dimensions) is **not** a node — it's driven by `PipelineDefinition.extract_metadata` and read from the original file regardless of node order (`DynamicPipeline._maybe_extract_metadata`).

### Frontend (`frontend/src/`)

React 19 SPA with React Router, Tailwind CSS, and MUI. `App.js` renders `LandingPage` when logged out or `AppShell` (nav rail: Gallery/Control Room groups) wrapping the routed views when logged in; auth state lives in `context/AuthContext.js` (injects the Bearer token, base URL `http://localhost:8000`). Views (older ones have a **component export name that differs from the filename**; newer views export a matching name):
- `views/SearchView.js` (exports `ImageQueryView`) — search with mode/threshold/workspace/top-K controls (`/search`)
- `views/PipelinesView.js` (exports `ModelManagementView`) — pipeline + node library management, including `PipelineGraphCanvas` for editing the DAG (`/pipelines`)
- `views/WorkspacesView.js` (exports `ImageUploadView`) — workspace CRUD + **sharing**: a `MembersModal` with debounced username autocomplete (`/workspaces/{id}/user-search`), role assignment (Viewer/Editor), and role-gated card controls (`/workspaces`)
- `views/WorkspaceDetailView.js` — single workspace detail (`/workspaces/:id`)
- `views/PipelineStatsView.js` — per-pipeline run stats for a workspace (`/workspaces/:id/pipelines/:pipelineId/stats`)
- `views/JobsView.js` (exports `ProgressTrackingView`) — statistics + recent jobs table (`/jobs`)
- `pages/ImageDetails.js` — single-image detail with detection overlay (`/image/:id`)
- `pages/LandingPage.js` — unauthenticated login/register landing

Design system: **Aperture** (`aperture/tokens.js` — `AP` color/type tokens, `STATUS` palette; `aperture/kit.js` — shared primitives like `Dot`, `Kbd`, `ApertureMark`, icons; `aperture/aperture.css`). Dark carbon canvas with a violet/indigo "Lumen" intelligence accent and a rare orange "Ember" human accent. New UI work should pull from `aperture/kit.js` rather than hand-rolling styles or introducing new MUI components.

**API error handling.** Every failed backend response is a standard envelope `{error: true, code, message, status}` (built in `src/api/errors.py`, covering deliberate `HTTPException`/`APIError` raises, validation errors, and unexpected 500s — the last never leaks internals). Frontend code reads it via `lib/apiError.js`'s `errorMessage(err)` / `errorCode(err)` rather than reaching into `err.response.data` directly.

## Key conventions

- Python: 4-space indent, `snake_case` modules, explicit `src.*` imports.
- React: PascalCase component filenames, camelCase hooks/helpers.
- All API routes except `/auth/register` and `/auth/login` require a Bearer JWT.
- **Data visibility is scoped by workspace membership, not by `owner_id`.** Scope asset/job/stats queries through the repo helpers `accessible_workspace_ids` / `accessible_asset_ids` / `can_access_asset` (a user reaches data for workspaces they own or are a member of). `owner_id` still scopes user-owned resources like pipelines and pipeline-nodes.
- **Workspaces are shareable with RBAC** (`owner` / `editor` / `viewer`). Enforce roles in `WorkspaceService` (`role_for` + `_can_view/_can_edit/_can_manage`): viewers read-only, editors edit/scan, owner manages members + delete. Routes map `WorkspaceAccessError` → 403.
- `SECRET_KEY` env var is required in production for JWT signing.
- `CORS` is currently locked to `http://localhost:3000`; update `allow_origins` in `src/api/app.py` deliberately.
- The `InMemoryPipelineRepository` in `repositories/memory_pipeline.py` is used exclusively in tests — it has the same interface as the Mongo repo. Keep its `_matches`/collection shims in sync when the Mongo repo uses a new query operator.
- **DB documents are Pydantic models** in `src/models/documents.py`. Build new documents via `Model(...).to_doc()` (never hand-assemble dicts); add a field by editing the model, not the repo's insert site.
- **Schema changes go through a migration.** Append a `Migration("000N_…", …, upgrade)` to `MIGRATIONS` in `src/migrations/runner.py` (append-only; never edit a released one); apply with `python -m src.migrations`. The API auto-runs pending migrations on startup unless `RUN_MIGRATIONS_ON_STARTUP=false`.
