---
project: PixQuery
type: knowledge-note
source: /mnt/d/Projects/PixQuery/docs/engineering/pixquery-architecture-reality-map.md
---

# PixQuery — Architecture Reality Map

**Date:** 2026-05-29  
**Purpose:** Compare the stated product/architecture vision against the current implementation observed in the repository.

## 1. Summary

PixQuery’s architecture is directionally sound. The repository already contains the essential skeleton for a local-first AI image processing system: workspaces, ingestion, jobs, model outputs, vector search, authentication, and a React UI. The largest reality gap is that the product documents and UI describe composable processing pipelines, but the worker still executes a fixed default analysis pipeline.

## 2. Vision vs implementation

### Workspace management

**Vision:** Users define watched folders with file extension filters and assigned pipelines.

**Observed:** Implemented substantially.

Evidence:

- `workspace_definitions` collection.
- `WorkspaceService` and workspace routes.
- `FilesystemReconciler` scans workspace paths.
- Frontend includes `WorkspacesView` and search workspace filter.

Gaps:

- Path mapping across host/WSL/Docker needs stronger documentation and validation.
- Need workspace health/status UI for inaccessible paths, scan progress, and scan errors.

### Pipeline node library

**Vision:** Nodes are modular AI/CV operations with inputs, outputs, config schema, and default config.

**Observed:** Data model exists.

Evidence:

- `pipeline_nodes` collection.
- Seeded system nodes in `MongoPipelineRepository._SYSTEM_NODES`:
  - Object Detection (YOLOv8)
  - Image Captioning (BLIP)
  - CLIP Embedding
  - Face Detection
  - Image Classification
  - Resize
  - Grayscale
  - Draw Bounding Boxes
- `PipelineService` can create/update/delete custom nodes.
- Frontend includes `PipelinesView` route.

Gaps:

- Not every seeded node has an executor implementation.
- No discovered runtime registry tying `node_type` to executable code.

### Pipeline definitions

**Vision:** A pipeline is an ordered chain of nodes with previous/next links and config overrides.

**Observed:** Storage/service layer exists.

Evidence:

- `pipeline_definitions` collection.
- `_build_node_chain()` assigns order and prev/next node IDs.
- `PipelineService` CRUD exists.

Gaps:

- Pipeline definitions are not yet the actual worker execution plan.
- No visible pipeline versioning strategy beyond default constants.
- No per-node run output model yet.

### Ingestion and queueing

**Vision:** New workspace files are detected and queued for asynchronous processing.

**Observed:** Implemented.

Evidence:

- `FilesystemReconciler` scans files, waits for stability, hashes content, creates observations, ensures jobs, publishes job IDs.
- RabbitMQ infrastructure exists in compose files.
- Worker consumer path exists.

Gaps:

- Need scale tests for large directories.
- Need incremental filesystem watcher behavior confirmed against current monitor implementation.
- Need UI visibility into scan state.

### Model processing

**Vision:** User-configured pipeline processes images with selected nodes.

**Observed:** Fixed default pipeline processes images.

Evidence:

- `DefaultImageAnalysisPipeline` runs YOLO, BLIP, and CLIP.
- Outputs are persisted to `model_outputs`.
- Embeddings are persisted to vector store if configured.

Gaps:

- Dynamic pipeline executor not implemented.
- No executor for OCR, face clustering, classification, resize, grayscale, draw boxes in the main run path.
- Need model caching and resource management.

### Search

**Vision:** Keyword, semantic, and hybrid search over indexed library.

**Observed:** Implemented at baseline.

Evidence:

- `SearchService` supports `keyword`, `semantic`, and `hybrid`.
- `SearchView.js` exposes modes, threshold, workspace filter, pagination.

Gaps:

- Semantic query model loads in request path.
- Hybrid ranking is manually merged and likely not robust.
- Keyword search is in-memory over a fixed pool.
- Search does not yet expose rich facets from detections/OCR/faces/metadata.

### User isolation and auth

**Vision:** Per-user data isolation via `owner_id` and JWT auth.

**Observed:** Partially implemented.

> **Update (2026-05-30):** Superseded — isolation is now by **workspace membership** with shareable workspaces and RBAC (owner/editor/viewer), and processing is workspace-scoped. This also fixed a first-writer-wins `owner_id` bug. See [[Workspace Sharing & Access Control]].

Evidence:

- `users` collection.
- Auth routes/security modules exist.
- `owner_id` appears in assets, workspaces, pipelines, nodes, and stats logic.
- Frontend auth context gates dashboard.

Gaps:

- Need security review for every route to ensure owner scoping is consistently enforced.
- Need path authorization: users must not use workspace paths to expose unintended host files.

### UI

**Vision:** Dark glassmorphic UI for search, pipeline manager, workspace manager, jobs, stats/details.

**Observed:** Implemented enough for a strong prototype.

Evidence:

- `App.js` route/nav structure.
- `SearchView.js` mature search UI.
- Design document provides detailed UI direction.

Gaps:

- Need verify all screens are wired to real backend routes and handle empty/error/loading states well.
- Need explainability and pipeline-run detail views.

## 3. Key contradictions to fix

### AGENTS.md drift

Current `AGENTS.md` says:

- Infra: Redis, RabbitMQ, Qdrant.
- API command: `uvicorn src.api.main:app --reload`.

Current implementation shows:

- Infra: MongoDB, RabbitMQ, Weaviate.
- API command in compose: `uvicorn api_main:app --host 0.0.0.0 --port 8000 --reload`.

Impact:

- Future contributors/agents will run incorrect services and commands.

Recommendation:

- Update `AGENTS.md` immediately.

### Pipeline promise vs execution reality

Docs/UI promise configurable pipelines. Worker executes `DefaultImageAnalysisPipeline`.

Impact:

- This is the largest product trust gap.

Recommendation:

- Build dynamic executor MVP before adding many more UI features.

### Vector DB mismatch in historical docs

Some project guidance references Qdrant while compose uses Weaviate.

Impact:

- Confusion around search architecture and dependencies.

Recommendation:

- Decide whether Weaviate is the chosen vector DB. If yes, update all docs. If no, migrate deliberately.

## 4. Proposed dynamic pipeline executor MVP

### Runtime abstractions

```python
class NodeExecutor(Protocol):
    node_type: str
    def run(self, context: dict, config: dict) -> dict:
        ...
```

### Registry

```python
NODE_EXECUTORS = {
    "object_detection": YoloExecutor(...),
    "captioning": BlipExecutor(...),
    "embedding": ClipEmbeddingExecutor(...),
    "resize": ResizeExecutor(),
    "grayscale": GrayscaleExecutor(),
}
```

### Execution flow

1. Worker receives job ID.
2. Load job, asset, assigned pipeline definition.
3. Initialize context: `{ "image": PIL.Image, "asset": asset }`.
4. For each pipeline node in order:
   - Load node definition and config overrides.
   - Validate required inputs are present.
   - Execute node.
   - Merge outputs into context.
   - Persist per-node output or pointer.
5. Persist final model outputs.
6. Upsert embeddings if produced.
7. Complete/fail job.

### Minimal first executors

- `captioning`
- `embedding`
- `object_detection`

Then add:

- `ocr`
- `metadata_extraction`
- `face_detection`
- `duplicate_detection`

## 5. Recommended docs cleanup

Create/update:

- `README.md`: setup, architecture, quickstart, sample images.
- `AGENTS.md`: correct commands and project structure.
- `docs/engineering/pixquery-current-implementation-audit.md`: current reality.
- `docs/product/pixquery-product-vision-roadmap.md`: product direction.
- `docs/research/pixquery-market-technical-analysis.md`: landscape and recommendation.

## 6. Final verdict

PixQuery has a strong architectural core and a clear opportunity, but it must close the pipeline execution gap quickly. The current implementation is best described as a **working local AI image search prototype with pipeline-management scaffolding**. The next major milestone should be transforming that scaffolding into an actual pipeline runtime.
