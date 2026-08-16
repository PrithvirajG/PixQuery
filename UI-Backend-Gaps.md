# Aperture UI → Backend Feature Gaps

The frontend now implements the Aperture hi-fi design (claude.ai/design project "PixQuery").
Everywhere the backend already had the data, the UI is wired to it. The items below are
the features the design calls for that the backend cannot serve yet, in rough priority
order. Each gap notes where the UI currently degrades gracefully.

## 1. Per-workspace / per-pipeline job statistics endpoint

**Design needs:** Workspace cards (image count, index coverage, health, last-job outcome,
storage), the Workspace Detail stat strip, and the Pipeline Statistics counters.

**Today:** `/stats/overview` is global and `/stats/jobs/recent` is a flat recent-jobs
list. The UI polls `/stats/jobs/recent?limit=500` and aggregates client-side — correct
only within the recent window, and heavy.

**Suggested:** `GET /workspaces/{id}/stats` returning
`{image_count, storage_bytes, coverage, per_pipeline: {pipeline_id: {queued, processing,
completed, failed, last_updated}}}` via a Mongo aggregation over `processing_jobs` +
`image_assets`. The workspace list endpoint could embed a summary of this per card.

## 2. Match-reason / result grouping in search

**Design needs:** Every result carries a semantic match-reason chip ("golden hour · 96"),
and results can be **grouped by reason** into collapsible sections.

**Today:** `match_reason` exposes matched fields (filename/caption/ocr) and a similarity
score — the chip works but shows "in caption · 84" rather than a semantic label. Grouping
is done client-side by that coarse label.

**Suggested:** Have the search service derive a reason label per hit (e.g. the matched
caption n-gram, top detected object, or nearest-cluster label from embeddings) and
optionally return `groups: [{label, score, asset_ids}]` for grouped mode.

## 3. Pipeline outputs grouped by pipeline in image detail

**Design needs:** The detail rail groups outputs **by the pipeline that produced them**
(name + #id + task + model), because two pipelines can run the same task with different
models. Every payload type should be renderable (palette, OCR text, metadata…).

**Today:** `/images/{id}/detail` returns a flat `description` + `detections` and a
provenance list **without payloads** and with only the *latest* run's pipeline id. The UI
reconstructs sections per output type and marks other outputs "payload not exposed".

**Suggested:** Return
`pipelines: [{pipeline_id, pipeline_name, pipeline_version, outputs: [{output_type,
model_name, payload, node_type, created_at}]}]` by joining `model_outputs` →
`pipeline_runs` → `pipeline_definitions`.

## 4. Find similar (image-to-image search)

**Design needs:** A "✦ Find similar" action on image detail (and "ref: sunset.png"
style reference-image results in search).

**Today:** No endpoint; the button is rendered disabled. The CLIP image embedding is
already in Weaviate, so this is cheap: `GET /images/{id}/similar?top_k=` doing a
nearVector query with the stored vector, excluding the anchor asset.

## 5. Total result count + search facets

**Design needs:** "248 results" header; left-rail facets for Type / Date / Color / Tags /
Pipeline that scope the query without re-searching.

**Today:** Search returns only a page slice — the UI shows "24+" style counts. The only
filters are mode/threshold/workspace. Type (mime/extension), date range, dominant color,
tags and pipeline filters need query parameters on `/search` plus supporting data
(color extraction is a pipeline node that doesn't exist yet; tags could come from
detections).

## 6. Live worker telemetry (log stream, now-processing stage, ETA, pause)

**Design needs:** Pipeline Statistics shows a `tail -f` live log, the exact stage the
current image is on, throughput/ETA, and a Pause control.

**Today:** Workers report nothing mid-job; the UI polls job documents and renders an
"activity feed" from status transitions. Pause is rendered disabled.

**Suggested:** Workers publish progress/log events (RabbitMQ fanout or Mongo capped
collection) keyed by `(workspace_id, pipeline_id)`; API relays via the existing `/ws`
WebSocket. Pause = a flag the reconciler/worker consults before dispatch, plus a
`POST /workspaces/{id}/pipelines/{pid}/pause` route. ETA/throughput can be computed from
completed-job timestamps server-side.

## 7. Bulk retry

**Today:** Only `POST /jobs/{job_id}/requeue`; "Retry all failed" loops requests
sequentially. A `POST /jobs/requeue?workspace_id=&pipeline_id=&status=failed` bulk
endpoint would make this atomic.

## 8. Image dimensions in asset metadata

**Design needs:** FILE INFO shows dims (`4032 × 3024 · 12 MP`).

**Today:** `image_assets.metadata` doesn't reliably carry width/height (only if a
`metadata_extraction` node ran and the API exposed it). The UI falls back to the
browser's naturalWidth/Height of the thumbnail. Cheap fix: record width/height at
ingestion time in the reconciler.

## 9. Storage size per workspace

**Design needs:** Workspace cards show total storage ("38.2 GB").

**Today:** Not aggregated anywhere; part of the `GET /workspaces/{id}/stats` proposal
(sum of `size_bytes` over active assets).
