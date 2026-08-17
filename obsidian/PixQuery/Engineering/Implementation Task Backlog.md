---
project: PixQuery
type: knowledge-note
created: 2026-05-29
---

> **Update 2026-08-16: Superseded — see PR #1.** All of P0–P4 below are now done in the codebase (this doc's checkboxes/status were never updated to reflect it):
> - **P0** — `AGENTS.md`, `README.md`, and `CLAUDE.md` now correctly describe MongoDB/RabbitMQ/Weaviate, the real `backend/src` layout, and the actual frontend filenames.
> - **P1 (central task)** — the dynamic pipeline executor exists: `backend/src/pipelines/processing/executors/base.py` (`NodeExecutor` Protocol), `registry.py` (`_EXECUTOR_CLASSES`), and `pipeline.py`'s `DynamicPipeline` (Kahn's-algorithm topological execution over the node DAG, per-node output persistence). The worker (`rmq_processor.py`) runs `DynamicPipeline`, and the ingestion linkage now reads workspace `pipeline_ids`.
> - **P2** — `SearchService._encode_query()` now uses the shared, cached `ClipModel` (`get_clip_model()`) instead of loading HuggingFace transformers per request, fixing both the perf issue and the image/text embedding-space mismatch; hybrid ranking uses Reciprocal Rank Fusion (`_reciprocal_rank_fusion()` in `search_service.py`).
> - **P3** — search results and image detail carry a structured `match_reason` (`search_service.py`), giving explainable "why matched" provenance.
> - **P4** — an OCR node (`OcrExecutor` in `executors/builtin.py`, `node_type: "ocr"`) and metadata/EXIF extraction are implemented and registered in `_EXECUTOR_CLASSES`.
>
> Current source of truth: `CLAUDE.md`'s DynamicPipeline section and this repo's code. Kept below as a historical decision record — do not treat the P0–P4 task lists as an open backlog.

# PixQuery — Implementation Task Backlog (P0–P4)

Derived from [[Product Vision & Roadmap]], [[Current Implementation Audit]], [[Architecture Reality Map]], and [[Market & Technical Landscape Analysis]]. Turns those notes into precise, prioritized engineering tasks, verified against the current codebase.

Scope is **near-term core (P0–P4)**; roadmap Phases 5–6 (RBAC/teams, consumer photo features) are explicitly deferred. Each task states **Why / Where / What**, with **Alternatives** for the non-trivial ones.

> **Update (2026-05-30):** Workspace-level sharing + RBAC (owner/editor/viewer) and per-workspace processing isolation have since been delivered ahead of the deferred Phase 5–6 — see [[Workspace Sharing & Access Control]]. Org-wide teams/multi-tenancy remain deferred.

## Context

The four knowledge-base notes converge on one verdict: PixQuery has a **credible skeleton** (workspaces, ingestion, jobs, model outputs, vector search, auth, React UI) but a **trust-breaking gap** — the product/UI promise *composable pipelines*, while the worker still runs a fixed YOLO→BLIP→CLIP path. Several supporting problems (stale docs, per-request model loading, a CLIP embedding-space mismatch, opaque search, thin metadata) compound this.

### Verified ground truth (from code, not just docs)
- **Worker is hardcoded.** `worker_main.py` → `ImageProcessorConsumer` (`src/pipelines/processing/rmq_processor.py:17-24`) instantiates one `DefaultImageAnalysisPipeline` and calls `run_job()` (`src/pipelines/processing/pipeline.py:26-92`). `pipeline_definitions` / `pipeline_nodes` are **never read** during processing.
- **The linkage is broken even before the worker.** `watcher.py:_make_reconciler()` (`src/pipelines/ingestion/watcher.py:103-111`) never passes the workspace's `pipeline_ids`, so `FilesystemReconciler` defaults to `DEFAULT_PIPELINE_ID="default_image_analysis"` (`reconciler.py:94-98`). Every job is stamped with the default pipeline regardless of what the user assigned.
- **8 system nodes seeded** (`src/repositories/mongo_pipeline.py` `_SYSTEM_NODES`): object_detection, captioning, embedding, face_detection, classification, resize, grayscale, draw_boxes. **Only 3 have implementations** (YOLO/BLIP/CLIP). No `NodeExecutor` interface or registry exists anywhere. `_build_node_chain()` (`src/services/pipeline_service.py:105-123`) builds prev/next links for the UI only.
- **Search reloads CLIP per request.** `SearchService._encode_query()` (`src/services/search_service.py:276-288`) calls `CLIPModel.from_pretrained(...)` + `CLIPProcessor.from_pretrained(...)` on every semantic query.
- **CLIP embedding-space mismatch (correctness bug).** Worker embeds *images* with the OpenAI `clip` package, `ViT-B/32` (`src/pipelines/processing/models/clip.py`). Search encodes *text* with HuggingFace `transformers` `openai/clip-vit-base-patch32`. Different implementations → not guaranteed the same space → semantic search is subtly wrong.
- **Hybrid ranking is naive.** Keyword hits get fixed `score=1.0`; semantic hits use Weaviate `certainty` (0–1); lists are concatenated, deduped, sorted by score (`search_service.py:181-207`) — so keyword always outranks semantic. Keyword search pulls a 2000-asset pool and filters in Python (`search_service.py:90-118`).
- **Docs drift.** `AGENTS.md` says Redis/RabbitMQ/Qdrant + `uvicorn src.api.main:app` and lists folders (`ingestion/processing/query/storage`) that don't match `backend/src`. `README.md` is 2 lines. The repo's own `CLAUDE.md` lists wrong frontend filenames (see P0).
- **Image detail** (`frontend/src/pages/ImageDetails.js`, route `/image/:id`, API `GET /images/{id}/detail`) shows caption + detection overlays but no pipeline/model version, timestamps, or embedding provenance. **Search cards** (`views/SearchView.js`) show a score badge only — no "why matched."
- **Test pattern to reuse:** `unittest` + `InMemoryPipelineRepository` (`tests/test_filesystem_pipeline.py`); the in-memory repo mirrors the Mongo repo interface and must be extended in lockstep with any new repo method.

---

## P0 — Make the foundation truthful (docs + setup + smoke test)
**Why:** Contributors/agents currently run wrong services and commands; there's no sample data to verify a working install. Cheap, unblocks everything else. (Audit §10 P0; Roadmap Phase 1.)

**Where / What:**
- `AGENTS.md` — correct infra to **MongoDB / RabbitMQ / Weaviate**; commands to `uvicorn api_main:app --reload --port 8000`, `python worker_main.py`, `python monitoring_main.py`; fix the module map to the real `backend/src` layout (`api/`, `services/`, `repositories/`, `pipelines/{ingestion,processing}`, `infrastructure/{messaging,vector_store}`).
- `README.md` — expand from the 2-line stub: overview, the 3-process architecture diagram, "known-good local startup" (infra compose → backend deps → 3 processes → frontend), a **Windows/WSL/Docker path-mapping** note for `workspace_path`, and a short troubleshooting list.
- `CLAUDE.md` — fix the frontend section: actual files are `views/SearchView.js` (exports `ImageQueryView`), `views/WorkspacesView.js` (`ImageUploadView`), `views/PipelinesView.js` (`ModelManagementView`), `views/JobsView.js` (`ProgressTrackingView`), plus `pages/ImageDetails.js`, `pages/LandingPage.js`. (Current CLAUDE.md lists the export names as if they were filenames.)
- **Sample dataset + smoke test** — add a few small test images and an end-to-end check: create workspace → reconcile → process → search returns the expected hit.

**Alternatives (smoke test):**
- **(Recommended)** Two-tier: a fast `unittest` integration test of ingestion using `InMemoryPipelineRepository` + a fake publisher (extends the existing `tests/test_filesystem_pipeline.py` pattern, no infra needed) **plus** a documented manual end-to-end checklist in the README for the real-infra path.
- A single full integration test that spins up real Mongo/RabbitMQ/Weaviate — higher fidelity but flaky/slow in CI and on WSL; defer to a tagged/optional suite.

---

## P1 — Make pipelines real (dynamic pipeline executor) ★ central task
**Why:** The #1 gap named by all four notes. Stored `pipeline_definitions` must become the worker's execution plan, and jobs must actually reference the workspace's assigned pipeline. (Audit §5/§10 P1; Reality Map §2/§4.)

**Where / What:**
1. **Executor framework** — new `backend/src/pipelines/processing/executors/`:
   - `base.py`: `NodeExecutor` protocol — `node_type: str`; `run(context: dict, config: dict) -> dict` (returns only the keys it adds).
   - `registry.py`: `NODE_EXECUTORS: dict[node_type, NodeExecutor]`.
   - Concrete executors **wrapping existing model wrappers** (`YoloModel.detect`, `BlipModel.describe`, `ClipModel.embed/embed_text`) for `object_detection`, `captioning`, `embedding`; plus trivial PIL ops already seeded: `resize`, `grayscale`, `draw_boxes`. Register `face_detection`/`classification` as explicit "not implemented" executors that fail the node with a clear message (no model yet).
2. **Dynamic runtime** — `pipeline.py`: add `DynamicPipeline.run_job(repository, job_id)`:
   - Reuse the existing guardrails from `DefaultImageAnalysisPipeline` (`pipeline.py:35-39`): asset active, file exists, SHA-256 unchanged; and the existing `start_job`/`complete_job`/`fail_job` retry flow.
   - Load the pipeline definition for `job["pipeline_id"]` (reuse `PipelineService` getter), init `context = {"image": PIL.Image, "asset": asset}`, iterate nodes **in `order`**: merge `default_config` + `config_overrides`, validate `context_inputs` present (fail node clearly if not), run executor, merge `context_outputs`, persist a per-node output.
   - After the chain: upsert embeddings to Weaviate if `embeddings`/`text` present in context (reuse current Weaviate upsert calls).
3. **Fix the linkage** — `watcher.py:_make_reconciler()` must read `ws.get("pipeline_ids")` and the reconciler (`reconciler.py:observe_file` ~94) must `ensure_processing_job` **once per assigned pipeline** (loop), falling back to the default pipeline when a workspace has none.
4. **Per-node persistence** — extend `add_model_output` (or add `add_node_output`) in **both** `mongo_pipeline.py` and `memory_pipeline.py` to carry `node_id`, `node_type`, `order` alongside the existing `model_name/version/output_type/payload`.
5. **Seed a default pipeline definition** equal to today's behavior (`object_detection → captioning → embedding`) so existing/empty-workspace jobs keep working; switch `rmq_processor.py` to `DynamicPipeline`.

**Alternatives:**
- **Coexist vs. replace (Recommended: coexist).** Build `DynamicPipeline` beside `DefaultImageAnalysisPipeline`, seed a matching default definition, then flip the worker. Low risk, preserves current behavior. Replacing outright breaks empty workspaces and in-flight jobs.
- **Per-node storage shape.** Reuse `model_outputs` with node metadata (Recommended — minimal) vs. a new `node_outputs` collection (more structure, more migration; over-engineered for now).
- **Pipeline versioning.** Content-hash the node list+configs into `pipeline_version` (Recommended — config edits auto-trigger reprocess via the existing job-uniqueness/version test at `tests/test_filesystem_pipeline.py:102-123`) vs. manual integer bumps (forgettable).

---

## P2 — Search: correctness + performance (independent of P1, can run in parallel)
**Why:** Per-request model loads make semantic search slow; the CLIP image/text mismatch likely makes it *wrong*; hybrid ranking lets keyword always dominate. (Audit §6/§10 P2; Reality Map §2 search.)

**Where / What:**
1. **Fix the CLIP mismatch first (correctness).** Encode text queries with the **same** model family used to embed images: reuse the `ClipModel` wrapper's `embed_text()` (`models/clip.py`) in `SearchService` instead of HuggingFace transformers in `_encode_query()`.
2. **Cache the model.** Load one shared `ClipModel` once (module-level singleton or `lru_cache`); stop reloading per request. Also cache `SearchService` in `dependencies.py` (currently new per request; repo is already `lru_cache`d).
3. **Fix hybrid ranking.** Replace concat-and-sort with **Reciprocal Rank Fusion** over the keyword and semantic ranked lists (robust, parameter-light, no score-scale assumptions).
4. **(Scale, optional)** Push keyword filtering into MongoDB (`$regex` on path + a text index on caption output) instead of pulling 2000 docs into Python; note the regex/index tradeoffs. Not urgent for demo-scale libraries.

**Alternatives:**
- **Model serving.** Process-wide singleton now (Recommended) vs. a dedicated model-service process (future, heavier).
- **Hybrid strategy.** RRF in app code (Recommended) vs. Weaviate **native** BM25+vector hybrid — bigger change, needs text indexed in Weaviate (the `TextEmbedding` class already stores `text`); defer unless RRF proves insufficient.

---

## P3 — Explainable search (builds on existing model outputs; richer after P1)
**Why:** Product pillar 4.4 — users should see *why* a result matched. Today: a bare score badge, and an image-detail page with no provenance. (Roadmap Phase 3; Audit §10 P3.)

**Where / What:**
- **Backend search** (`search_service.py`): attach a structured `match_reason` per result — keyword → matched term(s) + field (path vs caption); semantic → similarity %; hybrid → both. The service already knows the mode and which list produced each hit.
- **Image detail** (`routes/images.py` `/detail` + `pages/ImageDetails.js`): return and render full provenance from `model_outputs`/`pipeline_runs` — `model_name`, `model_version`, `output_type`, `created_at`, `pipeline_id/version`, embedding presence. Add an "Analysis / provenance" panel.
- **Search cards** (`views/SearchView.js`): render why-matched chips (matched term, similarity %, top detected objects).

**Alternatives:** Minimal (mode label + score) vs. full per-signal breakdown. Recommended: ship the structured `match_reason` from the backend, render progressively on the frontend.

---

## P4 — First new high-value nodes: OCR + EXIF/metadata
**Why:** Notes call OCR the "next highest-value model output"; EXIF/metadata unlocks future search facets. Both also exercise the P1 executor framework with real, non-trivial nodes. (Roadmap §9 #6, Phase 3; Audit §10 P4.)

**Where / What:**
- **OCR node** — `node_type: "ocr"`, inputs `["image"]`, outputs `["ocr_text"]`. New executor + seed entry in `_SYSTEM_NODES`. Add OCR text to the keyword search haystack (cheap, immediate value). Dependency in `requirements.worker.txt` / pyproject `worker` extra.
- **Metadata node** — `node_type: "metadata_extraction"`, inputs `["image"]`, outputs `["metadata"]`. Executor uses Pillow `Image.getexif()` (**no new dependency**) → dimensions, camera, datetime, GPS. Stored for future facet filters.

**Alternatives (OCR engine):** `pytesseract` (light, but needs the system `tesseract` binary — document it) **(Recommended default)** vs. `easyocr` (pip-only, GPU-friendly, heavier download). Search integration: fold OCR text into keyword now vs. a dedicated OCR-aware index later (defer).

---

## Cross-cutting: testing
Every phase extends the existing `unittest` + `InMemoryPipelineRepository` pattern; keep the in-memory repo in sync with new Mongo methods so executor/pipeline tests need no live infra. Use fake executors/publishers (as `tests/test_filesystem_pipeline.py` already does) to test `DynamicPipeline` deterministically.

## Suggested order
P0 (unblocks contributors, cheap) → **P1 (backbone)** → P3 & P4 (depend on P1) ; **P2 runs in parallel** (independent of P1).

---

## Verification
- **P0:** Follow the new README on a clean checkout; `cd backend && python -m unittest discover tests` is green; `docker compose -f docker-compose.infra.yml up -d` then run the manual end-to-end checklist and confirm a sample image becomes searchable.
- **P1:** Unit-test the registry + `DynamicPipeline` with the in-memory repo and fake executors. Integration: create a pipeline via `POST /pipelines`, assign it to a workspace, drop an image in, and confirm `model_outputs` match exactly that pipeline's nodes (not the hardcoded three). Edit a node config → confirm `pipeline_version` changes and the asset reprocesses (extend the existing version test).
- **P2:** Assert only one CLIP load occurs across many `/search` calls (no per-request `from_pretrained`). Embedding-consistency test: image-embed a picture and text-embed its concept → high cosine similarity (guards the mismatch fix). Unit-test RRF ordering with synthetic ranked lists.
- **P3:** `/search` responses include `match_reason`; `/images/{id}/detail` includes model/pipeline provenance; React Testing Library asserts chips/provenance render.
- **P4:** Executor unit tests for `ocr` and `metadata_extraction`; end-to-end: an image with embedded text becomes findable by that text via keyword search.
