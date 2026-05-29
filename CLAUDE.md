# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

PixQuery is an AI-powered local photo management system. It ingests images from watched directories, runs them through configurable AI pipelines (object detection, captioning, CLIP embedding), stores results in MongoDB + Weaviate, and exposes a natural-language/vector search API consumed by a React SPA.

## Commands

### Infrastructure (required before running backend)
```bash
docker compose -f docker-compose.infra.yml up -d   # MongoDB:27017, RabbitMQ:5672, Weaviate:8080
```

### Backend
```bash
cd backend && pip install -r requirements.txt       # or: pip install -e ".[api,worker,monitor]"
cd backend && uvicorn api_main:app --reload --port 8000   # API server
cd backend && python worker_main.py                 # RabbitMQ consumer / pipeline executor
cd backend && python monitoring_main.py             # filesystem watcher + reconciler
```

### Tests
```bash
cd backend && python -m unittest discover tests     # all backend tests
cd backend && python -m unittest tests.test_filesystem_pipeline   # single test file
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
- **`worker_main.py`** — Consumes `image_task` messages; runs `DefaultImageAnalysisPipeline` (YOLO → BLIP → CLIP) via `src/pipelines/processing/`.
- **`monitoring_main.py`** — Polls workspace definitions from MongoDB, watches filesystem paths, publishes jobs via `FilesystemReconciler`.

### Backend source layout (`backend/src/`)

| Package | Responsibility |
|---|---|
| `api/routes/` | FastAPI route handlers (one file per resource) |
| `api/security.py` | JWT creation/verification, bcrypt password hashing |
| `api/dependencies.py` | FastAPI dependency injection (DB, current user, services) |
| `services/` | Business logic — `ImageService`, `JobService`, `SearchService`, `PipelineService`, `WorkspaceService`, `StatsService` |
| `repositories/` | Data access — `mongo_pipeline.py` (production), `memory_pipeline.py` (tests) |
| `pipelines/processing/` | `DefaultImageAnalysisPipeline` + YOLO/BLIP/CLIP model wrappers |
| `pipelines/ingestion/` | `FilesystemReconciler` (hash-based dedup, job dispatch), `watcher.py` |
| `infrastructure/messaging/` | RabbitMQ publish/consume via `aio-pika` |
| `infrastructure/vector_store/` | Weaviate upsert/search |
| `config.py` | All env-var defaults in one place |

### Key data flow

1. `monitoring_main.py` scans workspace paths, calls `FilesystemReconciler.reconcile()`.
2. Reconciler computes SHA-256 of each file, upserts `image_assets` + `file_observations` in MongoDB, creates `processing_jobs`, publishes job IDs to RabbitMQ.
3. `worker_main.py` picks up job ID, loads asset from MongoDB, runs YOLO → BLIP → CLIP, stores outputs in `model_outputs`, upserts vectors to Weaviate, marks job `completed`.
4. `api_main.py` serves assets/search/stats to the React frontend. Search supports `keyword` (MongoDB substring), `semantic` (Weaviate vector), and `hybrid` (merged + re-ranked) modes.

### Frontend (`frontend/src/`)

React 19 SPA with React Router, Tailwind CSS, and MUI. Four main views:
- `ImageQueryView.js` — search with mode/threshold/workspace/top-K controls
- `ModelManagementView.js` — pipeline + node library management
- `ImageUploadView.js` — workspace CRUD
- `ProgressTrackingView.js` — statistics + recent jobs table

Design system: dark glassmorphic (`bg-slate-950` base, violet/blue accents, `backdrop-blur` glass cards). New views use pure Tailwind; avoid introducing MUI components in new UI work.

## Key conventions

- Python: 4-space indent, `snake_case` modules, explicit `src.*` imports.
- React: PascalCase component filenames, camelCase hooks/helpers.
- All API routes except `/auth/register` and `/auth/login` require a Bearer JWT.
- All DB queries are scoped by `owner_id` — never query without it.
- `SECRET_KEY` env var is required in production for JWT signing.
- `CORS` is currently locked to `http://localhost:3000`; update `allow_origins` in `src/api/app.py` deliberately.
- The `InMemoryPipelineRepository` in `repositories/memory_pipeline.py` is used exclusively in tests — it has the same interface as the Mongo repo.
