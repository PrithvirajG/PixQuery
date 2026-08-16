---
project: PixQuery
type: knowledge-note
source: /mnt/d/Projects/PixQuery/docs/engineering/pixquery-current-implementation-audit.md
---

# PixQuery — Current Implementation Audit

**Date:** 2026-05-29  
**Workspace inspected:** `/mnt/d/Projects/PixQuery`

## 1. What PixQuery currently is

PixQuery is a local-first AI image search and processing application. It watches image folders, registers discovered files as assets, queues asynchronous processing jobs, runs computer-vision models, stores derived metadata, and exposes search/browse functionality through a FastAPI backend and React frontend.

The implementation already resembles the intended architecture in the technical requirements document, but with one important caveat: the product documents describe a fully composable pipeline executor, while the current worker path still runs a fixed default image analysis pipeline.

## 2. Runtime architecture

### Frontend

- React SPA under `frontend/src`.
- Main routes in `frontend/src/App.js`:
  - `/search`
  - `/workspaces`
  - `/pipelines`
  - `/jobs`
  - `/image/:id`
- Authentication context in `frontend/src/context/AuthContext.js`.
- UI style: dark, glassmorphic Tailwind/MUI hybrid.

### Backend

- FastAPI entrypoint: `backend/api_main.py` imports `src.api.app:create_app`.
- Routes under `backend/src/api/routes`:
  - `auth.py`
  - `images.py`
  - `jobs.py`
  - `pipeline_nodes.py`
  - `pipelines.py`
  - `search.py`
  - `stats.py`
  - `status.py`
  - `websocket.py`
  - `workspaces.py`
- Service layer under `backend/src/services`.
- Repository layer under `backend/src/repositories`.

### Infrastructure

From compose files:

- API service: FastAPI/Uvicorn on port 8000.
- Frontend service: Node/React on port 3000.
- Ingestor service: runs `monitoring_main.py`.
- Worker service: runs `worker_main.py`.
- MongoDB: primary document store.
- RabbitMQ: asynchronous processing queue.
- Weaviate: vector store for embeddings.

## 3. Data model observed

`MongoPipelineRepository` uses these collections:

- `image_assets`
- `file_observations`
- `processing_jobs`
- `pipeline_runs`
- `model_outputs`
- `users`
- `pipeline_nodes`
- `pipeline_definitions`
- `workspace_definitions`

Key concepts:

- `image_assets`: content-addressed image records keyed by SHA-256.
- `file_observations`: workspace-relative file sightings and active/missing status.
- `processing_jobs`: queued/processing/completed/failed jobs per asset + pipeline version.
- `pipeline_runs`: execution records for job attempts.
- `model_outputs`: structured model outputs such as captions and detections.
- `pipeline_nodes`: node library, including seeded system nodes.
- `pipeline_definitions`: user-defined ordered chains of pipeline nodes.
- `workspace_definitions`: watched folders with extensions and pipeline IDs.

## 4. Ingestion flow

Implemented in `backend/src/pipelines/ingestion/reconciler.py`.

Flow:

1. Iterate files in a workspace with configured extensions.
2. Wait until each file is stable.
3. Hash file content with SHA-256.
4. Upsert an image asset.
5. Upsert a workspace file observation.
6. Ensure a processing job exists for the asset/pipeline/version.
7. Publish new job IDs to RabbitMQ when a publisher is present.
8. Mark no-longer-seen observations as missing.

Strengths:

- Uses content hashes for deduplication/idempotency. *(Update 2026-05-30: dedup is now **per workspace** — asset identity is `(workspace_id, content_sha256)`, so the same image in different workspaces is processed independently. See [[Workspace Sharing & Access Control]].)*
- Separates asset identity from workspace path observations.
- Handles missing files and refreshes active asset status.
- Waits for stable files before processing.

Concerns:

- Recursive scanning over very large folders can be expensive.
- Stable-file checks may slow large initial imports.
- Workspace path behavior needs careful Docker/Windows/WSL documentation.

## 5. Processing flow

Implemented primarily in `backend/src/pipelines/processing/pipeline.py`.

Current `DefaultImageAnalysisPipeline` does:

1. Start job and pipeline run.
2. Load asset path.
3. Verify file still exists and hash has not changed.
4. Open image with PIL.
5. Run YOLO detections.
6. Run BLIP captioning.
7. Run CLIP image embedding.
8. Run CLIP text embedding over the generated caption.
9. Save detections and caption to `model_outputs`.
10. Upsert embeddings to Weaviate if vector store is configured.
11. Complete or fail job with retry metadata.

Strengths:

- Good correctness checks before processing.
- Stores model version-ish metadata in outputs.
- Has failure recording with traceback and retry behavior.
- Produces both human-readable captions and vector embeddings.

Main gap:

- Stored pipeline definitions are not yet the execution source of truth. The system has pipeline nodes and definitions, but the actual processing path is still hardcoded to YOLO → BLIP → CLIP.

## 6. Search flow

Implemented in `backend/src/services/search_service.py` and frontend `SearchView.js`.

Modes:

- `keyword`: substring match over path + caption.
- `semantic`: CLIP text encoding → Weaviate GraphQL `nearVector` query against `TextEmbedding`.
- `hybrid`: run keyword and semantic independently, merge/dedupe, sort by score.
- empty query: browse latest active images.

Strengths:

- The product exposes a clear keyword/semantic/hybrid model to users.
- Workspace filtering exists.
- Search degrades to keyword if semantic search fails.
- Browse-all behavior makes the search page useful without a query.

Concerns:

- `_encode_query()` loads `CLIPModel` and `CLIPProcessor` inside the request path. This should be cached or served by a model service.
- Keyword search pulls up to 2,000 assets and filters in Python; acceptable for demos, not large libraries.
- Hybrid scoring is simplistic: keyword hits are score `1.0`, semantic hits use certainty, then merged/sorted. This can distort ranking.
- Weaviate has native hybrid search capabilities that may be better than manual merge.

## 7. Frontend product surface

Observed route structure supports the intended product:

- Search and browse image grid.
- Workspaces management.
- Pipeline management.
- Jobs monitoring.
- Image detail page.
- Auth-gated dashboard and unauthenticated landing page.

`SearchView.js` already includes:

- Query input.
- Mode selector: keyword / semantic / hybrid.
- Workspace dropdown.
- Similarity threshold slider for semantic/hybrid.
- Pagination.
- Image cards with thumbnails, captions/descriptions, file sizes, and scores.

## 8. Documentation drift found

`AGENTS.md` appears stale relative to the current repo:

- It says infrastructure starts Redis, RabbitMQ, and Qdrant.
- Current compose uses MongoDB, RabbitMQ, and Weaviate.
- It says backend route command is `uvicorn src.api.main:app --reload`.
- Current entrypoint is `api_main.py`, which imports `src.api.app:create_app`.
- It references folders such as `ingestion`, `processing`, `query`, and `storage` at a structure that partly differs from the current `backend/src` layout.

Recommendation: update `AGENTS.md` soon, because future agents and contributors will otherwise run wrong commands.

## 9. Product maturity assessment

### Already credible

- Local-first architecture.
- Async queue-based processing.
- Content-hash asset model.
- Workspace abstraction.
- Model output storage.
- CLIP/BLIP/YOLO baseline AI stack.
- Semantic and hybrid search API.
- React search/workspace/pipeline/job UI surfaces.

### Not yet product-grade

- Dynamic pipeline execution.
- Large-library search/indexing performance.
- Model caching and hardware acceleration story.
- Setup/diagnostics for self-hosted users.
- Security hardening for path access and deployment.
- Metadata breadth: EXIF, OCR, faces, duplicates, video, RAW.
- Automated tests across the full ingestion-processing-search path.

## 10. Recommended engineering priorities

### Priority 0 — correct docs and setup

- Update `AGENTS.md` to match MongoDB/RabbitMQ/Weaviate and current commands.
- Add a “known-good local startup” section to README.
- Document Windows/WSL/Docker path mapping.

### Priority 1 — make pipeline execution real

- Define a runtime interface for node executors.
- Map `node_type` to executor implementations.
- Execute the ordered `pipeline_definitions.nodes` chain.
- Persist per-node outputs and errors in `pipeline_runs` or `model_outputs`.
- Version node configs and invalidate/reprocess when configs change.

### Priority 2 — make semantic search fast

- Cache CLIP text model on process startup or move it to a model service.
- Consider native Weaviate hybrid search or another vector DB strategy if Weaviate remains operationally heavy.
- Add search performance tests against thousands of assets.

### Priority 3 — add explainability

- On image detail pages, show all model outputs: caption, detections, embeddings metadata, pipeline, model versions, timestamps.
- On search results, show why the item matched.

### Priority 4 — deepen image intelligence

- OCR node.
- EXIF/metadata extraction node.
- Face detection and clustering path.
- Duplicate/perceptual hash node.
- Optional newer embedding models beyond CLIP ViT-B/32.

## 11. Suggested next documents

- `docs/product/pixquery-product-vision-roadmap.md` — product thesis and roadmap.
- `docs/research/pixquery-market-technical-analysis.md` — external landscape and strategic recommendation.
- `docs/engineering/pixquery-architecture-reality-map.md` — gap map between TRD and implementation.
- Updated `AGENTS.md` — contributor/agent execution guide.
