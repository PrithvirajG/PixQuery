# PixQuery — Product Vision & Roadmap

**Date:** 2026-05-29  
**Status:** Strategy draft based on current repository implementation and external landscape research.

## 1. Product thesis

PixQuery should become the **local-first AI workbench for visual folders**.

The wedge is not “another Google Photos replacement.” Immich and PhotoPrism already serve that category well. PixQuery’s stronger opportunity is to help users point at arbitrary local workspaces, run configurable AI pipelines, and search/inspect/export the resulting visual intelligence.

Short version:

> PixQuery turns folders of images into searchable, explainable, programmable visual knowledge bases.

## 2. Target users

### Primary early users

- AI builders managing image datasets.
- Designers and creative professionals with reference libraries.
- Developers who want a local image intelligence API.
- Researchers organizing visual corpora.
- Privacy-conscious power users with large local photo/image folders.

### Later users

- Small teams with internal visual asset libraries.
- Photographers who want local AI search but do not need full DAM complexity.
- Families only if PixQuery later adds mobile backup, albums, timeline, sharing, and video polish.

## 3. Positioning

### Avoid

- “Self-hosted Google Photos clone.”
- “Photo gallery app.”
- “Backup app.”

### Prefer

- “Local AI image search engine.”
- “Visual workspace intelligence.”
- “Composable computer-vision pipelines for your folders.”
- “Private semantic search for images, screenshots, datasets, and design assets.”

## 4. Product pillars

### 4.1 Local-first privacy

PixQuery should keep images and AI outputs under the user’s control. Cloud integrations can come later, but the core product should work locally or on-premise.

Product implications:

- Clear setup for local Docker.
- No required cloud model calls.
- Explicit path and file access controls.
- Exportable metadata and no lock-in.

### 4.2 Workspace-native organization

Users should not need to import images into PixQuery’s own storage structure. PixQuery watches existing folders and maintains an index.

Product implications:

- Workspaces are first-class.
- Workspace path validation and health checks matter.
- Missing/moved files should be visible.
- Multiple workspaces should be searchable independently or globally.

### 4.3 Composable pipelines

Pipelines are PixQuery’s key differentiator. A pipeline is an ordered chain of AI/CV nodes that transforms an image into metadata, outputs, and embeddings.

Product implications:

- Node library with system and user/custom nodes.
- Visual pipeline builder.
- Per-node config and schema validation.
- Pipeline versioning and reprocessing.
- Per-node logs, timings, outputs, and failures.

### 4.4 Explainable search

Search should not be a black box. Users should see why results matched.

Product implications:

- Show matching caption terms.
- Show semantic similarity score.
- Show detected objects.
- Show OCR hits when added.
- Show faces/people when added.
- Show which pipeline/model produced the signal.

### 4.5 Developer/API friendliness

PixQuery should expose the indexed visual intelligence for other workflows.

Product implications:

- Stable REST API.
- Export JSONL/CSV/sidecar files.
- Webhooks for new outputs/jobs.
- Plugin/custom node SDK.
- CLI for indexing/search/export.

## 5. Current product capabilities

Already present or partially present:

- FastAPI backend.
- React SPA.
- JWT authentication.
- Workspace definitions.
- Pipeline node and pipeline definition storage.
- File ingestion and reconciliation.
- RabbitMQ job queue.
- MongoDB persistence.
- Weaviate embedding store.
- YOLO object detection.
- BLIP captioning.
- CLIP image/text embeddings.
- Keyword, semantic, and hybrid search.
- Search page with workspace filters and similarity threshold.
- Jobs, workspaces, pipelines, and image details routes.

## 6. Strategic roadmap

### Phase 1 — Make the foundation truthful and reliable

Goal: the system should install, run, index, process, and search predictably.

Deliverables:

- Update README and AGENTS.md to match current implementation.
- Add local setup checklist and troubleshooting.
- Add Docker health checks for API, MongoDB, RabbitMQ, Weaviate, worker, and ingestor.
- Add integration test: sample folder → ingest → process → search result.
- Add model caching for semantic query embedding.
- Add workspace scan progress and errors.
- Add admin diagnostics page or endpoint.

Success metric:

- A new developer can clone, start, index sample images, and run search in under 30 minutes.

### Phase 2 — Make pipelines real

Goal: pipeline definitions in MongoDB become executable runtime plans.

Deliverables:

- Node executor interface.
- Registry mapping `node_type` to executor implementation.
- Runtime context object passed node-to-node.
- Per-node output persistence.
- Per-node error persistence.
- Pipeline versioning.
- Reprocess controls by image/workspace/pipeline.
- UI showing pipeline runs and node outputs.

Success metric:

- A user can create a pipeline in the UI, assign it to a workspace, drop in an image, and see outputs generated by that exact pipeline.

### Phase 3 — Own explainable multimodal search

Goal: make search better and more transparent than a generic gallery search.

Deliverables:

- Search-result “why matched” panel.
- OCR node and OCR-aware search.
- EXIF/metadata extraction and metadata filters.
- Better hybrid ranking.
- Saved searches.
- Search facets: workspace, date, extension, model output type, object label, dimensions, camera metadata.
- Optional native Weaviate hybrid search evaluation.

Success metric:

- Users trust results because they can inspect which signals caused each match.

### Phase 4 — Expand model/node ecosystem

Goal: make PixQuery extensible and future-proof.

Deliverables:

- Local model registry.
- Alternative embedding models such as newer CLIP/SigLIP variants.
- Face detection/recognition/clustering node family.
- Perceptual duplicate detection.
- Image classification node.
- LLaVA/VLM description node for richer captions.
- Custom Python node SDK.
- Import/export node packages.

Success metric:

- A power user can add a custom analysis node without forking PixQuery core.

### Phase 5 — Team/on-premise workflows

Goal: support small teams and internal asset libraries.

Deliverables:

- Role-based access control.
- Workspace sharing.
- Audit logs.
- Team-level pipelines.
- Central model worker pool.
- Backup/export strategy.
- Deployment guide for NAS/on-premise servers.

Success metric:

- A small team can run PixQuery on a server and share searchable internal image workspaces safely.

### Phase 6 — Consumer photo features, only if justified

Goal: selectively add consumer-photo features after the workbench core is strong.

Potential features:

- Albums.
- Sharing links.
- Timeline browsing.
- Mobile upload/backup.
- Video support.
- Memories/story generation.
- Geolocation maps.

Decision rule:

- Build these only if they support the core wedge or if user demand clearly pulls PixQuery toward a broader photo app.

## 7. Non-goals for now

- Replacing Immich as a polished family photo backup app.
- Building native mobile apps before the core pipeline/search engine is excellent.
- Supporting every RAW/video format immediately.
- Cloud multi-tenancy before local/on-premise is robust.
- Hiding AI uncertainty. PixQuery should expose confidence, model version, and source output.

## 8. Product risks

### Scope creep

The photo-management category is huge. Avoid albums/sharing/mobile until the pipeline/search wedge is strong.

### Setup complexity

MongoDB + RabbitMQ + Weaviate + Torch + model weights is heavy. Invest early in health checks, docs, sample data, and graceful degradation.

### Model quality variance

BLIP/CLIP baseline models can produce weak captions or misses. Make models swappable.

### Trust and privacy

If PixQuery serves local files over HTTP, validates paths poorly, or stores credentials unsafely, the privacy-first story collapses.

## 9. Recommended immediate next actions

1. Update stale contributor docs.
2. Add sample dataset and smoke-test script.
3. Cache CLIP query model.
4. Implement dynamic pipeline execution MVP.
5. Add result explainability on image detail and search cards.
6. Add OCR node as the next high-value model output.

## 10. One-line north star

**PixQuery should make every local image folder searchable, inspectable, and programmable without sending private media to the cloud.**
