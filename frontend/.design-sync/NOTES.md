# design-sync notes — PixQuery Aperture

## Repo shape

- `frontend/` is a Create React App **application** (react-scripts), not a
  published component-library package. There is no `dist/`, no `main`/`module`/
  `exports` field in `package.json`, and no build script that produces a library
  entry — `npm run build` produces a static app bundle, not something esbuild
  can point at.
- The design system itself is `src/aperture/` (`kit.js` — 27 primitives, `tokens.js`
  — the `AP`/`STATUS` token objects, `aperture.css` — keyframes + a handful of
  utility classes, `blocks.js` — 10 composed pieces, added by this sync). It's
  **plain JavaScript, no TypeScript, no `.d.ts`** anywhere in the repo.
- Consequence: every component's prop contract in `.design-sync/config.json`'s
  `dtsPropsFor` is **hand-written from reading the source**, not extracted by
  ts-morph. If a component's props change, its `dtsPropsFor` entry needs a
  matching manual edit — nothing will flag drift automatically.
- **Do NOT pass `--entry` to `package-build.mjs` for this repo.** `--entry`
  makes the converter treat the given file as an already-built dist entry
  (`resolveDistEntry` returns it immediately), which skips `synthEntry`
  detection entirely — and with `synthEntry` false, the zero-`.d.ts`
  content-scan fallback (`deriveComponentsFromSrc`) never runs, so every
  component silently vanishes (`[ZERO_MATCH] ... tokens-only DS`, "components:
  0" — this is what happened on the first attempt of this sync).
- Instead, `PKG_DIR` (= `<node-modules>/<cfg.pkg>` when `--entry` is omitted)
  must resolve to a real directory containing `cfg.srcDir`. Since this repo
  isn't a real npm package, this sync symlinks it:
  `ln -sfn .. node_modules/pixquery-aperture` (run from `frontend/`) — makes
  `node_modules/pixquery-aperture` point at the repo root. **This symlink is
  gitignored (lives under `node_modules/`) and must be recreated on every
  fresh clone and before every re-sync build** — it does not survive `npm
  ci`/`npm install`, which don't touch unrelated symlinks but also won't
  recreate one that's missing. Command above; verify with
  `ls node_modules/pixquery-aperture/src/aperture/` before building.
- Invocation is therefore just `node .ds-sync/package-build.mjs --config
  .design-sync/config.json --node-modules ./node_modules --out ./ds-bundle`
  — no `--entry` flag. The converter synthesizes its own entry by walking
  `src/aperture/*.jsx` directly; `src/aperture/index.js` (a real barrel file
  this sync also added, `export * from './kit'; export * from './blocks'`,
  for the app's own convenience) plays no role in discovery — it's `.js`, not
  `.jsx`, so the converter's file walk ignores it.
- `AP` and `STATUS` are excluded from the component list via
  `componentSrcMap: {"AP": null, "STATUS": null}` — they're plain token
  objects, not components, but their capitalized names would otherwise be
  picked up by the content scan.
- **`kit.js`/`blocks.js` were renamed to `.jsx`** (`kit.jsx`, `blocks.jsx`) as
  part of this sync — esbuild's default loader only auto-parses JSX in
  `.tsx`/`.jsx` files, not `.js`, and `lib/bundle.mjs` (which sets the loader
  map) is explicitly off-limits to fork. Existing app imports (`from
  '../aperture/kit'`, extension-less) were unaffected — CRA/webpack resolves
  the extension the same way esbuild does. `tokens.js` has no JSX and was left
  as `.js`.
- **Grouping**: none of the 37 components enrich via src-path matching (the
  name→file heuristic assumes one file per component; this repo has ~37
  components across 2 shared files), so every component would otherwise land
  in a single flat "general" group. Fixed via `cfg.docsMap` pointing each
  component at a tiny stub under `.design-sync/component-docs/<Name>.md`
  (frontmatter-only: `category: <Group>`) — the officially-sanctioned path for
  "regroup a component with no real doc" (base SKILL.md §"What the converter
  emits"). Regenerate via `.design-sync/gen-docs.sh` (committed, not
  gitignored) if components are added or regrouped — edit its `write <Name>
  "<Group>"` lines and re-run it, then add the new/changed `docsMap` entries
  to config.json to match.

## Styling idiom — no CSS classes, a JS token object

Aperture does **not** use CSS custom properties, Tailwind, or CSS-in-JS
libraries. Every component styles itself with an inline `style={{...}}` object
built from `AP.*`/`STATUS.*` — plain JS constants imported from `tokens.js`
(colors, gradients, font stacks). `aperture.css` (wired via `cssEntry`) carries
only the handful of effects inline styles can't do: keyframe animations
(`ap-pulse`, `ap-shimmer`, `ap-pulse-dot`), the photo grain/vignette
(`ap-photo`/`ap-vig`), and scrollbar styling (`ap-scroll`).
This is why `AP`/`STATUS` are still exported from the bundle (kit.js's own
`export { AP, STATUS }`) even though they're excluded from the component list —
the design agent needs them to style any custom markup it writes that isn't
already a component.

## Fonts

`Geist` / `Geist Mono` are loaded via a Google Fonts `<link>` in
`public/index.html`, not shipped as `@font-face` anywhere in the repo — there's
nothing for `extraFonts` to copy. Set `runtimeFontPrefixes: ["Geist"]` to
suppress `[FONT_MISSING]` honestly rather than substituting a different font.

**Re-sync risk**: this assumes claude.ai/design's render runtime can reach
`fonts.googleapis.com` itself (the same way this repo's own `index.html` does).
If it can't, every rendered design falls back to system-ui in place of Geist.
Nothing in this sync's own render-check would catch that — it isn't a failure
mode the local Playwright check can see. If component cards in the DS pane look
like the wrong font, this is the first thing to check.

`Inter` also appears in `AP.sans`'s font stack (`'Geist', 'Inter', ...
system-ui, sans-serif`) but — unlike Geist — is never actually served by this
app anywhere (not in the Google Fonts `<link>`, no local file). It's a
pure fallback that in practice never resolves and the stack falls through to
`system-ui`. Suppressed via `runtimeFontPrefixes` alongside Geist rather than
sourcing a real Inter — sourcing it would be over-fixing a family the app
itself doesn't actually rely on.

## Playwright / render check

This repo's own e2e suite already pins `@playwright/test@1.62.1` (chromium
build 1234), and that build is what's cached under `~/.cache/ms-playwright/` on
the machine this sync ran from. Installed the matching bare `playwright@1.62.1`
into `.ds-sync/node_modules` rather than triggering a fresh ~200MB chromium
download — a version drift here will need `browsers.json` re-checked against
whatever's cached (see base SKILL.md §4.1).

## Known render warns

Triaged during the fan-out authoring pass (7 parallel subagents, one per
component group) — none of these are component defects, all legitimate for a
static single-frame screenshot capture:

- **CSS-animated components capture as one still frame.** `Shimmer`,
  `ShimmerCard` (the `ap-shimmer` sweep) and `Bar`'s `pulse` prop (the
  `ap-pulse` sheen) are correct in the bundle but a screenshot can only show
  one point in the animation. If a re-sync's render check flags these as
  "looks static", that's expected — verify by reading the component's `.jsx`
  for the `className="ap-pulse"`/`"ap-shimmer"` rather than re-authoring the
  preview.
- **Emoji glyphs may not render in the headless capture font.**
  `DeleteOutputsBtn`'s trash icon is the literal `🗑` emoji character from the
  component source; in headless Chromium on the machine this sync ran from it
  rendered as a small placeholder box (no color-emoji font installed), not a
  styling defect — button chrome, disabled dimming, and layout all captured
  correctly. Same root cause likely affects any other emoji glyph in kit.jsx
  (`PipelineSection`'s `◇`/`✦`-style marks are plain Unicode symbols, not
  emoji, and rendered fine). **Worth a manual eyeball on the live DS pane**
  once uploaded, in case the same gap exists in claude.ai/design's own
  renderer — that would be a real (if cosmetic) problem, not a local-capture
  artifact.
- **`Kbd`'s "⌘K" story renders as just "K".** The ⌘ glyph came up invisible in
  the same headless capture environment — almost certainly the same
  font-reachability gap as the Geist/Inter note above (system fallback fonts
  often lack the ⌘ codepoint), not a `Kbd` defect. Same "verify on the live DS
  pane" caveat applies.

## Re-sync risks

- **`dtsPropsFor` is hand-maintained.** Every prop contract in this sync came
  from reading `kit.js`/`blocks.js` source directly, not from real types. A
  future prop added to a component (e.g. a new variant on `Chip`) needs its
  `dtsPropsFor` entry updated by hand, or the design agent won't know it exists.
- **`blocks.js` is coupled to the backend's pipeline-state vocabulary.**
  `StatePill`/`ProcessButton`/`PipelineSection`'s `state` values
  (`not_started`/`queued`/`processing`/`completed`/`failed`) and
  `PipelineSection`'s `section` shape mirror `backend/src/services/
  image_service.py`'s `_pipeline_state` states and `ImageDetails.js`'s
  `viewPipelines` mapping (see `frontend/src/pages/ImageDetails.js`). If that
  backend contract changes, the previews' example data — and `dtsPropsFor` for
  those five components — will describe a state machine that no longer matches
  the API, silently.
- **Geist font reachability** — see Fonts section above; unverified.
- Component count in this sync: 27 from `kit.jsx` + 10 from `blocks.jsx` = 37.
- **`ControlHeader` and `Photo` have no intrinsic size** — `ControlHeader` is a
  flex row that stretches to fill its parent (real usage: a full-width page
  header), and `Photo` (`.ap-photo`, `position:relative;overflow:hidden` with
  absolutely-positioned children) sets no width/height of its own — real usage
  always sizes it via a parent grid cell. Their authored previews wrap them in
  an explicitly-sized `<div>` (`width: 640` / `width:220,height:160`) for this
  reason; a future preview edit that drops that wrapper will silently degrade
  to a squeezed or blank card, not an error.

## Re-sync log

- **2026-08-28 — ActBtn: `tone="danger"`, `loading`/`loadingLabel`, real pressed
  state.** Requested via a design template built in Claude Design
  (`templates/act-btn-states`) that documented its own diff ("shipped today"
  vs "not yet in code"). Added to `kit.jsx` as backward-compatible new props
  (no existing call site passed `tone`/`loading` before). `tone="danger"` uses
  `STATUS.err.*` directly for rest; hover/pressed danger shades
  (`rgba(240,86,107,.24)`/`.55`) and the accent/neutral pressed shades have no
  matching tokens in `tokens.js` — inlined as literals in `ActBtn`, consistent
  with how the rest of `kit.jsx` already mixes literals with `AP.*` tokens.
  Added `.ap-spin` keyframe to `aperture.css` for the loading spinner (with a
  `prefers-reduced-motion` stop, matching the existing `ap-pulse`/`ap-shimmer`
  pattern). Wired into two real call sites: `WorkspacesView.js`'s delete
  button (`tone="danger"`) and `PipelineStatsView.js`'s retry buttons
  (`loading`, replacing a hand-rolled `disabled` + `'⟳ …'` text swap).
  **Not wired elsewhere** — other `ActBtn` call sites across `PipelinesView.js`
  / `WorkspaceDetailView.js` were left as-is; revisit if their actions
  (create/apply/edit) later want a loading or danger treatment.
- This re-sync also surfaced (and fixed) `[GRID_OVERFLOW]` on 6 components
  that weren't flagged during the original sync: `ControlHeader`,
  `PipelineSection`, `ShimmerCard`, then (after fixing those three shifted
  the grid) `ActBtn`, `GhostBtn`, `OutputBody`, `OutputCard`. All given
  `cfg.overrides.<Name>: {"cardMode": "column"}` per the standard fix — full
  card width per story, column mode can't re-flag wide by construction. Not a
  regression from the ActBtn change; just never checked full-bundle grid
  layout until this re-sync's full validate pass. If a future re-sync flags
  more components this way, same fix.

- **2026-08-29 — `objColor(task, name, alpha)`: deterministic per-object
  colour, shared by `ObjRow` and the bbox overlay.** Requested via a design
  template (`templates/obj-row-color`) that specified the exact palette (8
  OKLCH hues, L 0.74/C 0.14, stepped ~33°, hue 0-99 reserved to stay clear of
  `STATUS.err`/Ember) and the hashing rule (`task + ":" + name`, not the row's
  index — rows sort by confidence and reshuffle — and not `name` alone, so two
  detectors emitting the same label don't collide). Added to `blocks.jsx`
  (exported alongside `ObjRow`, not `kit.jsx` — it's detection-domain logic,
  living where `aggregateDetections`/`OUTPUT_LABEL` already do). `ObjRow`
  gained a `task` prop (defaults the hash's task half to `'default'` if
  omitted) and now colours its swatch/checkbox-accent/highlight-tint from it
  instead of a fixed Lumen violet; also added the design's adjacent "toggled
  off" fix (row dims to .45 opacity, label strikes through) since it was
  specified in the same template. `OutputBody`'s two `ObjRow` call sites
  (detections, labels) now pass `task={o.model_name}`. `ImageDetails.js`'s
  bbox overlay threads `model_name` onto each flattened detection
  (`det.__task`) and calls the same `objColor` for box stroke/fill/tag colour,
  so a row and its box agree without hovering either one — "one function,
  both sides" per the design's own note.
  **One deliberate deviation from a literal reading of the template:** the
  overlay's hover state keeps the object's own hue (heavier stroke/fill
  opacity) rather than switching to Ember as it did before this change. The
  template didn't specify overlay hover styling explicitly (it only showed
  the box-colour-matches-row-colour end state); swapping to a generic accent
  on hover would have undercut the exact thing the feature is for. Flagged to
  the user in case Ember-on-hover was wanted as an additional layer.
  **Re-sync surprise**: `OutputBody`/`OutputCard` compose `ObjRow` but their
  own `sourceKeys` did NOT change when their `ObjRow` calls gained a new
  `task={...}` prop — the sourceKey recipe tracks a component's own declared
  signature, not full-body edits to JSX it passes to children. Their cards
  still rendered correctly (the shared `_ds_bundle.js` always rebuilds in
  full), confirmed by manually forcing a spot-check capture — but the
  anchor-based diff alone would NOT have caught this on its own. **When a
  child component's new prop is wired up from a parent that passes data the
  parent already had (not a parent API change), manually verify the parent's
  own cards too** — the automated diff can miss it.

## Authoring pass — batch summary

All 37 components were authored via 7 parallel subagents (one per component
group, disjoint sets, each running its own `preview-rebuild.mjs` +
scoped `package-capture.mjs` loop) plus 3 authored solo by the orchestrator
first to calibrate (Dot, OutputCard, PipelineSection). Every one of the 37
components graded `good` on its first capture — no `needs-work` iterations,
no `[STOP]` conditions, no config/global issues surfaced by any batch.
