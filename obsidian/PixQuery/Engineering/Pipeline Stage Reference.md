---
project: PixQuery
type: knowledge-note
created: 2026-09-03
status: reference
---

# Pipeline Stage Reference

The current, complete list of pipeline node types — what PixQuery can actually run today, verified directly against code (2026-09-03), not the 22 proposed-but-unbuilt ones in [[New Pipeline Stage Proposals]].

## Where this list lives (so it never goes stale)

There was no single readable list of this before now — CLAUDE.md names the 9 node types in one dense line, but not what each does or its known issues. This note is the readable version; the **executable source of truth stays in code**, in two places that must agree:

- `backend/src/repositories/pipeline_nodes_repository.py`'s `_SYSTEM_NODES` — name, description, `context_inputs`/`context_outputs`, `config_schema`, `default_config`. Reseeded into MongoDB on every process start.
- `backend/src/services/executors/registry.py`'s `_EXECUTOR_CLASSES` — `node_type` → the `BaseNodeExecutor` subclass that actually runs it. `test_pipeline_stages.py::test_every_seeded_system_node_has_an_executor` fails CI if these two ever drift apart (see [[DAG Branch-Level Parallelism (Tech Debt)]]'s sibling note on that guarantee).

**The live, always-current view** is the Pipelines page in the app itself (`/pipelines` → `GET /pipeline-nodes`) — it renders directly off `_SYSTEM_NODES`, so it can never be stale the way a written doc can. Treat this note as an annotated, human-readable snapshot of that list plus the things the API response doesn't carry (which model/library, known bugs, output shape) — re-verify against the two files above before relying on a detail here past a few weeks old.

## The 9 current stages

| `node_type` | What it does | Model / library | Config honored? |
|---|---|---|---|
| `object_detection` | Bounding-box object detection | Ultralytics YOLOv8n, stock COCO checkpoint (`yolov8n.pt`, 80 classes) | **No** — `model`/`threshold` fields are decorative ([[Stage Model Quality Audit]]) |
| `face_detection` | Face bounding boxes | OpenCV Haar cascade (`frontalface_default`) | Yes — `scale_factor`/`min_neighbors`/`min_size` |
| `classification` | Whole-image top-K labels | torchvision MobileNetV3-Small, ImageNet-1k (1000 classes) | Yes — `top_k` |
| `captioning` | One-sentence natural-language caption | BLIP (`Salesforce/blip-image-captioning-base`) via HF `transformers` | **No** — `model` field is decorative |
| `embedding` | CLIP vector for semantic search | OpenAI's original `clip` package, `ViT-B/32` (smallest CLIP variant) | **No** — `model` field is decorative |
| `resize` | Resize the working image | Pillow only, no model | Yes — `width`/`height` |
| `grayscale` | Convert working image to grayscale (3-channel) | Pillow only, no model | N/A — no config fields |
| `image_write` | Persist the current working image to disk | Pillow file write, no model | Yes — `directory`/`filename`/`format`/`quality` |
| `ocr` | Extract text from the image | Tesseract via `pytesseract` | Yes — `lang` |

## Per-stage detail

### `object_detection` — Object Detection (YOLOv8)
- **I/O:** `["image"]` → `["detections"]`
- **Persisted as:** `model_outputs.output_type = "detections"`, `{detections: [...]}`
- **model_name/version:** `yolo` / `v8n`
- **Known issues:** stock COCO vocabulary has no "tiger" class at all (nearest class: zebra) — see [[Stage Model Quality Audit]] for the full root-cause writeup and fix plan (`yolov8n-oiv7.pt` swap, config wiring).

### `face_detection` — Face Detection
- **I/O:** `["image"]` → `["detections"]` (same shape as object_detection — `label: "face"`, confidence always reported as `1.0` since Haar has no real confidence)
- **model_name/version:** `opencv_haar` / `frontalface_default`

### `classification` — Image Classification
- **I/O:** `["image"]` → `["labels"]`
- **Persisted as:** `output_type = "labels"`, `{labels: [{label, confidence}, ...]}`
- **model_name/version:** `mobilenet_v3_small` / `imagenet1k`

### `captioning` — Image Captioning (BLIP)
- **I/O:** `["image"]` → `["caption"]`
- **Persisted as:** `output_type = "caption"`, `{text}`
- **model_name/version:** `blip` / `image-captioning-base`
- **Known issues:** `-base` is BLIP's smallest checkpoint — short, generic captions. Not yet swapped to `-large`.

### `embedding` — CLIP Embedding
- **I/O:** `["image"]` → `["embeddings"]` (+ `["text_embedding"]` if a `caption` is already in context, for text search)
- **Never persisted to `model_outputs`** — `embeddings`/`text_embedding`/`image`/`asset` are working state (`_PERSIST_SKIP_KEYS` in `pipeline_execution_service.py`); instead upserted straight to Weaviate by `_store_embeddings`.
- **model_name/version:** `clip` / `ViT-B/32`
- **Known issues:** smallest/oldest CLIP backbone (2021). Search-side query encoding (`ClipQueryEncoder`) correctly shares this exact same cached model instance, so there's no image/text space mismatch — the ceiling is model quality, not consistency. See [[Stage Model Quality Audit]].

### `resize` — Resize
- **I/O:** `["image"]` → `["image"]` (working state only — a downstream `image_write` node persists the result if wanted)
- Default `640×640`.

### `grayscale` — Grayscale
- **I/O:** `["image"]` → `["image"]`. Converts to `"L"` mode then back to `"RGB"` so downstream nodes (which expect 3 channels) still work.

### `image_write` — Write Image to Disk
- **I/O:** `["image"]` → `["written_image"]`
- **Persisted as:** `output_type = "written_image"`, `{path, format, width, height}`
- Writes are anchored at `<workspace_root>/pixquery_output/` (fixed this session — previously anchored at the *source file's own folder*, which combined with a live-watcher ingestion gap caused a runaway re-ingestion loop; both are fixed). `directory` config is now a relative *subfolder within* the managed output root, not a replacement for it.
- Never touches the original source file.

### `ocr` — OCR (Tesseract)
- **I/O:** `["image"]` → `["ocr_text"]`
- **Persisted as:** `output_type = "ocr"`, `{text}`
- **model_name/version:** `tesseract` / `pytesseract`

## What's explicitly not here yet

22 additional stage proposals (quality/aesthetic scoring, open-vocabulary detection, color palettes, segmentation, depth, species/scene ID, near-duplicate hashing, API-based VLM annotation, and more) are researched and shortlisted but **not implemented** — see [[New Pipeline Stage Proposals]] for the full catalogue and the top-5 build-first picks. The frontend's `OutputBody` renderer (`aperture/blocks.jsx`) already has cases ready for 9 of those shapes (built 2026-09-03, ahead of their backend executors) so the UI won't need to catch up once each stage lands — see that note's "held back deliberately" callout on why the cross-image Near Duplicates page specifically still needs its backend first.

## Adding a new stage (the actual mechanism)

1. New `BaseNodeExecutor` subclass in `services/executors/builtin.py` — set `node_type`/`model_name`/`model_version`, implement `run(context, config) -> dict`. **Must actually read every field it advertises in `config`** — the three decorative-config bugs above are exactly what NOT to do.
2. Register it in `registry.py::_EXECUTOR_CLASSES`.
3. Add a `_SYSTEM_NODES` entry in `pipeline_nodes_repository.py` (name, description, `context_inputs`/`context_outputs`, `config_schema`, `default_config`) — this is what makes it appear in the pipeline editor UI, with zero frontend code required.
4. **User-created custom node types are currently disabled** (`PipelineNodeCreationDisabledError`, blanket policy as of 2026-09-03) — every new stage today ships as a system node via the steps above, not through the "Add Node" UI (which was removed along with the block).
5. Secrets for an API-based executor go in `config.py` via `os.getenv(...)`, never in the node's Mongo config document.
6. Raise `PermanentNodeError` for unrecoverable config problems (bad/missing API key, unknown model id); let transient failures (timeout, rate limit, 5xx) bubble as ordinary exceptions so the existing job retry (3 attempts, 60/300/900s backoff) handles them.

Related: [[Stage Output UI Plan]] · [[Stage Model Quality Audit]] · [[New Pipeline Stage Proposals]] · [[Backend Architecture Standards]]
