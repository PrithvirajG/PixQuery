# Repository Guidelines

## Project Structure & Module Organization

PixQuery is split into a Python backend and a React frontend.

Backend code lives in `backend/src`:

- `api/` — FastAPI app factory (`app.py`), routers, dependencies, and JWT/bcrypt security. Route handlers are under `api/routes/` (one file per resource: `auth`, `images`, `jobs`, `search`, `stats`, `status`, `workspaces`, `pipelines`, `pipeline_nodes`, `websocket`).
- `services/` — business logic (`ImageService`, `JobService`, `SearchService`, `PipelineService`, `WorkspaceService`, `StatsService`).
- `repositories/` — data access. `mongo_pipeline.py` is the production MongoDB repo; `memory_pipeline.py` is an in-memory implementation with the same interface, used by tests.
- `pipelines/ingestion/` — `FilesystemReconciler` (hash-based dedup + job dispatch) and the multi-workspace `watcher.py`.
- `pipelines/processing/` — the worker-side pipeline (`pipeline.py`), RabbitMQ consumer (`rmq_processor.py`), and model wrappers under `models/` (YOLO, BLIP, CLIP).
- `infrastructure/messaging/` — RabbitMQ publish/consume via `aio-pika`.
- `infrastructure/vector_store/` — Weaviate upsert/search.
- `config.py` — all environment-variable defaults.

Backend tests and fixtures are in `backend/tests`.

Frontend code lives in `frontend/src`: reusable UI in `components/`, page-level screens in `views/` and `pages/`, auth state in `context/`, and static assets in `frontend/public`.

Root-level `docker-compose.infra.yml` starts the three infrastructure services (MongoDB, RabbitMQ, Weaviate). `docker-compose.yml` additionally runs the API, worker, `ingestor` (the monitor process), and frontend.

## Build, Test, and Development Commands

- `docker compose -f docker-compose.infra.yml up -d`: start local infrastructure (MongoDB:27017, RabbitMQ:5672/15672, Weaviate:8080).
- `cd backend && pip install -r requirements.txt`: install backend runtime dependencies (or `pip install -e ".[api,pipeline-worker,file-watcher]"`).
- `cd backend && uvicorn api_main:app --reload --port 8000`: run the FastAPI API locally. The entry point `api_main.py` calls `src.api.create_app()`.
- `cd backend && python pipeline_worker_main.py`: run the RabbitMQ consumer / pipeline executor.
- `cd backend && python file_watcher_main.py`: run the filesystem watcher + reconciler.
- `cd backend && python -m unittest discover tests`: run backend tests. Single file: `python -m unittest tests.test_filesystem_pipeline`.
- `cd frontend && npm install`: install React dependencies.
- `cd frontend && npm start`: start the React dev server at `http://localhost:3000`.
- `cd frontend && npm test`: run Jest/React Testing Library tests.
- `cd frontend && npm run build`: create a production frontend build.
- `cd frontend && npm run build:css`: regenerate minified Tailwind output in `src/output.css`.

## Coding Style & Naming Conventions

Use 4-space indentation for Python and lowercase `snake_case` module filenames. Prefer explicit imports from `src.*` packages and keep API, service, repository, and pipeline concerns separated. Data visibility is scoped by **workspace membership** (via the repo helpers `accessible_workspace_ids` / `accessible_asset_ids` / `can_access_asset`), not by a single `owner_id`; user-owned resources like pipelines remain `owner_id`-scoped. Workspaces are shareable with `owner`/`editor`/`viewer` roles enforced in `WorkspaceService` (see `technical-requirement-doc.md` §10.1). React components use PascalCase filenames and exports, such as `ImageCard.js`; hooks, helpers, and local variables use camelCase. Follow the Create React App ESLint configuration and avoid committing generated caches such as `__pycache__`.

## Testing Guidelines

Backend tests use `unittest`; name files `test_*.py` and keep fixtures in `backend/tests`. Tests use `InMemoryPipelineRepository` (no live infra required) — extend it in lockstep whenever you add a method to `MongoPipelineRepository`. Add focused tests for processing, search, storage, and API behavior when changing those areas. Frontend tests use Jest with React Testing Library; colocate component tests as `*.test.js` when practical.

## Commit & Pull Request Guidelines

Recent commits use short, descriptive summaries, for example `Fixed and shifted to Rabbit MQ`. Keep commits focused on one change. Pull requests should include a concise description, affected backend/frontend areas, test results, linked issues when applicable, and screenshots for UI changes.

## Security & Configuration Tips

Do not commit local databases, model outputs, credentials, or watched photo directories. Keep service credentials and paths configurable through environment variables (see `backend/src/config.py`). `SECRET_KEY` is required for JWT signing in production. The API currently allows CORS from `http://localhost:3000`; update `allow_origins` in `src/api/app.py` deliberately for deployed environments.
