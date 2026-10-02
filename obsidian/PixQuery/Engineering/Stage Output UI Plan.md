---
project: PixQuery
type: knowledge-note
created: 2026-09-03
status: decided
---

# Stage Output UI Plan

How every pipeline node's output becomes a legible, on-brand visualization — the convention, the exact component contracts, the full payload spec for all 16 current `output_type`s, and the Near Duplicates requirements. Written 2026-09-03 after building the 11 new render cases; decisions below were confirmed the same day.

Related: [[Pipeline Stage Reference]] · [[Stage Model Quality Audit]] · [[New Pipeline Stage Proposals]]

## Summary

Every stage's output is rendered by `OutputBody` (`frontend/src/aperture/blocks.jsx`), dispatching on its `output_type` string — one visual pattern per output *shape*, reused across every stage that shares that shape, not one bespoke screen per model. Anything without a dedicated case falls back to plain text rather than breaking, so backend and frontend ship independently in either order. As of this doc: **16 output types have a real rendering case** (5 original + 11 built 2026-09-03, ahead of their backend); **0 of the 11 new ones have live data yet** — backend build order follows the earlier top-5 pick (see [[New Pipeline Stage Proposals]]).

## 1. The plan — conventions

1. **Dispatch on `output_type`, not on the stage.** A stage persists its result to `model_outputs` under some `output_type` key. `OutputBody` branches on that key. Two stages that happen to produce the same shape (any future bbox detector, say) share one rendering case for free.
2. **One pattern per shape, built from existing primitives.** A scalar score gets the metric-tile pattern. A list of confidence-scored items gets `ObjRow` + `Meter` — already shared by `detections`, `labels`, and now `open_vocab_detections` and `species`. New patterns compose `AP`/`STATUS` tokens and existing blocks (`Eyebrow`, `Muted`, `objColor`) rather than inventing new visual language per stage.
3. **No dedicated case yet? It still renders.** The fallback (`Muted`, "Output recorded") means a backend stage can ship before its UI pattern exists — and did, in the other direction, this week: 11 patterns exist with zero backend behind them. Neither side blocks the other.
4. **Shape-sharing extends beyond the card.** The bbox overlay on the image itself was keyed to `output_type === 'detections'` only; open-vocabulary detection produces the identical shape, so the overlay's filter now checks either type (`ImageDetails.js`). One overlay, two producers — the pattern, not the pipeline, decides what draws.
5. **A stage that leaves the device says so.** `OffDeviceBadge` is one shared component, not per-stage copy — see the naming decision below.
6. **Node config vs. node output are two different rollout speeds.** A new stage's *existence* (name, config fields, its slot in the pipeline editor) appears automatically — the editor fetches the node library live from the backend. Its *output* rendering is the part that needs an explicit `OutputBody` case. Shipping a stage doesn't imply shipping its visualization the same day, and that's fine by design.
7. **Cross-image views are a different mechanism entirely.** Everything above is one `StageCard` rendering one image's one stage. Near Duplicates groups *across* images — its own route, its own nav entry, a real backend aggregation to query, not a new `output_type` case. Spec'd below, deliberately not wired into the app yet — a nav item pointing at no data is worse than no nav item.

## 2. Component contracts

All in `frontend/src/aperture/blocks.jsx` unless noted. A new stage's UI is built *from* these, not beside them — reach for a new primitive only when none of these fit the shape.

**`StageCard`** — the chrome every stage renders inside:
```
StageCard({
  index, total,          // "index/total" badge, e.g. "3/5" — only shown when total > 1
  name,                  // stage label, e.g. outputLabel(o)
  icon,                  // e.g. outputIcon(o) — 13px inline SVG, tinted lumenSoft when shown
  trailing,               // right-aligned mono text, e.g. "model_name · model_version"
  hidden = false,        // collapses to header-only; body unmounts, not just visually hidden
  onToggleHidden,        // wired to the header's EyeBtn
  children,              // the stage's OutputBody — only rendered when !hidden
})
```

**`OutputBody({ o, detectionState })`** — the dispatcher; one new stage means one new branch here:
```
// o = the persisted model_outputs row for this stage:
{
  output_type: string,      // the dispatch key — see section 4 for every current shape
  model_name: string,
  model_version: string,
  payload: object,           // shape depends entirely on output_type — aliased "p" inside each branch
  order: number,
  summary?: string,          // used only by the unmatched-type fallback
}
// detectionState is only meaningful for a bbox shape (detections /
// open_vocab_detections) — wires each row's checkbox + hover to the
// image overlay. Omit it and the same rows render read-only.
{ hiddenLabels: Set<string>, toggleLabel(name), hoveredLabel: string|null, setHoveredLabel(name) }
```

**Shared primitives already built — reuse before inventing:**
```
Meter({ v })                          // v: 0–1 → bar + numeric readout, e.g. confidence
ObjRow({ name, n, c, task, checked, onToggle,
        onHoverEnter, onHoverLeave, highlighted })  // one confidence-scored row; n = repeat count
objColor(task, name, alpha?)          // deterministic oklch hue, keyed by "task:name" — same hue
                                        // used by a row's swatch and its overlay box
Eyebrow({ children, c, style })       // small mono tracked label — section/field headers
Muted({ children })                   // dim helper/empty-state text
OffDeviceBadge({ provider })          // "via {provider}" pill — any API-based stage carries this
```

## 3. Design tokens

From `frontend/src/aperture/tokens.js` — the complete set. Anything built for this system should draw only from these, never a new hex.

**Surfaces & ink:** void `#06070d` · base `#0b0d15` · panel `#11131d` · card `#171a26` · cardHi `#1d2130` · ink `#edeff7` · ink2 `#a4a9bd` · ink3 `#6c7286` · ink4 `#474d61`

**Lumen (intelligence accent):** lumen `#8b7bf7` · lumen2 `#6366f1` · lumenSoft `#bcb3fc` · lumenBg `rgba(124,108,247,0.13)` · lumenBg2 `rgba(124,108,247,0.22)` · lumenLine `rgba(140,124,247,0.42)` · lumenGrad `linear-gradient(135deg, #8b7bf7 0%, #6366f1 100%)`

**Ember (rare human/memory accent):** ember `#ef9355` · emberBg `rgba(239,147,85,0.15)` · emberLine `rgba(239,147,85,0.45)`

**STATUS (semantic, not the accent):** ok `#46d6a6` · warn = ember · err `#f0566b` · run = lumen · queue = ink2 · idle = ink3

**Type:** sans `'Geist', 'Inter', -apple-system, BlinkMacSystemFont, system-ui, sans-serif` · mono `'Geist Mono', ui-monospace, 'SF Mono', Menlo, monospace`

## 4. Output payload spec

The literal contract each `OutputBody` branch reads today, field for field.

| `output_type` | Shape |
|---|---|
| `caption` | `{ text: string }` |
| `detections` / `open_vocab_detections` | `{ detections: [{ label, confidence, bbox: [x_c,y_c,w,h] }], queries?: string[] }` — `queries` only on the open-vocab variant, shown as chips. Bbox overlay reads both types. |
| `labels` | `{ labels: [{ label: string, confidence: number }] }` |
| `ocr` | `{ text: string }` |
| `written_image` | `{ written_image: { path, width, height, format } }` |
| `image_stats` | `{ sharpness?, exposure?, contrast?, brightness?, colorfulness?: number }` — each ~0–100; grid renders only the fields present. |
| `aesthetic_score` | `{ score: number }` — 0–10 |
| `nsfw_flag` | `{ flagged: boolean, label?: string, score?: number }` — score 0–1 |
| `color_palette` | `{ colors: [{ hex: string }], dominant?: string, temperature?: number }` — temperature -1 (cool) … 1 (warm) |
| `segments` | `{ segments: [{ label: string, area_fraction: number }] }` — fractions of 1, sorted desc |
| `annotations` | `{ fields: { [key]: string \| string[] }, source?: 'api', provider?: string }` — array values render as chips |
| `species` | `{ name: string, confidence?: number, taxonomy?: string[] }` — taxonomy joined with " › " |
| `scene` | `{ labels: [{ label, confidence? }], indoor_outdoor?: 'indoor'\|'outdoor', attributes?: string[] }` |
| `geo_estimate` | `{ candidates: [{ region: string, confidence: number }] }` — top 3 shown, rest dimmed |
| `depth` | `{ median: number }` — 0 (near) – 1 (far). **Only `median` is currently read — no p10/p90 range rendering yet.** |

**Decision:** these 11 new shapes lock in as-is — build backend executors to match this table exactly.

## 5. Current state

| # | `output_type` | Status |
|---|---|---|
| 1–5 | `caption`, `detections`, `labels`, `ocr`, `written_image` | **live** — real backend data renders today |
| 6–16 | `image_stats`, `aesthetic_score`, `nsfw_flag`, `color_palette`, `open_vocab_detections`, `segments`, `annotations`, `species`, `scene`, `geo_estimate`, `depth` | **coded** — pattern correct, no executor producing data yet |
| — | Near Duplicates page | **not started** |

Backend build order (from [[New Pipeline Stage Proposals]]'s top-5): `color_palette_kmeans` + `image_stats_opencv` first (zero new dependencies), then `scene_classification_places365`, `open_vocab_detection_owlv2`, `vlm_annotate_claude`.

## 6. Near Duplicates requirements

Spec'd ahead of its backend so a build has something to target — a cross-image page, not an `OutputBody` case.

**Route & nav:** `/duplicates`, Gallery group (alongside Search) — a browsing view, not a Control Room admin page. New stroke-SVG icon, `kit.js` convention (20×20 viewBox, 1.7 stroke-width).

**Data contract** (endpoint doesn't exist yet — this is the shape it should return):
```
GET /duplicates?workspace_id=&threshold=
→ {
  groups: [{
    group_id: string,             // stable across requests — likely the shared hash prefix
    match_percent: number,         // 0–100, drives the match-pill color: lumen ≥95, ok 80–94
    assets: [{ asset_id, thumbnail_url, relative_path, is_original?: boolean }],
    note?: string                  // e.g. "resave chain", "cropped/reframed" — backend-supplied
  }],
  total_groups: number,
  total_assets: number
}
```

**Actions per group:** "Keep all" (dismiss the group, no data change) and "Review & merge" (opens a picker — no deletion happens without this explicit second step; the grouping alone must never auto-delete anything). The threshold selector controls the `threshold` query param server-side, not a client-side filter.

**Decision:** treated as its own track, not sequenced into the top-5 backend list above — pick up whenever, independent of that order.

## 7. Decisions (2026-09-03)

- **Payload shapes**: lock in as coded (section 4) — no changes before backend work starts.
- **`OffDeviceBadge` provider naming**: standardize on one canonical string **per provider**, not per node type, so every stage from the same provider reads identically — `"Claude"` for any Anthropic-API-based executor (`vlm_annotate_claude`, `document_extract_claude`, ...), `"Google Cloud Vision"` for any GCV-based one (`safe_search_gcv`, `landmark_detection_gcv`). Executors should pass the exact canonical string, not a variant (never `"claude-api"`, `"Claude API"`, etc.).
- **Near Duplicates sequencing**: independent track, not ordered against the top-5 stage list.
