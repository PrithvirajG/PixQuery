---
project: PixQuery
type: knowledge-note
created: 2026-09-02
status: active
---

# Stage Model Quality Audit

Triggered 2026-09-02 by a concrete product bug: a tiger in a test image was labeled "zebra" by the `object_detection` stage, and CLIP-based search results felt inaccurate. Investigated against the actual code (not assumptions) in `backend/src/infrastructure/ml/` and `backend/src/services/executors/builtin.py`.

Parked in favor of this: [[DAG Branch-Level Parallelism (Tech Debt)]] — execution speed doesn't matter if stage output is wrong.

## Finding 1 — root cause of "tiger → zebra": stock YOLO checkpoint has no tiger class

`YoloModel.__init__` (`infrastructure/ml/yolo.py:9`) hardcodes `model_path='yolov8n.pt'` — Ultralytics' stock checkpoint, pretrained on **COCO** (80 classes). COCO's animal classes: `bird, cat, dog, horse, sheep, cow, elephant, bear, zebra, giraffe`. **No "tiger" class exists in COCO at all** — a tiger photo is mathematically forced into the closest of those 80 labels, and a striped four-legged animal maps to `zebra`. Not a detection error; a vocabulary ceiling the model can't cross.

## Finding 2 — bigger problem: "model" and "threshold" config fields are decorative (confirmed bug, not speculation)

`pipeline_nodes_repository.py`'s seeded system nodes advertise real config for three stages, but the executors silently ignore it:

| Stage | Advertised config (`config_schema`) | Executor reads it? |
|---|---|---|
| `object_detection` | `model`, `threshold` | **No** — `ObjectDetectionExecutor.run()` (`builtin.py:31-33`) calls `self._get_model().detect(image=...)` with no config at all. `_get_model()` always builds `YoloModel()` with no args → always `yolov8n.pt`. The `0.5` threshold is never passed to `.detect()`; Ultralytics' own default (~0.25) applies instead — more low-confidence noise than the UI implies. |
| `captioning` | `model` | **No** — `CaptioningExecutor.run()` (`builtin.py:143-144`) always uses `Salesforce/blip-image-captioning-base`. |
| `embedding` | `model` | **No** — `EmbeddingExecutor.run()` (`builtin.py:162-170`) always uses CLIP `ViT-B/32`. |

Confirmed **not** broken (config genuinely read): `classification` (`top_k`), `resize` (`width`/`height`), `face_detection` (`scale_factor`/`min_neighbors`/`min_size`), `image_write` (`directory`/`filename`/`format`/`quality`).

**Practical effect:** the pipeline editor lets a user pick a different object-detection model or tune its threshold — and it silently does nothing. Any attempt to fix the tiger problem through the UI would have failed for a reason invisible from the UI itself.

## Finding 3 — CLIP embedding space is *not* mismatched (an old concern, genuinely fixed) — but the model is CLIP's smallest variant

Checked `SearchService`'s query encoder (`infrastructure/vector_store/query_encoder.py::ClipQueryEncoder`) against the worker's `EmbeddingExecutor` — both route through the same cached `get_clip_model()` singleton (`infrastructure/ml/clip.py`, `lru_cache(maxsize=1)`), so image and text vectors genuinely share one space. The image/text-space-mismatch bug recorded in [[Implementation Task Backlog]] (P2) is confirmed still fixed.

What's *not* fixed: the model itself, `ViT-B/32`, is CLIP's smallest/weakest backbone (OpenAI, 2021). The same `clip` pip package already ships stronger checkpoints usable in-process with no new dependency — `ViT-L/14`, `ViT-L/14@336px` — a materially better retrieval model, gated on the same config-wiring bug as Finding 2 (or a hardcoded swap).

## Recommendation, in order of leverage

1. **Wire `config` through in the three broken executors** (`object_detection`, `captioning`, `embedding`) — cheap, mechanical, makes the existing pipeline-editor UI truthful, and is the prerequisite for changing any model without further code changes.
2. **Swap the default object-detection checkpoint** to `yolov8n-oiv7.pt` (Ultralytics, Open Images V7, 601 classes, **includes "Tiger"**) — drop-in, no new dependency. Trade-off: larger download, somewhat slower inference.
3. **Bump YOLO size** (`n` → `s`/`m`) for accuracy within whatever vocabulary is chosen — pure speed/accuracy trade-off.
4. **Apply the configured confidence threshold** to `.detect()` so low-confidence noise stops leaking through as if it were a real detection.
5. Lower priority: CLIP `ViT-B/32` → `ViT-L/14` for search relevance (bigger model, more VRAM/latency); BLIP `-base` → `-large` for richer captions.

## Status

Findings reported to the user 2026-09-02; implementation not yet started — awaiting a scope decision (config-wiring only vs. also swapping default model checkpoints, given the size/latency trade-offs of the wildlife-vocabulary and larger-CLIP options).

Related: [[Pipeline Stage Reference]] · [[DAG Branch-Level Parallelism (Tech Debt)]] · [[Implementation Task Backlog]] · [[Current Implementation Audit]]
