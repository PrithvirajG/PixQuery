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
cd backend && pip install -r requirements.txt       # or: pip install -e ".[api,pipeline-worker,file-watcher]"
cd backend && uvicorn api_main:app --reload --port 8000   # API server
cd backend && python pipeline_worker_main.py                 # RabbitMQ consumer / pipeline executor
cd backend && python file_watcher_main.py             # filesystem watcher + reconciler
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
file_watcher_main.py  →  RabbitMQ (image_task queue)  →  pipeline_worker_main.py
        ↓                                                      ↓
    MongoDB                                              Weaviate (vectors)
        ↑
  api_main.py  ←→  React SPA (frontend/)
```

- **`api_main.py`** — FastAPI HTTP/WebSocket server. Entry point calls `src.api.create_app()`.
- **`pipeline_worker_main.py`** — Consumes `image_task` messages via `src/consumer/processing/image_task_consumer.py`'s `ImageProcessorConsumer`, which runs `PipelineExecutionService` (`src/services/pipeline_execution_service.py`).
- **`file_watcher_main.py`** — Polls workspace definitions from MongoDB, watches filesystem paths via `src/consumer/ingestion/filesystem_watcher.py`'s `WorkspaceWatcher`, which runs `ReconciliationService` (`src/services/reconciliation_service.py`).

### Backend source layout (`backend/src/`)

| Package | Responsibility |
|---|---|
| `api/routes/` | `rest/` — FastAPI HTTP route handlers: `auth`, `images`, `jobs`, `search`, `stats`, `status`, `workspaces`, `pipelines`, `pipeline_nodes`. `ws/` — WebSocket route handlers, one file per endpoint, each a full connection lifecycle (accept/auth/send-loop/receive-loop/close) rather than split by message direction; today just `events_socket.py`'s `/ws/events` |
| `api/security.py` | JWT creation/verification, bcrypt password hashing, `authenticate_from_token(token, users)` — the shared decode-then-look-up step for anywhere a token can't travel as an `Authorization` header (today: `api/routes/ws/events_socket.py`, since the browser WebSocket API can't set headers) |
| `api/dependencies.py` | FastAPI dependency injection — builds the 9 per-collection repositories off one shared connection and wires each service from the specific repos it needs |
| `services/` | Business logic — `ImageService`, `JobService`, `SearchService`, `PipelineService`, `WorkspaceService`, `StatsService`, plus `PipelineExecutionService` (DAG executor, used by the pipeline-worker process) and `ReconciliationService` (filesystem ingestion, used by the file-watcher process) |
| `services/access_scope.py` | Composes workspace + observation repositories into "what can this user/workspace see" (`accessible_workspace_ids`, `accessible_asset_ids`, `workspace_asset_ids`, `can_access_asset`) — the one join every visibility-scoped query shares |
| `services/executors/` | `registry.py` maps `node_type` strings → cached `BaseNodeExecutor` subclasses; `builtin.py` has implementations for `object_detection`, `face_detection`, `classification`, `captioning`, `embedding`, `resize`, `grayscale`, `image_write`, `ocr` |
| `models/documents.py` | Pydantic v2 document models — one class per MongoDB collection; **source of truth for schema**. Persist via `Model(...).to_doc()` |
| `utils/` | Generic, domain-agnostic helpers with zero dependency on `services`/`repositories`/`consumer` — the dividing line from a domain-specific "utility" module like `services/access_scope.py`, which stays put precisely because it's coupled to PixQuery's own models. `files.py` (`sha256_file`, `wait_for_stable_file` — raises `errors/files.py`'s `FileNotStableError`), `graph.py` (`topological_order` — Kahn's algorithm, the one shared implementation `pipeline_execution_service.py` and `pipeline_service.py` both wrap and translate exceptions from; raises `errors/graph.py`'s `GraphCycleError`/`UnknownNodeError`), `exif.py` (`extract_image_metadata` + EXIF/GPS parsing), `time.py` (`utcnow`), `vectors.py` (`normalize` — L2 normalization), `collections.py` (`top_by_frequency`) |
| `errors/` | Every custom exception in the backend, one module per owning flow/service — `graph.py`, `files.py`, `executors.py`, `pipelines.py`, `jobs.py`, `workspaces.py`. Centralized so a route handler doesn't need to know which service/util module happens to define an error, just that it's under `errors/`; each module still conceptually belongs to the flow it's named after, this package just holds the class definitions, not the logic that raises/handles them. The one exception *not* here: `api/errors.py`'s `APIError` stays put, since it's inseparable from that same file's FastAPI exception-handler registration (`register_error_handlers`) rather than a plain marker class raised/caught across modules. |
| `domain_events.py` | `Event` dataclass + factory functions (`pipeline_state_event`, `pipeline_stage_event`, `outputs_cleared_event`) broadcast to connected UIs — deliberately thin (routing identity + small state, never output payloads). Not to be confused with `publisher/events/`/`consumer/events/` below, which are the AMQP transport that carries these |
| `migrations/runner.py` | Versioned schema migrations — `run_migrations()`, ordered `MIGRATIONS` list, `schema_migrations` collection |
| `repositories/` | Data access — 9 per-collection repositories (`image_assets_repository.py`, `file_observations_repository.py`, `processing_jobs_repository.py`, `pipeline_runs_repository.py`, `model_outputs_repository.py`, `users_repository.py`, `pipeline_nodes_repository.py`, `pipeline_definitions_repository.py`, `workspace_definitions_repository.py`), each pure CRUD against exactly one collection — no cascades, no policy, no event emission. `bootstrap.py`'s `ensure_schema(db)` creates every collection's indexes and seeds the system pipeline nodes — call it once per process against a shared connection (see `api/dependencies.py::get_database()`). `fake_mongo.py`'s `FakeDatabase`/`FakeCollection` is the pymongo-emulating fake tests build any repository against directly (see `tests/repo_factory.py`'s `new_repos()`) |
| `infrastructure/ml/` | Model wrappers (`BlipModel`, `ClipModel`, `YoloModel`, `ModelInterface`) — loaded lazily by the executors above and by `infrastructure/vector_store/query_encoder.py` |
| `infrastructure/messaging/` | Generic transport primitives only — every named publisher/consumer lives in `publisher/`/`consumer/` instead (see below). `rabbitmq_publisher.py`'s `RabbitPublisher` and `rabbitmq_consumer.py`'s `RabbitConsumer` are the named-durable-queue pattern (competing consumers, one message each), both sharing `rabbitmq_connection.py`'s `_connect_with_retry`. `event_sink.py`'s `EventSink` — the mutable, swappable sink every service emits domain events through (armed with a real `EventPublisher` after each process's event loop starts) |
| `infrastructure/vector_store/` | `protocol.py` (`VectorSearchClient`, `QueryEncoder`), `weaviate.py` (`WeaviateEmbeddingStore` writes + `WeaviateSearchClient` reads), `query_encoder.py` (`ClipQueryEncoder`) |
| `consumer/` | Every RabbitMQ consumer in the codebase, one subpackage per concern, regardless of which process runs it — every one of them subclasses `RabbitConsumer` (`connect()`/`start_consuming()`/`on_message()`/`close()`), even when it overrides most of that contract's body rather than reusing it (see `events/` below); the point is a consistent interface and one place to find "every consumer," not maximal code sharing. `processing/` and `ingestion/` are full background processes with their own `worker.py` bootstrap (`pipeline_worker_main.py`/`file_watcher_main.py`); `events/` has no `worker.py` — its `EventConsumer` is instantiated lazily *inside* the API process by `api/routes/ws/events_socket.py`, not run standalone. |
| `consumer/processing/` | `image_task_consumer.py`'s `ImageProcessorConsumer(RabbitConsumer)` — consumes `image_task`, hands each job id to `PipelineExecutionService.run_job`, requeues on backoff. `worker.py`'s `start_pipeline_worker()` is the process bootstrap `pipeline_worker_main.py` calls |
| `consumer/ingestion/` | Two independent consumers driving `ReconciliationService` per workspace: `filesystem_watcher.py`'s `WorkspaceWatcher` + `ImageEventHandler` (one watchdog `Observer` per workspace, not RabbitMQ) and `scan_command_consumer.py`'s `ScanCommandConsumer(RabbitConsumer)` (consumes `scan_commands`, the manual "Scan" button's redispatch-failed path). `worker.py`'s `start_file_watcher()` is the process bootstrap `file_watcher_main.py` calls — builds the repos, starts the watcher, connects the scan consumer, runs the refresh/reconcile loop |
| `consumer/events/` | `event_consumer.py`'s `EventConsumer(RabbitConsumer)` — binds an exclusive queue to the `pixquery.events` fanout exchange and fans each event out to every WebSocket open in this API process. Overrides `connect()`/`start_consuming()` outright rather than calling `super()`: fanout pub/sub against an anonymous/exclusive/auto-delete queue with `no_ack=True` is a different delivery pattern than `RabbitConsumer.connect()`'s named durable queue for competing consumers, so reusing that body would declare the wrong kind of queue — see the module docstring. The only caller is `api/routes/ws/events_socket.py`'s lazily-started `get_subscriber()`, which now does `connect()` then `start_consuming()`, same two-step lifecycle as the other two consumers' `worker.py` |
| `publisher/` | Every named RabbitMQ publisher in the codebase — the mirror image of `consumer/`, same reasoning (one place to find "every publisher," each subclasses `RabbitPublisher`). Just `events/` today. |
| `publisher/events/` | `event_publisher.py`'s `EventPublisher(RabbitPublisher)` — the publish half of the live-events fanout; see `infrastructure/messaging/`'s row and `consumer/events/`'s row for the consume-side mirror. Constructed and `connect()`-ed directly in each of the three processes (`api/app.py::_start_event_bus`, `consumer/processing/image_task_consumer.py`, `consumer/ingestion/worker.py`), then wired into that process's `EventSink` |
| `config.py` | All env-var defaults in one place |
| `logging_config.py` | Central logging setup — `get_logger(__name__)` (every logger in the codebase goes through this, never `logging.getLogger` directly), `configure_logging(process_name=...)` (called once per process entry point), and the request-tracing contextvar (`bind_request_id`/`request_scope`/`get_request_id`) — see the Logging section below |

### Key data flow

1. `file_watcher_main.py` scans workspace paths, calls `ReconciliationService.reconcile()`.
2. The service computes SHA-256 of each file, upserts `image_assets` + `file_observations` in MongoDB, creates `processing_jobs`, publishes job IDs to RabbitMQ. A newly-created job (and a manually redispatched failed one) emits a `pipeline_state_event(state="queued")` through the injected `EventSink` — that's an explicit call in the service now, not an implicit side effect of the write.
3. `pipeline_worker_main.py` picks up job ID, loads the asset, runs each `ResolvedNode` in the pipeline through its registered executor, stores outputs in `model_outputs`, upserts vectors to Weaviate, marks job `completed`. `PipelineExecutionService` also owns the job's retry policy (`RETRY_DELAYS`, `MAX_ATTEMPTS`) and emits every state/stage transition itself, for the same reason — the repositories underneath are pure CRUD with no side effects of their own.
4. `api_main.py` serves assets/search/stats to the React frontend. Search supports `keyword` (MongoDB substring), `semantic` (Weaviate vector), and `hybrid` (merged + re-ranked) modes.

**Processing is workspace-scoped.** Assets are unique on `(workspace_id, content_sha256)` and jobs on `(workspace_id, asset_id, pipeline_id, pipeline_version)` — the same image in two workspaces is processed and stored twice, independently. Dedup applies only *within* a workspace.

**PipelineExecutionService executor model.** A `PipelineDefinition` is a DAG: `nodes` (vertices, each a `{node_id, pipeline_node_id, config_overrides, position}`) plus `edges` (`{edge_id, from_node_id, to_node_id, from_output?, to_input?}`), built by `PipelineService._build_graph`. A definition with no stored `edges` is treated as a straight chain (`_linear_edges`). `PipelineExecutionService._run_graph` topologically sorts the graph (Kahn's algorithm, raises on cycles/unknown edge refs) and runs each node once: with no port mapping a node inherits its parent's full context (so a straight chain threads `image` through unchanged); `from_output`/`to_input` pulls a single named value, used to disambiguate fan-in. Each node gets its own context copy, so divergent branches don't clobber each other; the final context is merged in topological order (last write wins). Executors are resolved via `get_executor(node_type)` from the registry; `_PERSIST_SKIP_KEYS = {"image", "asset", "embeddings", "text_embedding"}` are working state and are not written to `model_outputs`. To add a new node type: create a `BaseNodeExecutor` subclass in `builtin.py` and register it in `_EXECUTOR_CLASSES` in `registry.py`. Metadata extraction (EXIF/GPS/dimensions) is **not** a node — it's driven by `PipelineDefinition.extract_metadata` and read from the original file regardless of node order (`PipelineExecutionService._maybe_extract_metadata`).

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
- **Data visibility is scoped by workspace membership, not by `owner_id`.** Scope asset/job/stats queries through `services/access_scope.py`'s `accessible_workspace_ids` / `accessible_asset_ids` / `workspace_asset_ids` / `can_access_asset` (a user reaches data for workspaces they own or are a member of; these compose a `WorkspaceDefinitionsRepository` with a `FileObservationsRepository`, since no single per-collection repository can answer that join alone). `owner_id` still scopes user-owned resources like pipelines and pipeline-nodes.
- **Workspaces are shareable with RBAC** (`owner` / `editor` / `viewer`). Enforce roles in `WorkspaceService` (`role_for` + `_can_view/_can_edit/_can_manage`): viewers read-only, editors edit/scan, owner manages members + delete. Routes map `WorkspaceAccessError` → 403.
- `SECRET_KEY` env var is required in production for JWT signing.
- `CORS` is currently locked to `http://localhost:3000`; update `allow_origins` in `src/api/app.py` deliberately.
- **Repository file names carry the `_repository.py` suffix**, matching the class (`XxxRepository`) and DI provider (`get_xxx_repository()`) naming — e.g. `image_assets_repository.py`. `bootstrap.py` and `fake_mongo.py` are the two exceptions in `repositories/`, since neither is a repository implementation itself.
- **Service file names carry the `_service.py` suffix**, matching the class (`XxxService`) and DI provider (`get_xxx_service()`) naming — e.g. `image_service.py`. `access_scope.py`, `document_serializer.py`, and `pipeline_versioning.py` are the exceptions in `services/`, since each is a plain-function utility module with no `Service` class — the same reasoning as `bootstrap.py`/`fake_mongo.py` in `repositories/`.
- **Repositories are per-collection and pure CRUD — no cascades, no policy, no event emission.** Each of the 9 in `repositories/` (`ImageAssetsRepository`, `FileObservationsRepository`, `ProcessingJobsRepository`, `PipelineRunsRepository`, `ModelOutputsRepository`, `UsersRepository`, `PipelineNodesRepository`, `PipelineDefinitionsRepository`, `WorkspaceDefinitionsRepository`) wraps exactly one collection and never reaches into another — there is no god-repository or shared base class behind them, just `SomeRepository(database)` against a plain pymongo `Database` (or, in tests, `fake_mongo.FakeDatabase`). A service takes the *specific* repositories it needs as constructor keyword args — see any `services/*.py` constructor or `api/dependencies.py`'s `get_*_service()` providers for the pattern. Cross-collection orchestration (cascading deletes, the reprocess-replaces-not-accumulates behavior, retry policy, event emission) lives in the service that owns the operation, composing 2+ repositories explicitly — e.g. `WorkspaceService.delete_workspace`, `PipelineExecutionService._begin_run`/`_fail`. Tests build all 9 in one call via `tests/repo_factory.py`'s `new_repos()` (a fresh `FakeDatabase`, system nodes seeded like production) or `repos_from_database(db)` for a specific one.
- **Domain events are emitted by services, not repositories.** `infrastructure/messaging/EventSink` is a mutable box a service holds a reference to; each process arms it with a real `EventPublisher` once its event loop exists (`api/app.py`'s `_start_event_bus`, `consumer/processing/image_task_consumer.py`, `consumer/ingestion/worker.py`) and every mutating service method that matters to the UI (job state transitions, per-stage progress, outputs cleared) calls `self.event_sink.emit(...)` explicitly at the point of change.
- **External capabilities are injected, not imported mid-method.** `SearchService` takes `vector_store: VectorSearchClient` and `query_encoder: QueryEncoder` (both defaulting lazily to the Weaviate/CLIP adapters), so ranking and fusion are testable without infrastructure — see `tests/test_search_dependencies.py`. Follow the same pattern for new outbound dependencies.
- **`workspace_id` from a request is a filter, never a widening.** It arrives unvalidated on `/search`, so `SearchService._allowed_asset_ids` intersects the workspace's assets with the caller's own accessible set. Any new workspace-scoped query must intersect the same way rather than substituting the workspace scope for the user scope.
- Degrading gracefully still means logging: `search_service.py`'s logger records why semantic search fell back (unencodable query vs. vector-store fault) so a misconfigured Weaviate doesn't look like a missing CLIP install.
- **DB documents are Pydantic models** in `src/models/documents.py`. Build new documents via `Model(...).to_doc()` (never hand-assemble dicts); add a field by editing the model, not the repo's insert site.
- **Schema changes go through a migration.** Append a `Migration("000N_…", …, upgrade)` to `MIGRATIONS` in `src/migrations/runner.py` (append-only; never edit a released one); apply with `python -m src.migrations`. The API auto-runs pending migrations on startup unless `RUN_MIGRATIONS_ON_STARTUP=false`.

## Logging

Every logger in the backend is created via `src/logging_config.py`'s `get_logger(__name__)` — never `logging.getLogger` directly, and never a scattered `logging.basicConfig()` (there used to be nine of those; all gone). `get_logger` maps the caller's module path onto a `pixquery.*` namespace (`src.services.image_service` → `pixquery.services.image_service`), so the logger hierarchy mirrors the package layout and every layer — router, service, repository, a whole package — can be leveled independently.

`configure_logging(process_name=...)` is called exactly once, at the top of each of the four entry points (`api_main.py`, `pipeline_worker_main.py`, `file_watcher_main.py`, `src/migrations/__main__.py`), before any other import can log. It installs two handlers on the `pixquery` root logger: a colorized console handler (ANSI, auto-skipped on a non-TTY stream) and a `RotatingFileHandler` writing to `LOG_DIR/{process_name}.log`.

Env vars (all read once, in `config.py`):

| Var | Default | Purpose |
|---|---|---|
| `LOG_LEVEL` | `INFO` | Root level for the whole `pixquery` tree |
| `LOG_LEVELS` | *(empty)* | Per-logger overrides, applied on top of `LOG_LEVEL` — `"pixquery.repositories=WARNING,pixquery.services.search_service=DEBUG"` |
| `LOG_FORMAT` | includes timestamp, level, `[request_id]`, logger name, message | Shared by console + file |
| `LOG_COLOR` | `true` | Console only; ignored on redirected/non-TTY output |
| `LOG_TO_FILE` | `true` | Toggle the rotating file handler off entirely |
| `LOG_DIR` | `logs` | Where `{process_name}.log` and its rotated backups land |
| `LOG_FILE_MAX_BYTES` | `10485760` (10 MB) | Rollover cap per file |
| `LOG_FILE_BACKUP_COUNT` | `5` | Rotated files kept alongside the current one |

**Request tracing.** A short id (`logging_config.py`'s `request_id` contextvar) rides every log line — `%(request_id)s` in the default format — and every RabbitMQ message published via `RabbitPublisher.publish()`, as the AMQP `correlation_id`, defaulting to whatever id is currently bound. That's what makes one user action traceable across process boundaries without threading an id through every call site by hand:

1. `api/app.py`'s HTTP middleware binds one id per request (`X-Request-ID` header if the caller sent one, else a fresh one) and echoes it back on the response.
2. A route that publishes onto RabbitMQ (e.g. `workspaces.py`'s `/scan` → `scan_commands`) doesn't pass a `correlation_id` explicitly — `RabbitPublisher.publish()` reads the ambient one.
3. The receiving consumer's `on_message` rebinds it from `message.correlation_id` via `with request_scope(message.correlation_id):` before doing any work — see `ScanCommandConsumer`, `ImageProcessorConsumer`.
4. Anything that publishes further downstream (e.g. `ReconciliationService` dispatching onto `image_task`) inherits the same ambient id automatically, so it survives another hop.

A trigger chain with no inbound request (a filesystem-detected file change, the periodic reconcile loop) binds a **fresh** id of its own at the outermost point (`ImageEventHandler._observe`, `WorkspaceWatcher.sync`/`reconcile_all`) — see `request_scope()` — so its own log lines are still traceable as one unit, just not tied to any HTTP request.

**What gets logged.** Deliberately not "everything" — routine reads are silent; mutating/destructive operations and their errors are not. `PipelineExecutionService.run_job` logs job start/complete/fail/retry at INFO/WARNING (per-node execution is DEBUG, off by default); `WorkspaceService`/`PipelineService` log create/delete/cascade-delete and membership changes; `auth.py` logs registration and failed logins. Follow that weighting for new code: log state transitions and failures, not every read.
