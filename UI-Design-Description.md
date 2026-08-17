# PixQuery — Design Vision & Specification
### A first-principles design system and screen spec, written to be fed to Claude Design

---

## 0. What this document is

This is not a record of what the current app looks like. This is a **fresh design vision** — how PixQuery *should* look and feel, designed from the ground up. It defines the soul of the product (the vibe), the system (color, type, space, motion), and every screen (purpose, content, layout, interaction). It ends with a practical **guide for feeding this to Claude Design** so you can generate the new UI, screen by screen, and then revamp the frontend against it.

Read it top to bottom once. Then use **§10 (the feeding guide)** as your working playbook.

---

## 1. First principles — what PixQuery actually is

Before a single color: *what are we designing?*

PixQuery is a **private, local AI that understands your photos.** You point it at folders on your own machine. It looks at every image — detects objects, reads text, writes a caption, builds a semantic fingerprint — and then lets you find any memory by describing it in plain language. Nothing leaves your computer.

That sentence contains the whole emotional brief. There are **three feelings** the design must produce:

1. **Intimacy & warmth** — these are *your memories*. Browsing them should feel like opening a beautifully made photo box, not querying a database.
2. **Intelligence you can trust** — the magic (semantic search, AI captions) must feel *smart but transparent*. The user should always be shown *why* the AI did what it did, or the magic becomes suspicion.
3. **Calm control & privacy** — it runs on *your* hardware. The product should feel like a private, premium instrument — a darkroom, an observatory — quiet, precise, and entirely yours. Privacy isn't a checkbox; it's an atmosphere.

PixQuery also has a split personality, and the design must hold both halves in one system:
- **The Gallery** (Search, Image Detail) — photographic, warm, content-first, emotional.
- **The Control Room** (Pipelines, Workspaces, Jobs) — technical, precise, data-dense, confident.

The design language below is built to make both feel like the same product.

---

## 2. The vibe

> **One line:** *A private darkroom for your memories — calm and photographic, with intelligence that glows when it works.*

**Mood words:** calm · precise · private · premium · intelligent · tactile · quiet-confidence · cinematic.

**The metaphor:** an **aperture / observatory**. The interface is a dark, recessive instrument. The *light* comes from two sources only — your **photographs**, and **moments of intelligence** (the AI matching, processing, finding). Everything else recedes into deep, cool shadow so those two things glow.

**What it is NOT:** not a flat corporate SaaS dashboard; not neon cyberpunk; not heavy skeuomorphic glass; not a bright white productivity tool. It's closer to *Linear meets a photographer's Lightroom meets a spacecraft HUD* — dark, deliberate, and beautiful.

I'm naming the system **"Aperture"** so every contributor (and Claude Design) has a shared word for the target.

---

## 3. Design principles (the rules the whole system obeys)

1. **Content is the light source.** The chrome is dark and quiet so photos and data are the brightest things on screen. If a UI element competes with a photograph for attention, the UI element loses.
2. **Calm by default, alive on intelligence.** Motion, glow, and color-saturation are *earned* — they appear when the AI is doing something (searching, matching, processing) or when a state is live. A resting screen is still.
3. **One accent, used with discipline.** A single violet→indigo "intelligence" accent carries every primary action and every AI moment. A warm ember accent appears rarely, for human/memory highlights. Discipline here is what makes it feel premium instead of busy.
4. **Explain the magic.** Semantic search must always show *why* a photo matched (caption, text-in-image, visual similarity %). AI outputs always carry provenance (which model, which pipeline). Trust is a feature; transparency is how we earn it.
5. **Depth through translucency, not decoration.** Layering is communicated with soft blur and subtle elevation, never with borders-on-borders or noisy textures. Glass is a tool for hierarchy, used sparingly.
6. **Two moods, one grid.** The Gallery is spacious and image-led; the Control Room is dense and precise. Same tokens, same type, same spacing rhythm — only the information density changes.
7. **Generous, rhythmic space.** An 8pt spatial system. Air around content is a feature, not waste. Crowding reads as cheap.
8. **Progressive disclosure.** Power (custom pipelines, config JSON, RBAC) is always reachable but never shoved forward. A first-time user sees a clean path; a power user finds the depth.
9. **Privacy you can feel.** Reinforce "local · offline · yours" in copy, in the empty states, in the auth screen. It's a core differentiator and an emotional anchor.
10. **Keyboard-first and accessible.** A command palette, logical focus order, visible focus rings, AA contrast on dark, and `prefers-reduced-motion` respect. Speed and inclusivity are part of "premium."

---

## 4. Color system — "Aperture"

The palette is a **cool near-black neutral ramp** ("Carbon") + a **violet→indigo intelligence accent** ("Lumen") + a **rare warm accent** ("Ember") + a tight semantic set + a curated data-viz palette for the technical surfaces.

> Why dark, on principle: a photo app should put photographs against a near-black wall — like a gallery or a darkroom — so color and detail in the images pop. Dark is not a trend choice here; it's the correct frame for the content.

### 4.1 Carbon — the neutral ramp (the "wall")
A near-black with a faint cool/indigo undertone (never a flat gray — the slight blue keeps it premium and photographic).

| Token | Hex | Use |
|---|---|---|
| `carbon-1000` | `#07080D` | Deepest backdrop, behind the canvas; image-detail stage |
| `carbon-950` | `#0A0C14` | **App canvas** (default background) |
| `carbon-900` | `#10131F` | Sticky header, raised panels |
| `carbon-850` | `#161A29` | **Card surface** |
| `carbon-800` | `#1E2333` | Elevated cards, inputs, hover surface |
| `carbon-700` | `#2A3042` | Strong hairline / pressed surface |
| `hairline` | `rgba(120,130,160,0.12)` | Default 1px borders & dividers |
| `hairline-strong` | `rgba(140,150,180,0.20)` | Card borders, focus-adjacent |

### 4.2 Ink — text on Carbon
| Token | Hex | Use |
|---|---|---|
| `ink-high` | `#EDF0FA` | Headings, primary values |
| `ink-mid` | `#A6AEC4` | Body, secondary labels |
| `ink-low` | `#6B7388` | Captions, meta, timestamps |
| `ink-faint` | `#454B5E` | Disabled, placeholder, hints |

### 4.3 Lumen — the intelligence accent (primary)
Violet→indigo. Used for primary actions, active states, focus, links, and **every AI moment** (searching, matching, processing).

| Token | Hex | Use |
|---|---|---|
| `lumen-300` | `#B7A6FF` | Accent text/icons on dark |
| `lumen-400` | `#9B86FF` | Hover text, light accents |
| `lumen-500` | `#7C5CFC` | **Core accent** |
| `lumen-600` | `#6A45F0` | Primary button base |
| `lumen-700` | `#5733D6` | Pressed |
| **Gradient** | `linear-gradient(135deg, #7C5CFC 0%, #5B8DEF 100%)` | Logo, primary CTAs, avatars, hero text |
| **Glow** | `0 0 24px rgba(124,92,252,0.28)` | Active/AI emphasis, focus aura |
| **Tint surface** | `rgba(124,92,252,0.14)` + border `rgba(124,92,252,0.34)` | Active chips, selected rows |

### 4.4 Ember — the warm accent (rare, human/memory)
A soft sunset amber. Reserved for *human warmth*: favorites/stars, a caption flourish, "memory" highlights, the occasional warm data point. Use it on **< 5%** of any screen — its rarity is the point. It provides emotional contrast against the cool Lumen "machine" accent (warm = your memories, cool = the AI).

| Token | Hex |
|---|---|
| `ember-300` | `#FFC79A` |
| `ember-400` | `#FF9E57` |
| `ember-500` | `#F6803B` |

### 4.5 Semantic colors
| Role | Token | Hex | Tint bg |
|---|---|---|---|
| Success / completed / active | `verdant` | `#3FD08B` | `rgba(63,208,139,0.12)` |
| Warning / processing-attention | `amber` | `#F2B23E` | `rgba(242,178,62,0.12)` |
| Danger / failed / destructive | `rose` | `#FF6B6B` | `rgba(255,107,107,0.12)` |
| Info / neutral signal | `azure` | `#5B8DEF` | `rgba(91,141,239,0.12)` |

### 4.6 Data-viz / category palette (the Control Room)
Pipeline node types, job statuses, charts, detection labels. A curated, harmonious set so technical screens stay legible and colorful without clashing:

| Meaning | Color | Hex |
|---|---|---|
| Object detection | Violet (Lumen) | `#7C5CFC` |
| Face detection | Pink | `#F472B6` |
| Segmentation | Indigo | `#818CF8` |
| Classification | Azure | `#5B8DEF` |
| Captioning | Cyan | `#4FD6E0` |
| Embedding (CLIP) | Teal | `#2DD4BF` |
| Grayscale | Slate | `#94A3B8` |
| Compress | Orange | `#FB923C` |
| Crop | Amber | `#FBBF24` |
| Resize | Gold | `#FACC15` |
| Draw boxes | Verdant | `#3FD08B` |

**Job status colors:** queued = Slate `#94A3B8`; processing = Lumen `#7C5CFC` (pulsing); completed = Verdant `#3FD08B`; failed = Rose `#FF6B6B`.
**Role colors:** owner = Ember/amber `#FBBF24`; editor = Azure `#5B8DEF`; viewer = Slate `#94A3B8`.

### 4.7 Detection-overlay colors
Bounding boxes derive a **stable hue per label** (hash the label → HSL ~`hsl(h, 72%, 62%)`) so "dog" is always the same color across images. Boxes glow on hover.

---

## 5. Typography

**Principle:** a confident, slightly geometric display face for personality + a neutral workhorse for UI + a precise mono for the technical truth (paths, IDs, JSON, dimensions).

| Role | Typeface | Notes |
|---|---|---|
| **Display / Headings** | **Geist** (alt: *Space Grotesk* for more character, *General Sans* for softer) | Page titles, hero, big numbers. Tight tracking on large sizes. |
| **Body / UI** | **Inter** | Everything functional. Variable weight. |
| **Mono** | **Geist Mono** (alt: *JetBrains Mono*) | Paths, IDs, JSON, image dimensions, code-like data. |

**Type scale (rem / px @16):**
| Token | Size | Weight | Use |
|---|---|---|---|
| Display | 56–72px | 700 | Landing hero only |
| H1 | 28px / 1.75rem | 700 | Section / page-defining titles |
| H2 | 22px | 650 | Page titles in-app |
| H3 | 18px | 600 | Card / panel headers |
| Body-lg | 16px | 450 | Lead paragraphs |
| Body | 14px | 450 | Default UI text |
| Label | 12px | 600 | Field labels, chips (uppercase, `tracking +0.08em`) |
| Micro | 11px | 600 | Meta, badges, table headers (uppercase) |
| Stat | 36–44px | 800 | Big dashboard numbers (`tabular-nums`) |

**Rules:** numbers that update use `tabular-nums`. Labels are uppercase with letter-spacing. Body line-height ~1.55. Gradient text (`Lumen` gradient, clipped) is reserved for the wordmark and one hero phrase — never for body.

---

## 6. Space, shape, elevation, motion

**Spacing — 8pt system:** `4 · 8 · 12 · 16 · 24 · 32 · 48 · 64`. Card padding 20–24. Section gaps 24–32. The Gallery breathes (more space); the Control Room is denser (12–16) but on the same grid.

**Radii:** small controls 8px · buttons/inputs/chips 12px · **cards 16px** · modals/large panels 20–24px · pills & avatars full.

**Elevation (3 levels, via translucency + blur, not hard shadows):**
- *Flat* — on canvas, hairline border only.
- *Raised (cards)* — `carbon-850`, hairline, faint ambient shadow.
- *Floating (modals/drawers/menus)* — `carbon-900` @ ~92% + `backdrop-blur(20px)`, hairline-strong, soft large shadow `0 24px 60px rgba(0,0,0,0.5)`.

**Glass:** used for the header, overlays, and select cards — `background: rgba(16,19,31,0.7); backdrop-filter: blur(16px)`. Always legible; never decorative.

**Ambient light:** two large, very soft blurred orbs bleed through the canvas — a Lumen violet (top-left) and an Azure (bottom-right), each ~`opacity 0.06`, `blur 140px`, fixed, non-interactive. This is the "observatory" glow. On the landing page it's stronger.

**Motion:**
- Durations: `120ms` (micro hover), `200ms` (default), `320ms` (enter/large). Easing: `cubic-bezier(0.2, 0.8, 0.2, 1)`.
- Reserved motion: AI search → a soft Lumen shimmer; processing → pulsing dot/ring; result cards → gentle stagger-in; image hover → 1.04 scale (500ms); detection box hover → glow.
- Modal/drawer: fade + 8px rise / slide-in. Respect `prefers-reduced-motion` (cut transforms, keep opacity).

**Iconography:** outline, 1.5–2px stroke, `currentColor`, ~20px. One consistent set (Lucide/Heroicons style). No filled or multicolor icons except the brand mark.

---

## 7. Signature elements (the things that make it *PixQuery*)

Design these well and the product has an identity:

1. **The Lumen mark** — a violet→indigo gradient tile "PQ" that subtly glows; the wordmark is gradient-clipped. It's the single most-repeated brand atom.
2. **Match-reason chips** — the trust device. Under every search result, tiny chips explain the match: `in caption` · `text in image` · `92% match`. This is the "explain the magic" principle made visible, and it's unique.
3. **The aperture glow** — ambient orbs + the way active/AI elements emit a soft Lumen aura. The interface literally lights up where intelligence happens.
4. **The node chain** — pipelines drawn as a vertical sequence of color-coded "intelligence modules" connected by flow lines, with live compatibility validation. The Control Room's hero object.
5. **Provenance footer** — on Image Detail, a quiet "Analysis" panel attributing every AI signal to a model/version. Transparency as design.
6. **Command palette (⌘K)** — press from anywhere to search, jump to a workspace, run a scan, switch screens. The keyboard-first soul of the product.

---

## 8. The pages — what they are, what's on them, how they feel

PixQuery is **one shell** + **six surfaces** + a few **cross-cutting moments** (command palette, onboarding, settings).

> Navigation order, by frequency of use: **Search · Workspaces · Pipelines · Jobs**. Image Detail is reached from Search/Jobs. Settings lives under the avatar.

---

### 8.0 App Shell & Navigation — *the frame*

**Feel:** a quiet, fixed instrument frame. The content scrolls; the frame doesn't move.

**Layout:** a slim sticky top bar (`64px`, glass `carbon-900/70 + blur`, hairline bottom). 
- **Left:** Lumen "PQ" mark + "PixQuery" gradient wordmark.
- **Center:** nav as understated pills — Search, Workspaces, Pipelines, Jobs. Active = Lumen tint chip with a faint glow; inactive = `ink-mid`, lightening on hover. Each pill has a small outline icon.
- **Right:** a `⌘K` command-palette hint button, then the user cluster — username + a tiny "Local · Offline" badge (reinforce privacy), and a circular gradient avatar (first initial) opening a menu (Profile/Settings, Sign out).
- **Background:** the canvas + ambient aperture orbs behind everything.
- **Mobile:** nav collapses into a bottom tab bar (thumb-reachable) or a scrollable pill row under the header; the `⌘K` becomes a search icon.

**Cross-cutting: Command palette (⌘K)** — a floating glass panel, autofocused input, fuzzy results grouped into *Search photos · Go to (screens/workspaces) · Actions (scan, new pipeline, new workspace)*. Keyboard-driven, Esc to close. This is a flagship interaction; spec it as a first-class component.

---

### 8.1 Landing & Authentication — *the invitation*

**Feel:** cinematic, confident, privacy-forward. The first 3 seconds must say "private AI that understands your photos." This is the only screen allowed full theatrical weight.

**Content & layout (single, scroll-light hero):**
- **Top bar:** mark + wordmark; light anchor links (How it works · Privacy · Pipelines); a text **Log in** and a gradient **Get started** button.
- **Hero:** a small pulsing eyebrow pill ("Local-first AI photo search"); a Display-size headline where the key phrase is Lumen-gradient — e.g. *"Find any memory by **describing it**."*; a calm sub-paragraph naming the substance (on-device YOLO + BLIP + CLIP, Weaviate vector search, 100% offline).
- **The living proof (signature):** a framed "app window" mockup showing a real query — *"my dog running on the beach at sunset"* — resolving into a small grid of result cards with **match-reason chips and a match %**. This single element teaches the whole product. Let it animate subtly (type the query, results fade/stagger in).
- **Three pillars:** Semantic Search (it understands meaning) · On-device Intelligence (YOLO/BLIP/CLIP run on your hardware) · Absolute Privacy (nothing leaves your machine). Glass cards, restrained icons, hover lift.
- **Quiet footer:** "Runs on your machine. Always."

**Auth:** a **focused glass modal** over a dimmed/blurred hero (not a separate page) — keeps the marketing context. 
- Heading swaps: "Welcome back" / "Create your private library". 
- Fields: Username, Password (show/hide), + Confirm (register). Inputs are deep-inset `carbon-1000` wells with Lumen focus.
- Gradient submit ("Log in" / "Create library"), spinner on submit. Inline ⚠ error banner. A one-line switch between login/register at the bottom.
- Copy reinforces privacy ("Your account stays on this machine").

---

### 8.2 Search — *the heart* (the Gallery)

**Feel:** open a photo box. Spacious, warm-leaning, photographs are the brightest thing. Fast and intelligent. This is the daily screen; it must feel effortless. Default (empty query) = browse the whole library.

**Content & layout:**
- **A commanding search bar** — wide, tall (~56px), centered emphasis, a Lumen magnifier inside, soft focus aura. Placeholder: *"Describe what you're looking for…"*. Autofocused. Blank = browse all. Enter or the gradient button searches; a subtle Lumen shimmer plays while the AI works.
- **A calm filter strip** (always visible, low-key — it should not shout):
  - **Mode** as three segmented pills: **Keyword · Semantic · Hybrid**, each with a one-line tooltip (exact text vs. meaning vs. both). Switching re-searches instantly.
  - **Workspace** scope dropdown ("All sources" default).
  - **Match strength** slider (0–100%) — only enabled for Semantic/Hybrid, gently disabled otherwise, value shown in Lumen.
- **A context line:** *"24 results for 'dog at sunset' · semantic"* or *"Browsing 1–24 of your library."* Keep it light, `ink-low`.
- **The result grid** — responsive **2 → 6 columns**, generous gap. Photographs dominate; chrome is minimal.

**The result card (the atom of the Gallery):**
- Square (or natural-ratio masonry, see below) thumbnail, `object-cover`, gentle hover scale + Lumen border glow.
- Filename (truncated) + optional caption snippet (2 lines, `ink-low`).
- **Match-reason chips** (the signature): `in caption` · `text in image` · `92% match` — tiny Lumen chips that explain *why this matched*. This is the trust moment; make it crisp.
- A whisper of metadata (size). Click → Image Detail.

**Layout choice:** I recommend an **even, calm uniform grid by default** (predictable, gallery-like), with masonry as an optional density mode. Pagination is **load-more / infinite within reason**, with a clear "showing N" — feels like browsing, not paging through a database.

**States:** *Loading* = staggered skeleton tiles (shimmer), not a bare spinner. *Empty (query)* = friendly "Nothing matched 'x' — try Hybrid, or fewer words." *Empty (no library)* = an onboarding nudge: "Your library is empty. Add a source folder to begin." with a CTA to Workspaces. *Error* = inline dismissible banner.

---

### 8.3 Image Detail — *the close-up* (the Gallery, focused)

**Feel:** a museum spotlight. The photo fills a near-black stage; everything else is a quiet rail of intelligence about it. No page scroll — it's an immersive viewer.

**Content & layout (stage + rail):**
- **Top bar:** ← back / breadcrumb filename; on the right, zoom controls `[–] 100% [+]` (25–400%, also ⌘/Ctrl-scroll) and a **Boxes** toggle.
- **The stage (right, dominant):** the image on a `carbon-1000` field, soft shadow, centered. Over it, an **SVG detection overlay** — color-coded bounding boxes (stable per-label hue) with label+confidence pills. Hovering a box glows it.
- **The intelligence rail (left, ~300px, scrolls independently):**
  - **File** — name, size, dimensions, type, last-seen date (mono where technical).
  - **Caption** — the BLIP description, set warmly (this is the "human" reading of the image — a candidate for an Ember touch).
  - **Detections** — a list of rows (color dot · label · confidence%). **Two-way hover**: hovering a row glows its box, hovering a box highlights its row, and the rail auto-scrolls to it. This bidirectional link is a delightful, trust-building detail.
  - **Analysis / Provenance** — the quiet transparency panel: which pipeline (version, status) and which models (`model@version`) produced these signals. Small, mono, `ink-low`. Proof the magic is real.
  - **Path** — full absolute path, mono, wrapped.
- **Hint:** a faint "⌘-scroll to zoom" bottom-right.

**States:** loading spinner on the stage; error → "Couldn't load this image" + back.

---

### 8.4 Pipelines — *the lab* (the Control Room)

**Feel:** a precise, satisfying construction tool. This is where power users compose how images get understood. Dense but legible; color-coded; immediate feedback. The node chain is the hero object.

**Content & layout — two tabs: `Pipelines` | `Node Library`.**

**Pipelines tab (two-pane):**
- **Left rail (~260px):** "＋ New pipeline" (inline name → create), then a scrollable list of pipelines (name + "N nodes"); selected = Lumen tint; hover reveals delete.
- **Right canvas — the editor:**
  - Inline-editable **name** + **description** at the top.
  - **The node chain:** a vertical sequence of **node modules** connected by flow lines. Each module shows: an order index, the node name, a **color-coded type badge** (per §4.6), and the data contract `in: image → out: detections`. If a node needs a context key nothing upstream produced, the module turns **rose-bordered** with a `⚠ needs: detections` badge — **live compatibility validation**. Per-module actions: reorder ↑↓, configure ⚙, remove ✕. Any config overrides show as a small mono tag.
  - A dashed **"＋ Add node"** affordance, then a gradient **Save pipeline**.
- **Add-node modal:** searchable list grouped by category (AI Models · CV Ops). Each option shows the type badge, description, and in/out keys. Incompatible-with-current-chain options are tinted rose with a "needs X" note but still addable. Click to append.
- **Config drawer:** slides from the right. **Phase 1: a clean JSON override editor** showing the node's default config (read-only) above an editable overrides field, with validation. **Design intent / north star:** evolve this into a **schema-rendered form** — sliders for thresholds (e.g. confidence 0.0–1.0), dropdowns for model variants, toggles for booleans — generated from each node's `config_schema`. Design both; build toward the form.

**Node Library tab:** a grid of all nodes (system + custom). Each card: name, description, color-coded type badge, a "system" tag for built-ins, and in/out keys. **System nodes are protected** (no delete). A "＋ New node" inline form creates custom nodes (name, type, inputs/outputs, description, config schema + defaults as JSON).

**Why two tabs:** nodes are a shared library; pipelines compose them. Separating *managing building blocks* from *composing chains* keeps each task focused.

**Future north star (note for the designer):** a horizontal **visual graph canvas** (drag nodes, draw connections) for when pipelines branch. Design the vertical chain now; keep the door open to the canvas.

---

### 8.5 Workspaces — *the sources* (the Control Room)

**Feel:** calm administration. This is where you tell PixQuery *where your photos live*, *what to do with them*, and *who else can see them*. Clear, actionable, never overwhelming. Sharing/RBAC is a first-class concept here.

**Content & layout:**
- **Header:** "Sources" (or "Workspaces") + a gradient **＋ New workspace**.
- **A grid of source cards** (1 → 3 columns). Each card:
  - **Name** + a **status badge** — Active (Verdant, pulsing dot) / Paused (slate). + a **role badge** (owner/editor/viewer) when you're not the owner.
  - **Path** in mono, truncated with tooltip — the most important fact, shown clearly.
  - **Pipelines** as Lumen chips; "no pipeline" reads as a gentle amber warning.
  - **File types** as small mono chips.
  - **Footer:** "Added {date}" + a **Scan now** action (spinner while scanning). Role-gated actions live top-right: **👥 Members** (everyone), **✎ Edit** (owner/editor), **🗑 Delete** (owner) — disabled actions explain why on hover.
  - Active cards carry a 2px Lumen top-accent and a soft hover glow; paused cards dim.

**Create / Edit drawer (right side, ~480px):**
- **Name.**
- **Folder path** — mono input + a **Browse** button that opens a **server-side directory browser** (because a browser can't pick server paths). Hint: "This path lives on the machine running PixQuery."
- **File extensions** — toggle chips (`.jpg .png .webp …`).
- **Pipelines** — multi-select cards (checkbox + name + node count). If none selected: amber note "files will be indexed but not searchable."
- **Active monitoring** toggle.
- Cancel + gradient Create/Save; inline errors.

**Directory browser modal:** breadcrumb of the current server path, an "Up" affordance, folders (clickable, each with a "Select" pill), files shown dimmed/non-interactive, filesystem roots when empty, and a "Use this folder" confirm. Permission errors surface inline.

**Members modal (the sharing surface):** 
- Owner-only **invite by username** with **debounced autocomplete** (suggestions as you type, excluding self/existing members) + a Viewer/Editor role select; selecting grants access **immediately** (no accept step) — frictionless for a local/trusted-team tool.
- A **member list**: avatar + username + role. Owner can change roles inline (Viewer/Editor) and revoke; the owner row and non-owner views are read-only.
- Reinforce the RBAC model visually with the role colors (owner=amber, editor=azure, viewer=slate).

**Empty state:** a warm invitation — "Point PixQuery at a folder of photos to begin" + a single CTA.

---

### 8.6 Jobs & Activity — *the pulse* (the Control Room)

**Feel:** a reassuring system monitor. Answers "is it working? what's done? what failed?" at a glance. Calm when idle; alive (pulsing) when processing.

**Content & layout:**
- **Header:** "Activity" + a Refresh control.
- **A stat row (6 cards):** Total Images (Lumen) · Active Sources (Teal) · Pipelines (Indigo) · Completed (Verdant) · Failed (Rose) · Processing now (Amber, with "+N queued"). Each: a tiny uppercase label, a small color-tinted icon tile, a big `tabular-nums` value, optional subtext. The **Failed** card draws the eye (it's the actionable one); **Processing** pulses when > 0.
- **A recent-jobs table:** columns — **Image/Asset** (a thumbnail + id is ideal; at minimum a truncated id, mono) · **Pipeline** · **Status** (a status pill with a colored, pulsing-when-processing dot) · **Updated** (relative time, sortable) · **Attempts** · a hover **Requeue** action on failed rows. Sortable headers (Lumen ▲/▼ on the active column). A "Last N" selector.
- **Live behavior:** auto-refresh every ~15s *only while* something is processing/queued; otherwise still. **North star:** drive live row transitions over the existing WebSocket so a row glides violet→green when it completes — a satisfying "it's alive" moment.

**Design intent upgrades to spec:** show a **thumbnail** in the asset column and make rows **click through to Image Detail**; add a status **filter**; consider an "activity timeline" alternate view for understanding processing bursts.

**Empty state:** "No activity yet — add a source and run a scan."

---

### 8.7 Settings / Profile — *the quiet corner* (new, recommended)

A small surface under the avatar: account (username, change password), appearance (theme density: comfortable/compact; reduced motion), and a privacy reaffirmation panel (where data lives, that it's offline). Keep it minimal — it exists so the avatar menu has a home and the privacy story has a page.

---

## 9. Cross-cutting specifications

**Responsive:**
| Surface | mobile | sm | md | lg | xl |
|---|---|---|---|---|---|
| Search grid | 2 | 3 | 4 | 5 | 6 |
| Source / node cards | 1 | 2 | — | 3 | 3 |
| Stat cards | 2 | 3 | — | — | 6 |
| Nav | bottom tab bar | bottom/scroll | inline | inline | inline |
| Drawers / modals | full-screen | fixed width | — | — | — |
| Image Detail | rail stacks above stage | split | split | split | split |

**State system (apply to every data surface):**
- **Loading:** skeletons that match the content shape (shimmering tiles for grids, ghost rows for tables); spinners only inside buttons.
- **Empty:** an icon, a one-line headline, a one-line helper, and exactly one CTA toward the next step.
- **Error:** a dismissible inline banner (rose tint) near the action — never only a corner toast.
- **Success:** a transient inline confirmation (≤2s), e.g. "Scan started."
- **Live:** pulsing dots (Verdant = active, Lumen = processing).

**Accessibility:** AA contrast on Carbon (never use `ink-faint` for essential text); visible Lumen focus rings; full keyboard nav (Enter submits, Esc closes, ⌘K opens palette); tooltips on icon-only and disabled controls explaining state; honor `prefers-reduced-motion`.

**Microcopy voice:** calm, plain, quietly confident. Privacy-forward ("on your machine", "offline"). Never jargon-y at the user ("vector cosine" → "visual similarity"), but precise in the Control Room (node types, pipeline versions, attempts). Helpful in empty/error states, never cute to the point of noise.

---

## 10. How to feed this to Claude Design (the playbook)

Claude Design generates UI from descriptions. The way to get a *coherent system* (not six unrelated screens) is to **establish the system first, then generate screens one at a time, then iterate on states.** Work in this exact order.

### Step 0 — Prime the system (do this once, first)
Open Claude Design and paste the **Style Foundation** block below as the very first message. Then ask it to produce a **style tile / component sheet** (color swatches, type specimen, buttons, inputs, chips, a card, a badge set) *before any full screen*. Approve the look here; everything downstream inherits it.

> **STYLE FOUNDATION — paste verbatim, prepend to every screen prompt**
> *Design system "Aperture" for PixQuery, a private, local-first AI photo-search app. Vibe: a calm, premium, cinematic darkroom/observatory — photographs and AI moments are the only light sources; chrome recedes into cool near-black. Background canvas `#0A0C14` (cool near-black with faint indigo undertone); raised panels `#10131F`; cards `#161A29`; inputs/elevated `#1E2333`; hairline borders `rgba(120,130,160,0.12)`. Text: high `#EDF0FA`, mid `#A6AEC4`, low `#6B7388`. Primary accent "Lumen" violet→indigo: core `#7C5CFC`, gradient `linear-gradient(135deg,#7C5CFC,#5B8DEF)`, glow `0 0 24px rgba(124,92,252,0.28)` — used for primary actions, active states, focus, and every AI moment. Rare warm accent "Ember" `#FF9E57` for human/memory highlights only. Semantics: success `#3FD08B`, warning `#F2B23E`, danger `#FF6B6B`, info `#5B8DEF`. Two large soft ambient orbs bleed through the background (violet top-left, azure bottom-right, ~6% opacity, 140px blur). Fonts: Geist (display/headings), Inter (UI/body), Geist Mono (paths/IDs/JSON). 8pt spacing; radii 12px controls / 16px cards / 20–24px modals; depth via translucency + blur, not hard shadows; outline icons 1.5–2px. Motion is calm and earned (120–320ms, ease `cubic-bezier(0.2,0.8,0.2,1)`), reserved for AI/live moments. Numbers use tabular figures; labels are uppercase 12px with letter-spacing. Generate everything dark-first, premium, and spacious.*

### Step 1 — The shell, then the command palette
Generate the **App Shell** (§8.0) first — header, nav, avatar menu, ambient orbs. Approve it. Then generate the **⌘K command palette** as an overlay on the shell. Lock these; they frame every screen.

### Step 2 — Screens, one at a time, in this order
Generate in priority order so the core experience lands first: **Search → Image Detail → Workspaces → Pipelines → Jobs → Landing/Auth → Settings.** For each, paste the Style Foundation + the screen section from §8 (you can paste the section nearly verbatim — it's written to be a prompt). Tell it: *"Generate the default (populated) state of this screen inside the Aperture shell."*

### Step 3 — Generate the states for each screen
After the default state is approved, ask for the **state set** explicitly, one prompt each: *loading (skeletons)*, *empty*, *error*, and any modal/drawer (e.g. "the Members modal", "the directory browser", "the add-node modal", "the auth modal"). Claude Design treats these as variants; generating them separately keeps each clean.

### Step 4 — Iterate with surgical feedback
Don't regenerate wholesale. Give targeted notes: *"keep the layout; make the match-reason chips smaller and move them under the caption"*, *"the node badge colors should follow the category palette: detection=violet, caption=cyan, embedding=teal"*, *"increase spacing between result cards to 16px"*. Reference the **principles** by name when something feels off ("this competes with the photo — content is the light source; calm the card chrome").

### Step 5 — Extract tokens & components for the build
Once approved, ask Claude Design to **export the design as Tailwind tokens / CSS variables and a component list**. That export becomes the contract for the frontend revamp — map each generated component to a React component, wire the real API data (search results + match reasons, node library, workspaces + members, jobs/stats), and replace screen by screen.

### Practical tips
- **Feed real content, not lorem.** Use real example data: query *"my dog running on the beach at sunset"*; node types `object_detection / captioning / embedding`; statuses `queued/processing/completed/failed`; a real-looking path `C:\Users\Alex\Photos\Italy`. Concrete content produces concrete, usable designs.
- **One screen per conversation thread** if it starts drifting — re-paste the Style Foundation to re-anchor.
- **Ask for both desktop and the responsive/mobile variant** of the heavy screens (Search, Image Detail, Pipelines).
- **Name the signature elements** (match-reason chips, node chain, provenance panel, aperture glow, command palette) — they're what make it PixQuery; call them out so they don't get genericized.
- **Hold the line on discipline:** if a generation adds extra colors, gradients, or borders, push back — "one accent, used with discipline."

### Suggested generation checklist
- [ ] Style tile / component sheet approved
- [ ] App shell + nav
- [ ] Command palette
- [ ] Search (default → loading → empty → error)
- [ ] Image Detail (default → loading)
- [ ] Workspaces (grid → create/edit drawer → directory browser → members modal → empty)
- [ ] Pipelines (editor → add-node modal → config drawer → node library → empty)
- [ ] Jobs (default → empty)
- [ ] Landing + auth modal
- [ ] Settings
- [ ] Token + component export for the revamp

---

## 11. Token quick-reference (for the build)

```
/* Carbon (neutrals) */
--carbon-1000:#07080D; --carbon-950:#0A0C14; --carbon-900:#10131F;
--carbon-850:#161A29; --carbon-800:#1E2333; --carbon-700:#2A3042;
--hairline:rgba(120,130,160,.12); --hairline-strong:rgba(140,150,180,.20);
/* Ink (text) */
--ink-high:#EDF0FA; --ink-mid:#A6AEC4; --ink-low:#6B7388; --ink-faint:#454B5E;
/* Lumen (primary accent) */
--lumen-300:#B7A6FF; --lumen-400:#9B86FF; --lumen-500:#7C5CFC; --lumen-600:#6A45F0; --lumen-700:#5733D6;
--lumen-gradient:linear-gradient(135deg,#7C5CFC,#5B8DEF);
--lumen-glow:0 0 24px rgba(124,92,252,.28);
--lumen-tint-bg:rgba(124,92,252,.14); --lumen-tint-border:rgba(124,92,252,.34);
/* Ember (warm accent, rare) */
--ember-300:#FFC79A; --ember-400:#FF9E57; --ember-500:#F6803B;
/* Semantic */
--verdant:#3FD08B; --amber:#F2B23E; --rose:#FF6B6B; --azure:#5B8DEF;
/* Category (pipeline nodes / data-viz) */
--c-detection:#7C5CFC; --c-face:#F472B6; --c-segmentation:#818CF8; --c-classification:#5B8DEF;
--c-caption:#4FD6E0; --c-embedding:#2DD4BF; --c-grayscale:#94A3B8; --c-compress:#FB923C;
--c-crop:#FBBF24; --c-resize:#FACC15; --c-drawboxes:#3FD08B;
/* Radii / spacing */
--r-sm:8px; --r-md:12px; --r-lg:16px; --r-xl:24px; --r-full:9999px;
--space: 4 8 12 16 24 32 48 64; /* 8pt system */
/* Type */
--font-display:"Geist","Space Grotesk",sans-serif;
--font-body:"Inter",sans-serif;
--font-mono:"Geist Mono","JetBrains Mono",monospace;
/* Motion */
--ease:cubic-bezier(.2,.8,.2,1); --dur-micro:120ms; --dur:200ms; --dur-lg:320ms;
```

---

## 12. Navigation map
```
Landing  ──(auth modal: log in / create)──►  App Shell  ( ⌘K command palette everywhere )
                                                 ├── Search        →  Image Detail
                                                 ├── Workspaces    →  Edit drawer · Directory browser · Members modal
                                                 ├── Pipelines     →  Pipelines | Node Library (add-node modal · config drawer)
                                                 ├── Jobs / Activity
                                                 └── avatar → Settings · Sign out
```

## 13. Screen summary
| Screen | Mood | Role | Daily? |
|---|---|---|---|
| Landing + Auth | Cinematic invitation | Convince + enter | Once |
| Search | Gallery, warm, spacious | Find/browse memories | Every day |
| Image Detail | Museum spotlight | Inspect one image + AI signals | Every day |
| Workspaces | Calm administration | Configure sources + sharing | Setup + occasional |
| Pipelines | Precise lab | Compose how images are understood | Setup + power users |
| Jobs / Activity | Reassuring monitor | Watch the system work | When things change |
| Settings | Quiet corner | Account + privacy reaffirmation | Rarely |
```
```
