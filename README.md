# PixQuery

PixQuery is a local-first AI image search and processing system. It watches
folders of images, runs them through AI pipelines (object detection, captioning,
CLIP embeddings), stores the results in MongoDB + Weaviate, and exposes
keyword / semantic / hybrid search through a FastAPI backend and a React SPA.

Everything runs on your own machine — images and AI outputs never leave it.

## Architecture

Three independent backend processes communicate through MongoDB and RabbitMQ:

```
 monitoring_main.py            worker_main.py
 (filesystem watcher)          (pipeline executor)
        │                              │
        │ scans workspace folders      │ consumes job IDs
        │ hashes + dedups files        │ runs YOLO -> BLIP -> CLIP
        ▼                              ▼
   ┌──────────┐   image_task    ┌──────────┐      ┌──────────┐
   │ RabbitMQ │◄────queue──────►│  worker  │─────►│ Weaviate │  (vectors)
   └──────────┘                 └────┬─────┘      └──────────┘
        ▲                            │ model outputs
        │ publishes jobs             ▼
        │                       ┌──────────┐
   (reconciler) ──────────────►│ MongoDB  │  (assets, jobs, outputs, users)
                                └────┬─────┘
                                     │
                              ┌──────▼──────┐      ┌──────────────┐
                              │ api_main.py │◄────►│  React SPA   │
                              │  (FastAPI)  │ HTTP │ (frontend/)  │
                              └─────────────┘  +WS └──────────────┘
```

- **`monitoring_main.py`** — reads workspace definitions from MongoDB, watches
  their folders, and dispatches processing jobs via `FilesystemReconciler`.
- **`worker_main.py`** — consumes `image_task` messages and runs the processing
  pipeline, writing model outputs to MongoDB and embeddings to Weaviate.
- **`api_main.py`** — serves auth, images, search, jobs, workspaces, pipelines,
  and stats to the frontend.

See `CLAUDE.md` and `AGENTS.md` for the full module map.

## Requirements

- Docker & Docker Compose (for MongoDB, RabbitMQ, Weaviate)
- Python 3.10+ and Node.js 18+ (for running backend/frontend outside Docker)
- ~16 GB RAM recommended; a CUDA GPU is optional but speeds up model inference

## Known-good local startup

Run these in order. Each backend process is long-running — use separate
terminals (or `docker compose up` for the all-in-one path below).

```bash
# 1. Infrastructure (MongoDB:27017, RabbitMQ:5672/15672, Weaviate:8080)
docker compose -f docker-compose.infra.yml up -d

# 2. Backend dependencies
cd backend
pip install -r requirements.txt          # or: pip install -e ".[api,worker,monitor]"

# 3. API server                          → http://localhost:8000
uvicorn api_main:app --reload --port 8000

# 4. Worker (new terminal, in backend/)
python worker_main.py

# 5. Monitor / filesystem watcher (new terminal, in backend/)
python monitoring_main.py

# 6. Frontend (new terminal)             → http://localhost:3000
cd frontend
npm install
npm start
```

The first worker run downloads model weights (YOLOv8, BLIP, CLIP), which can take
a few minutes. `SECRET_KEY` should be set in any non-local deployment (used to
sign JWTs). All other settings have sensible defaults in `backend/src/config.py`.

Alternatively, `docker compose up` builds and runs the API, worker, ingestor, and
frontend together on top of the infrastructure services.

## Manual end-to-end smoke test

After all processes are running:

1. Open `http://localhost:3000`, register an account, and log in.
2. Create a workspace pointing at an **absolute path** of a folder with images —
   for example the bundled samples at `<repo>/backend/samples` (see path mapping
   below if backend runs in Docker).
3. The monitor reconciles the folder and queues jobs; watch the **Jobs** view as
   they move `queued → processing → completed`.
4. Once a job completes, go to **Search**, type a term that matches the image
   content (e.g. the caption), and confirm a result with a thumbnail appears.
5. Open the image to see its caption and detection overlay.

For a fast wiring check that needs **no infrastructure or model weights**, run the
automated smoke test instead:

```bash
cd backend && python -m unittest tests.test_smoke_search
```

## Workspace paths across Windows / WSL / Docker

A workspace's path is interpreted by **whichever process watches it**, so it must
be valid there:

- **Everything native (host Python):** use a normal host path
  (`/home/you/photos`, or `C:\\Users\\you\\Photos` on Windows).
- **WSL running the backend:** use the WSL view of the path. A Windows folder
  `D:\Photos` is `/mnt/d/Photos` inside WSL.
- **Backend in Docker:** the container only sees folders you bind-mount into it.
  Mount the host folder (e.g. add `- /mnt/d/Photos:/data/photos` to the `worker`
  and `ingestor` services) and then register the workspace as the **container**
  path (`/data/photos`), not the host path.

If a workspace shows no activity, the watched path almost certainly isn't visible
to the monitor/worker process — check this first.

## Troubleshooting

- **No jobs appear after creating a workspace** — confirm `monitoring_main.py` is
  running and the workspace path is valid *for that process* (see path mapping).
- **Jobs stay `queued`** — the worker isn't running or can't reach RabbitMQ; check
  `python worker_main.py` output and that `docker compose -f docker-compose.infra.yml ps` shows RabbitMQ healthy.
- **Jobs go to `failed`** — open the job to read the recorded error; common causes
  are missing model weights (first run) or the file changing during processing.
- **Semantic search returns nothing / falls back to keyword** — Weaviate is
  unreachable or no embeddings exist yet (no completed jobs). Keyword search works
  without Weaviate.
- **Frontend can't reach the API** — the SPA targets `http://localhost:8000`;
  make sure the API is up and CORS (`allow_origins` in `src/api/app.py`) permits
  the frontend origin.
- **OCR node jobs fail** — the `ocr` node uses `pytesseract`, which needs the
  Tesseract binary installed on the worker host (e.g. `apt-get install tesseract-ocr`).

## Tests

```bash
cd backend && python -m unittest discover tests     # backend
cd frontend && npm test                              # frontend
```

## Documentation

- `AGENTS.md` — contributor/agent execution guide and module layout.
- `CLAUDE.md` — architecture and conventions for AI coding assistants.
- `technical-requirement-doc.md` — full technical requirements and API reference.
- `obsidian/PixQuery/` — product vision, audits, and the implementation backlog.
