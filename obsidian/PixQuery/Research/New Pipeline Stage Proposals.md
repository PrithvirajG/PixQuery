---
project: PixQuery
type: knowledge-note
created: 2026-09-03
status: proposal
---

# New Pipeline Stage Proposals

Researched 2026-09-03 (Opus subagent, web-verified against current model cards/licenses/pricing) in response to wanting to open up the executor/node-type system to new *kinds* of stages — not incremental upgrades to the existing YOLO/CLIP/BLIP models (that's tracked separately in [[Stage Model Quality Audit]]), but genuinely new capabilities to test varied, intriguing pipeline workflows. Scope explicitly included both locally-run models and API-key-based hosted models.

22 proposed node types across 7 categories, each with its resource profile and licensing caveats below, plus a consolidated I/O and dependency table at the end. This is a working shortlist, not an exhaustive survey.

## Cross-cutting design notes — read before building any of these

1. **Non-scalar outputs need a home.** Depth maps, segmentation masks, alpha mattes, upscaled images are arrays/images, not JSON. Route a dense pixel output through `"image"` (so `image_write` persists it) or emit a summarized JSON payload (percentiles, a coarse downsample) — never dump a raw array into `model_outputs`. Add any new working-state key to `_PERSIST_SKIP_KEYS`.
2. **A second embedding space is more than an executor.** Every alternative-embedding proposal is a cheap executor and an expensive integration: the Weaviate upsert path, the collection schema, and `ClipQueryEncoder` all assume one vector space today. A second space needs a second Weaviate collection, a second `QueryEncoder`, and a search-mode selector — budget it as a multi-day task, not the hour the executor itself takes.
3. **Cross-image stages don't fit the per-image executor.** Near-duplicate detection and face clustering need per-image *signatures* (a hash, an embedding) from the executor, but the actual grouping is a service + repository query over `model_outputs` — the demoable half isn't the executor.

## Category 1 — New label spaces & semantic understanding

The biggest real gap: COCO's 80 classes and ImageNet's 1000 generic ones are why a tiger becomes a zebra ([[Stage Model Quality Audit]]).

- **`scene_classification_places365`** — Places365 ResNet (local, ~45–100 MB, CPU-fine) classifies the *place* (365 scene categories) + indoor/outdoor + attributes. Zero overlap with existing stages, immediately searchable, cheap gate for expensive downstream stages. Caveat: weights from a plain CSAIL URL, not a versioned hub.
- **`open_vocab_detection_owlv2`** — `google/owlv2-base-patch16-ensemble` (Apache 2.0, ~600 MB–1.7 GB), zero-shot detection where labels come from *config* (`queries: list[str]`). The structurally correct fix for "no tiger class" — one node type, per-workspace vocabulary. Weaker than Grounding DINO on descriptive/color-modified phrases.
- **`species_id_bioclip`** — `imageomics/bioclip` via `open_clip` (~600 MB), fine-grained genus/species ID from TreeOfLife-trained CLIP. Says "Panthera tigris," not "zebra." Needs a gate (only run on detected animals) or it'll confidently misclassify furniture.
- **`region_caption_florence2`** — `microsoft/Florence-2-base/-large` (MIT, ~0.5–1.5 GB), grounded dense captions + phrase grounding + OCR-with-boxes from one checkpoint. Richer than BLIP's flat sentence. Requires `trust_remote_code=True` — pin the revision hash.
- **`vlm_annotate_claude`** (API) — Anthropic Messages API with structured outputs; prompt + schema are config, so one node type covers activity recognition, relationship extraction, album naming, keyword expansion. ~$0.003–0.016/image depending on model tier (Haiku 4.5/Sonnet 5/Opus 5), 2–6s latency. Sends images off-machine — off by default, clearly labelled.

## Category 2 — Quality, curation, aesthetics

Zero coverage today; turns PixQuery from "search" into "cull my 40,000 photos."

- **`image_stats_opencv`** — blur (Laplacian variance), exposure, contrast, brightness, colorfulness. No model, ~0 MB, ~5ms. "Find every blurry/blown-out shot." Caveat: not resolution-normalized — relative signal only, not absolute truth.
- **`aesthetic_score_laion`** — LAION-Aesthetics V2 predictor on CLIP ViT-L/14 (+1.7 GB resident, separate from the existing ViT-B/32). Caveat: audited, documented bias toward saturated/smooth "digital-art" look, under-rates documentary/candid/film-grain photography — label as taste, not quality. `pyiqa`'s MUSIQ is the technical-fidelity alternative if wanted later.

## Category 3 — Safety, moderation, provenance

- **`nsfw_classification_vit`** — `Falconsai/nsfw_image_detection` (~350 MB, CPU-fine). Binary flag for gallery blur/exclude, relevant given shareable RBAC workspaces. No category breakdown; treat as review-flag, never auto-delete.
- **`ai_image_detection_sdxl`** — `Organika/sdxl-detector` (~350 MB). **Weakest proposal on the list**: CC-BY-NC-3.0 (disqualifying if PixQuery ever goes commercial, per [[Cloud SaaS & On-Prem — Scope Exploration]]), accuracy collapses off-SDXL and on edited images, short category shelf-life. Ship experimental-labelled or skip.
- **`safe_search_gcv`** (API) — Google Cloud Vision SafeSearch, 5 graded likelihoods vs. one binary. ~$1.50/1000 units after free tier, 300–800ms. Needs a GCP service-account credential path in `config.py`, not just a key string. Same data-egress consideration as the Claude stages.

## Category 4 — Geometry & pixel-level

- **`depth_estimation_depth_anything_v2`** — Apache 2.0, Small ~100 MB CPU-viable / Large ~1.3 GB. Foreground/background separation, shallow-DOF detection. Needs cross-cutting note 1 (percentiles + downsample, not raw array) before building.
- **`panoptic_segmentation_mask2former`** — Swin-tiny (~180 MB) to Swin-large/ADE20K (~850 MB), segments "stuff" (sky/grass/road) that YOLO structurally can't see; area fractions as search facets. **Check the specific checkpoint's license individually** — Meta research weights on this repo carry mixed terms despite "majority MIT."
- **`subject_matting_birefnet`** — `ZhengPeng7/BiRefNet`, MIT (chosen specifically over the more popular but non-commercial `briaai/RMBG-2.0`), ~900 MB, GPU preferred. Clean cutouts feeding downstream classification/species-ID with a cropped subject.
- **`super_resolution_real_esrgan`** — BSD-3-Clause (cleanest license on the list), tiny weights (~64 MB) but GPU-heavy compute, 16× output file size. Deliberate manual-trigger only, never default ingest. Hallucinates plausible-but-false detail on faces/text — restoration tool, not evidence.

## Category 5 — Signatures, dedup, a second search index

- **`perceptual_hash_phash`** — pHash/dHash via `ImageHash`, no weights, ~10ms. Catches visual near-duplicates SHA-256 dedup structurally misses (resave/resize/messaging round-trip). Executor is trivial; the Hamming-distance grouping service is the actual work (cross-cutting note 3). Not crop/rotation-robust — that needs an embedding approach.
- **`color_palette_kmeans`** — LAB-space k-means, no weights, ~50ms. Dominant colors, warm/cool temperature, color-search, mood boards. Highest delight-per-effort on the entire list.
- **`embedding_siglip2`** — `google/siglip2-base-patch16-224`, Apache 2.0 (explicitly **not** `jinaai/jina-clip-v2` — better model, but CC-BY-NC-4.0). Second text↔image space, directly comparable against CLIP ViT-B/32 for the same query. Full cost is cross-cutting note 2.
- **`embedding_dinov2`** — `facebook/dinov2-base`, Apache 2.0, self-supervised *visual* similarity (no text side at all) — "more like this," not "matches these words." Cheaper to integrate than SigLIP2 since there's no `QueryEncoder`/text side needed. Stay on v2 — DINOv3 has a restrictive Meta license.

## Category 6 — People

- **`face_analysis_insightface`** — InsightFace `buffalo_l` (RetinaFace + ArcFace 512-d embeddings + age/gender), ~330 MB ONNX, CPU-viable via onnxruntime. Enables face clustering — arguably the single most-requested personal-photo-manager feature. **Blocking caveat**: code is MIT but the `buffalo_l` model pack itself is non-commercial research use only. Also: face embeddings are biometric data — deserves explicit opt-in, not default-on. Standalone emotion classifiers are unreliable enough to skip.

## Category 7 — Place & documents

- **`landmark_detection_gcv`** (API) — Google Cloud Vision landmark detection, returns lat/lng for famous landmarks — backfills GPS on photos with stripped EXIF. Same pricing/latency as SafeSearch. Only recognizes famous landmarks — thin coverage outside tourist sites; gate behind an outdoor-scene check to avoid wasting units.
- **`geoestimate_streetclip`** — `geolocal/StreetCLIP` (ViT-L/14, ~1.7 GB), fully local country/region guess from visual cues alone — no data leaves the machine, unlike the GCV landmark option. Same GPS-backfill workflow with global (if fuzzy) coverage instead of landmark-only. Present as a suggestion, never auto-write to GPS fields.
- **`document_extract_claude`** (API) — structured JSON extraction (vendor/date/total/line-items, or business-card fields) from receipts/whiteboards/screenshots — where Tesseract's raw OCR soup ends and queryable structure begins. ~$0.003–0.006/image; gate behind "Tesseract found meaningful text" so cost applies to a small library slice.

**On HF Inference API / Replicate specifically** (asked about explicitly): both are poor fits for bulk ingest. HF Inference Providers' free tier is $0.10/month (PRO: $2/month) — nowhere near enough for a photo library, and it's a routing layer over third-party availability that changes without notice. Replicate has 10–120s cold starts on infrequently-called models, which for a once-per-image stage on a low-traffic personal instance means paying full cold-start latency on most calls. Fine for trying a model before committing to running it locally; not a production ingest path. A dedicated always-warm endpoint is the right shape for hosted GPU inference, not a marketplace.

## Recommendations — build these first (ranked by intriguing-capability-per-effort)

1. **`color_palette_kmeans` + `image_stats_opencv`** (half a day, together) — zero new deps, zero weights, zero memory cost, milliseconds of latency. Color search, mood boards, blur/exposure culling, burst-ranking — and the two stages that most directly change what the gallery UI can do. No license/privacy/reliability risk at all. Do these first even though they're the least glamorous.
2. **`scene_classification_places365`** (half a day) — 45 MB, CPU, one afternoon, an entire second label vocabulary orthogonal to COCO and ImageNet. Also composes as a cheap gate for the expensive stages below.
3. **`open_vocab_detection_owlv2`** (1–2 days) — the structurally correct fix for tiger-becomes-zebra: makes *vocabulary* a per-node config field, so one node type serves a wildlife pipeline, a documents pipeline, a kitchen-inventory pipeline differently. Apache 2.0, output shape matches the existing detection overlay UI for free.
4. **`vlm_annotate_claude`** (1–2 days) — highest variety-per-line-of-code; prompt+schema as config means one node type covers many use cases. Forces the API-stage patterns (env-var keys, `PermanentNodeError` vs. transient classification, structured outputs) to get built properly once, reusable by every future API stage.
5. **`perceptual_hash_phash`** (1 day, mostly service-side) — near-duplicate detection PixQuery structurally can't do today (SHA-256 dedup misses every resave/resize/round-trip). 20-line executor; good forcing function for the cross-image-analysis pattern needed again for face clustering.

**Deliberately not in the top 5:** `depth_estimation`/`panoptic_segmentation` are the most visually impressive but need the non-scalar-output design decision settled first (right second wave). `face_analysis_insightface` is probably the highest user value on the whole list, held back specifically by the non-commercial model license plus the biometric-consent design work it deserves. `embedding_siglip2`'s executor is an hour; its integration is a two-day project — don't schedule it as the former. `ai_image_detection_sdxl` is the one proposal actively advised against as-is (CC-BY-NC, generator-specific accuracy, short shelf-life).

## Implementation reference — I/O contract & dependencies

Every stage takes `["image"]` as its `context_inputs` unless noted. Keys marked † are working state that must be added to `_PERSIST_SKIP_KEYS` rather than written to `model_outputs` (cross-cutting note 1).

| `node_type` | `context_outputs` | New dependency | Local/API |
|---|---|---|---|
| `scene_classification_places365` | `scene_labels`, `scene_attributes`, `indoor_outdoor` | — (torchvision) | Local |
| `open_vocab_detection_owlv2` | `detections` | `transformers` | Local |
| `species_id_bioclip` | `species`, `taxonomy`, `species_confidence` | `open_clip_torch` | Local |
| `region_caption_florence2` | `dense_captions`, `detailed_caption`, `grounded_regions` | `transformers`, `timm`, `einops` | Local |
| `vlm_annotate_claude` | `vlm_annotations` | `anthropic` | API |
| `image_stats_opencv` | `sharpness`, `exposure`, `contrast`, `brightness`, `colorfulness` | — (opencv) | Local |
| `aesthetic_score_laion` | `aesthetic_score` | `open_clip_torch` | Local |
| `nsfw_classification_vit` | `nsfw_label`, `nsfw_score` | `transformers` | Local |
| `ai_image_detection_sdxl` | `ai_generated`, `ai_generated_score` | `transformers` | Local |
| `safe_search_gcv` | `safe_search` | `google-cloud-vision` | API |
| `depth_estimation_depth_anything_v2` | `depth_stats` (+ `image`†) | `transformers` | Local |
| `panoptic_segmentation_mask2former` | `segments` | `transformers`, `scipy` | Local |
| `subject_matting_birefnet` | `subject_mask_stats` (+ `image`†) | `transformers`, `timm` | Local |
| `super_resolution_real_esrgan` | `image`† | `realesrgan`+`basicsr`, or `onnxruntime` | Local |
| `perceptual_hash_phash` | `phash`, `dhash` | `ImageHash` | Local |
| `color_palette_kmeans` | `palette`, `dominant_color`, `color_names`, `temperature` | — (or `scikit-learn`) | Local |
| `embedding_siglip2` | `embeddings_siglip2`† | `transformers` | Local |
| `embedding_dinov2` | `embeddings_dinov2`† | `transformers` | Local |
| `face_analysis_insightface` | `faces`, `face_embeddings`† | `insightface`, `onnxruntime` | Local |
| `landmark_detection_gcv` | `landmarks`, `web_entities` | `google-cloud-vision` | API |
| `geoestimate_streetclip` | `geo_estimate` | `transformers` | Local |
| `document_extract_claude` | `document_fields`, `document_type` | `anthropic` | API |

**Config fields that must actually be honored** (per the decorative-config bug in [[Stage Model Quality Audit]] — declaring a `config_schema` field the executor ignores is a correctness bug, not a nicety). The load-bearing ones: `open_vocab_detection_owlv2.queries` and `geoestimate_streetclip.candidates` (the entire point of those nodes), `vlm_annotate_claude` / `document_extract_claude`'s `prompt` + `output_schema` (the node *is* its config), and every stage's threshold/`top_k`. Where a field would imply swapping the underlying model, drop the field — constraint: one model per node type, since executors are cached per `node_type` for the worker's lifetime.

**API-stage error discipline** (both Claude stages, both GCV stages): missing/invalid API key, unknown model id, and malformed-request errors → `PermanentNodeError` so the job fails immediately; timeouts, rate limits, and 5xx bubble as ordinary exceptions into the existing 3-attempt / 60-300-900s retry policy. Keys come from env vars via `config.py`, never the per-node Mongo config document, which is API-visible.

## Status

Proposal only — nothing implemented. Awaiting a decision on which stage(s) to build first.

Related: [[Pipeline Stage Reference]] · [[Stage Model Quality Audit]] · [[DAG Branch-Level Parallelism (Tech Debt)]] · [[Market & Technical Landscape Analysis]]
