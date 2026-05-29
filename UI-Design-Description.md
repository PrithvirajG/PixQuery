# PixQuery — UI Design Description
### For Google Stitch / Figma Reference Generation

---

## Preface: What is PixQuery?

PixQuery is a **local-first, AI-powered photo management and search platform**. It runs entirely on your own machine (or on-premise server). You point it at folders of photos, it automatically analyses every image using a configurable chain of AI models, and then lets you search those photos using natural language ("Show me photos of my cat sleeping in sunlight") rather than just filenames.

### Core Mental Model (critical for understanding every page)

Before designing any screen, the designer must internalise three concepts:

**1. Pipeline Node**
A "node" is a single, self-contained AI or image-processing operation. It is the smallest building block.
Examples of node types:
- `object_detection` — runs YOLO, produces a list of detected objects with bounding boxes ("person 92%, cat 88%")
- `captioning` — runs BLIP, generates a human-readable description ("a cat sleeping on a windowsill")
- `embedding` — runs CLIP, converts the image to a 512-dimension vector for semantic search
- `grayscale`, `compress`, `resize`, `crop`, `draw_boxes` — CV utility operations

Every node declares:
- **Inputs** — what it needs from previous nodes in the chain (e.g. `image`, `detections`)
- **Outputs** — what it produces for subsequent nodes (e.g. `caption`, `embeddings`)

Think of a node as a LEGO brick with a defined plug and socket.

**2. Pipeline**
A pipeline is an **ordered, sequential chain of nodes**. Each node passes its result to the next one as an accumulated "context" object. A typical pipeline might be:

```
[Object Detection] → [Captioning] → [CLIP Embedding]
context:  { image }  →  { image, detections }  →  { image, detections, caption }  →  { image, detections, caption, embeddings }
```

Only the final embedding step enables semantic (vector) search. A pipeline with only `captioning` enables keyword search on captions. A pipeline with both enables everything.

**3. Workspace**
A workspace is a **monitored folder** on the server filesystem. When you create a workspace, you specify:
- A folder path (e.g. `C:\Users\Alice\Photos\Vacations`)
- Which file extensions to watch (`.jpg`, `.png`, `.webp`, etc.)
- Which pipeline(s) to run on every new image found in that folder

The background monitor constantly watches that folder. When a new image appears, it queues a job for the worker to process it through the assigned pipeline.

---

## Global Design System

All pages share these constants:

| Property | Value |
|---|---|
| **Base background** | `bg-slate-950` (near-black, #0A0B0F) |
| **Glass cards** | `bg-slate-900/60 backdrop-blur border-slate-800` |
| **Primary accent** | Violet (#8B5CF6 / violet-500) |
| **Secondary accent** | Blue-indigo gradient |
| **Active/focus glow** | `box-shadow: 0 0 24px rgba(139, 92, 246, 0.15)` |
| **Typography** | Inter or Outfit, variable weight |
| **Border radius** | Rounded-2xl (16px) for cards, rounded-xl (12px) for inputs |
| **CSS framework** | Pure Tailwind CSS (no Material UI) |

**Navigation bar**: Sticky, glass, ~56px tall. Left: "PQ" logo (violet gradient wordmark or monogram). Center/Right: nav links (Search, Pipelines, Workspaces, Statistics). Far right: user avatar bubble with dropdown (Sign Out). On mobile: horizontal scrollable pill nav below the header.

---

---

# Page 1 — Login / Signup Page

## Purpose

This is the **entry gate** to PixQuery. Unauthenticated users land here. It needs to do two things simultaneously:
1. Explain what PixQuery is (marketing/onboarding)
2. Let users authenticate quickly

Because PixQuery is primarily a local/self-hosted tool — often installed by a solo developer or technical user — the login page should feel like a **product showcase** rather than a plain form. The first time you open it, you should understand what you're looking at within 3 seconds.

---

## Layout

### Full-page Hero + Centred Auth Modal

The page is a **single full-viewport hero section** with a floating, glassmorphic authentication card anchored at the vertical/horizontal centre.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│  [Animated mesh-grid background — dark slate with subtle violet glow]   │
│                                                                         │
│                     PixQuery  ←─ top-left logo                          │
│                                                                         │
│     ┌────────────────────────────────────────────┐                      │
│     │           [Glass Auth Card]                │                      │
│     │                                            │                      │
│     │  🔍  PixQuery                              │                      │
│     │  AI-powered photo search                   │                      │
│     │                                            │                      │
│     │  ┌──────────────────────────────────────┐  │                      │
│     │  │  [ Sign In ]  [ Create Account ]     │  │  ← tab toggle        │
│     │  └──────────────────────────────────────┘  │                      │
│     │                                            │                      │
│     │  Username  ________________________        │                      │
│     │  Password  ________________________        │                      │
│     │                                            │                      │
│     │  [ Sign In ────────── violet btn ]         │                      │
│     │                                            │                      │
│     │  Error message (if any) ← red inline       │                      │
│     └────────────────────────────────────────────┘                      │
│                                                                         │
│     [Feature cards row — below the auth modal]                          │
│     ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │
│     │ Local AI     │  │ Semantic     │  │ Your Data    │               │
│     │ Pipelines    │  │ Search       │  │ Stays Local  │               │
│     └──────────────┘  └──────────────┘  └──────────────┘               │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Component Breakdown

### Background
- Full-viewport dark gradient: `slate-950` → `slate-900`
- Layered on top: animated **mesh-grid SVG** (fine grid lines, ~40px spacing, 5% opacity)
- Radial violet/indigo glow centred behind the auth card (subtle, ~30% opacity, ~600px diameter)
- Optional: slowly drifting particles or subtle grid animation to feel "alive" (low-intensity)

### Auth Card
- Width: 440px on desktop, full-width - 32px on mobile
- Background: `bg-slate-900/80 backdrop-blur-xl`
- Border: `border border-slate-800`
- Shadow: `shadow-2xl shadow-black/50`
- Border radius: `rounded-2xl` (16px)
- Padding: 32px

**Inside the card (top to bottom):**

1. **Icon + Product name** (centred): A violet/blue gradient icon (magnifying glass or grid) + "PixQuery" bold heading + short tagline ("AI-powered local photo search")

2. **Tab toggle — Sign In / Create Account**:
   - Two tabs, full-width, pill-shaped toggle style
   - Active tab: `bg-violet-600` with white text
   - Inactive: `bg-slate-800` with muted text
   - Switching tabs swaps the form fields with a fade/slide animation
   - **Rationale**: A tab toggle (not separate pages) keeps the UX compact for a self-hosted tool where users register once and then primarily sign in. No need for a full separate route per auth mode.

3. **Form fields (Sign In mode)**:
   - `Username` text input
   - `Password` input with show/hide toggle
   - "Remember me" checkbox (optional, lower priority)

4. **Form fields (Create Account mode)**:
   - `Username` text input
   - `Password` input + show/hide toggle
   - `Confirm Password` input
   - On registration, the first user automatically claims all unowned assets (existing database history)

5. **Primary CTA button**: Full-width, `bg-violet-600 hover:bg-violet-500`, rounded-xl, bold text. Shows loading spinner on submit.

6. **Error display**: Inline red banner below the button. Examples: "Invalid credentials", "Username already taken", "Passwords do not match". Should be dismissable.

### Feature Cards (below auth modal)
Three horizontal glassmorphic mini-cards, each ~200px wide:
- **Local AI Pipelines** — icon: CPU chip. Tagline: "YOLO, BLIP, CLIP — run entirely on your hardware"
- **Semantic Search** — icon: magnifying glass with sparkle. Tagline: "Ask in plain English, find with meaning"
- **Privacy First** — icon: shield/lock. Tagline: "Your photos never leave your machine"

These cards are purely informational — they ground the user's understanding of what they just logged into.

---

## Alternative Design Options

**Option A (current, recommended)**: Centred card + hero. Clean, SaaS-standard. Works for both first-time visitors and returning users.

**Option B — Split screen**: Left half: full-height brand/hero with product screenshot. Right half: auth form. More "landing page" feel. Better for public-facing deployments; heavier for a local tool.

**Option C — Minimal**: Just the form, no hero. `slate-950` background, the card, done. Best for internal/enterprise deployments where branding isn't the priority.

---

---

# Page 2 — Search Page

## Purpose

This is the **primary daily-use view**. Once set up, a user opens PixQuery to search their photo library. The page must feel fast, frictionless, and intelligent. A blank query should browse the full library. Any text query should return ranked results.

---

## Layout

```
┌─────────────────────────────────────────────────────────────────────────┐
│  [App header / nav]                                                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│         ┌──────────────────────────────────────────────┐               │
│         │  🔍  Search your photos...                  [⏎] │               │
│         └──────────────────────────────────────────────┘               │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────┐       │
│  │  FILTER BAR (always visible, not collapsible)               │       │
│  │  [Keyword] [Semantic] [Hybrid]  │  Workspace ▾  │  Sim: 0.0 │       │
│  └──────────────────────────────────────────────────────────────┘       │
│                                                                         │
│  "124 images" or "Showing 24 of 350 results for 'cat'"                 │
│                                                                         │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐               │
│  │ img  │ │ img  │ │ img  │ │ img  │ │ img  │ │ img  │               │
│  │ name │ │ name │ │ name │ │ name │ │ name │ │ name │               │
│  │ 92%  │ │ 88%  │ │      │ │      │ │      │ │      │               │
│  └──────┘ └──────┘ └──────┘ └──────┘ └──────┘ └──────┘               │
│  ┌──────┐ ┌──────┐ ┌──────┐ ...                                       │
│  │ img  │ │ img  │ │ img  │                                            │
│  └──────┘ └──────┘ └──────┘                                            │
│                                                                         │
│         [ ← Prev ]  Page 1 of 15  [ Next → ]                          │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Component Breakdown

### Search Bar
- Full-width, prominent, centred in the top section
- Max width ~800px, horizontally centred on the page
- Height: ~56px, larger than a typical input to feel like a "command" bar
- Left icon: magnifying glass (violet tint)
- Right: search submit button or press Enter behaviour
- Focus state: violet glow ring (`ring-2 ring-violet-500/30 border-violet-500/60`)
- Placeholder: "Search your photos…" or "Describe what you're looking for…"
- Autofocused on page load
- Blank query = "browse all" (loads all images paginated)

### Filter Bar (Always Visible, Not Collapsible)
**Design rationale**: Previous iteration had an "Advanced Options" collapsible panel. The decision was to always show filters because: (a) the workspace filter is the primary scoping tool and users need it every session, (b) hiding it behind a click wastes time for the primary user flow. The filters are lightweight and don't clutter the page.

The filter bar is a single horizontal strip below the search bar:

**1. Search Mode Tabs** (far left of filter bar):
- Three pill/segment buttons: `Keyword` | `Semantic` | `Hybrid`
- Keyboard shortcut display optional (Alt+1/2/3)
- Clicking changes mode immediately; on Semantic/Hybrid, the similarity slider activates
- **What they do**:
  - **Keyword**: Fast, exact substring match against file paths and AI-generated captions. No ML needed at query time.
  - **Semantic**: CLIP text encoder converts the query to a vector, searches against Weaviate. Understands meaning: "outdoor scene with greenery" matches forest photos even without that word.
  - **Hybrid**: Runs both, deduplicates, re-ranks by combined score. Best accuracy, slightly slower.

**2. Workspace Dropdown** (middle of filter bar):
- Dropdown with "All Workspaces" default + one option per workspace the user has created
- Selecting a workspace filters results to only images from that folder
- Triggers immediate re-search when changed
- Shows workspace name only (not full path — path is too long for a dropdown item)

**3. Minimum Similarity Slider** (right of filter bar):
- A horizontal slider, range 0.0–1.0, step 0.05
- Only active (not greyed-out) when mode is Semantic or Hybrid
- Default: 0.0 (show everything regardless of score)
- Typical use: set to 0.4–0.7 to filter out weak matches
- Shows numeric value next to slider label: `Min Similarity: 0.45`

### Results Count / Context Line
Thin text row below the filter bar:
- No query, all: "Showing 24 of 847 images in All Workspaces"
- With query: "24 results for "cat sleeping" (keyword)"
- Loading: "Searching…" with a subtle shimmer/pulse
- No results: "No results found for "purple elephant". Try Semantic search for broader matching."

### Image Results Grid
- Responsive grid: 6 columns at 1440px, 4 at 1024px, 3 at 768px, 2 at 480px, 1 at small mobile
- Each card (`ImageCard`):
  - Aspect-ratio 1:1 square thumbnail (object-cover, so images fill the square)
  - Bottom section: filename (truncated with ellipsis), optional caption snippet
  - Top-right corner: similarity score badge for semantic/hybrid mode only (e.g. `92%` in violet pill)
  - Hover: scale-up thumbnail, violet border glow, light box shadow
  - Click: navigates to Image Detail page

### Pagination
- Simple previous/next control + page indicator
- "Page 3 of 15" centred
- 24 images per page (matches PAGE_SIZE = 24 in code)
- Loads new results on page change; scroll to top of results grid

### Empty / Loading States
- **Loading**: Skeleton placeholder cards (grey animated shimmer blocks in the grid positions)
- **Empty**: Centred illustration + helpful message. For blank query with no images: "No images indexed yet. Create a Workspace to start watching a folder."
- **Error**: Red toast or inline banner

---

## Image Detail Page (linked from Search)

When a user clicks an image, they go to `/image/:id`. This is a full-viewport page:

```
┌─────────────────────────────────────────────────────────────────────────┐
│  [Nav header]                                                           │
├────────────────────────────────┬────────────────────────────────────────┤
│                                │                                        │
│  SCROLLABLE SIDEBAR (~320px)   │   FIXED IMAGE CANVAS (fills rest)     │
│                                │                                        │
│  File name (bold)              │  ┌─────────────────────────────────┐  │
│  Full path (mono, small)       │  │                                 │  │
│  Size + MIME type              │  │                                 │  │
│  ─────────────────────         │  │   [ image fills canvas ]        │  │
│  AI Caption                    │  │   + detection bboxes as SVG    │  │
│  "a cat sleeping on a          │  │     overlaid                    │  │
│  wooden windowsill in the sun" │  │                                 │  │
│  ─────────────────────         │  └─────────────────────────────────┘  │
│  Detections                    │                                        │
│  ┌────────────────────┐        │  Zoom: [ - ] 100% [ + ]              │
│  │ ● cat        88%   │        │  [ Toggle boxes ON/OFF ]             │
│  │ ● window     75%   │        │                                        │
│  │ ● sunlight   60%   │        │                                        │
│  └────────────────────┘        │                                        │
│                                │                                        │
│  ← Back to Search              │                                        │
│                                │                                        │
├────────────────────────────────┴────────────────────────────────────────┤
```

Key interactions:
- Hovering a detection row in sidebar → highlights that bounding box on the image (violet glow)
- Hovering a bounding box on the image → highlights the corresponding sidebar row
- Zoom: buttons + Ctrl+scroll wheel (25%–400% range)
- "Toggle boxes" button shows/hides all bounding boxes
- Sidebar scrolls independently; image canvas never scrolls

---

## Alternative Design Options

**Option A (current, recommended)**: Single column, sticky filter bar, paginated grid. Optimised for browsing.

**Option B — Google Photos style**: Infinite scroll (no pagination), date-grouped rows. Better for photo browsing by time; harder to implement server-side efficiently.

**Option C — Split search + results**: Left rail for filters, right area for results (masonry). Gives more filter surface area; useful if more filter dimensions are added (date range, detected object filter, etc.). **Recommended as a future evolution.**

**Option D — Command palette modal**: Press `/` anywhere in the app to open a search command palette. Faster for keyboard-first users. Can coexist with the main search page.

---

---

# Page 3 — Pipeline Management Page

## Purpose

This is the **configuration lab** where users design how their images get analysed. It is more complex than the other pages because it's fundamentally a **visual editor for a processing graph** (sequential chain, not a full DAG, but visually similar). Users who just want the defaults may rarely visit this page. Power users will spend significant time here crafting optimal pipelines.

---

## Context: Why Pipelines Matter

Every image that enters a workspace is processed by a pipeline. The pipeline determines:
- **What gets detected** (YOLO object detection node)
- **Whether captions are generated** (BLIP captioning node — enables keyword search on descriptions)
- **Whether semantic search works** (CLIP embedding node — required for Semantic and Hybrid modes)
- **Whether images are pre-processed** (resize, compress, greyscale before AI runs)

A user might have:
- Pipeline A: `[Resize 1024px] → [YOLO] → [BLIP] → [CLIP]` — full analysis
- Pipeline B: `[Compress 85%] → [CLIP]` — fast indexing for large archives
- Pipeline C: `[Greyscale] → [YOLO]` — just detection, no search

---

## Layout: Two-Tab Page

```
┌─────────────────────────────────────────────────────────────────────────┐
│  [App header / nav]                                                     │
├─────────────────────────────────────────────────────────────────────────┤
│  [ Pipelines ]  [ Node Library ]   ← page-level tabs                   │
├─────────────────────────────────────────────────────────────────────────┤
```

### Tab 1 — Pipelines

```
├────────────────────┬────────────────────────────────────────────────────┤
│  Pipeline List     │  Pipeline Editor (right panel)                    │
│  (~288px wide)     │                                                    │
│                    │  Pipeline name: ______________  [Save]            │
│  + New Pipeline    │  Description:   ______________                    │
│                    │                                                    │
│  ▶ Full Analysis   │  ─────────── Node Chain ──────────────────────    │
│    Pipeline        │                                                    │
│                    │  ┌──────────────────────────────────────────┐    │
│  ▶ Quick Embed     │  │  Node 1: Object Detection [violet badge]  │    │
│    Pipeline        │  │  in: image  →  out: detections, image     │    │
│                    │  │  Config: confidence 0.4   [⚙] [↑] [↓] [✕] │    │
│  ▶ Archive Fast    │  └──────────────────────────────────────────┘    │
│                    │              ↓  (connector arrow)                  │
│                    │  ┌──────────────────────────────────────────┐    │
│                    │  │  Node 2: Captioning       [cyan badge]    │    │
│                    │  │  in: image  →  out: caption               │    │
│                    │  │  Config: model blip-large  [⚙] [↑] [↓] [✕] │    │
│                    │  └──────────────────────────────────────────┘    │
│                    │              ↓                                     │
│                    │  ┌──────────────────────────────────────────┐    │
│                    │  │  Node 3: CLIP Embedding   [teal badge]    │    │
│                    │  │  in: image  →  out: embeddings             │    │
│                    │  │  Config: model clip-vit-b32 [⚙] [↑] [↓] [✕] │    │
│                    │  └──────────────────────────────────────────┘    │
│                    │                                                    │
│                    │  [ + Add Node ]                                   │
│                    │                                                    │
│                    │  ⚠ Warning: Node 2 requires `detections`          │
│                    │    but no node above it provides that key.         │
│                    │  (only shows when chain is incompatible)           │
├────────────────────┴────────────────────────────────────────────────────┤
```

---

## Component Breakdown

### Left Panel — Pipeline List

- Fixed width: ~288px (or `w-72` / 18rem)
- Header: "Pipelines" label + "New Pipeline" button (violet, full-width or top-right)
- Each item: clickable row showing pipeline name + subtle "N nodes" count badge
- Active/selected: violet left border + slightly lighter background
- Right-click or kebab menu (⋮): Rename, Duplicate, Delete
- **Rationale for a persistent left panel** (vs. dropdown/tabs): The user will frequently switch between pipelines to compare or manage multiple. A persistent list makes navigation instant and keeps the full pipeline name visible at all times.

### Right Panel — Pipeline Editor

**Name & Description Inputs** (top of right panel):
- Inline editable text fields for pipeline name and optional description
- Save/update triggers `PUT /pipelines/{id}`
- Unsaved changes indicator (yellow dot or "Unsaved" badge) when edits are pending

**Node Chain** (vertically stacked cards with connectors):

Each node card shows:
- **Node type badge** (colour-coded pill, top-left): `object_detection` = violet, `captioning` = cyan, `embedding` = teal, CV ops = orange/amber
- **Node name** (bold, short): "Object Detection", "Scene Captioning", "CLIP Embedding"
- **Context flow line** (small, below name): `in: image → out: detections, image`
- **Actions (right side of card)**:
  - `⚙` Config icon: opens config drawer
  - `↑` Move up
  - `↓` Move down
  - `✕` Delete node

Between each node card: a small vertical line with a downward arrow (→), representing the data flow. The arrow can optionally show the key being passed (e.g. `detections →`).

**Compatibility Warning Badge**:
- When a node requires a context key (e.g. `detections`) that no preceding node produces, show a red warning badge (`⚠`) on that node card
- Tooltip or inline text: "Node requires `detections` — add an Object Detection node before this"
- The Add Node modal also shows incompatible nodes with a red tint and warning label

**"Add Node" Button**:
- Centred below the last node card
- Opens the Add Node Modal

### Add Node Modal

- Full-screen overlay, centred modal, ~576px wide, max 80% viewport height
- Top: Search input (autofocused) — filters nodes by name and type as you type
- Results: scrollable list of node cards, grouped by category (AI Models | CV Operations | Utilities)
- Each node card in the list shows: name, type badge, brief description, context inputs/outputs
- Incompatible nodes (missing required context key): red-tinted card with ⚠ "Requires `detections` from a previous node"
- Clicking a compatible node adds it to the pipeline immediately

### Config Drawer

- Slides in from the right side (right-side drawer, ~400px wide)
- Shows the node's `config_schema` rendered as a form
- Examples of config fields:
  - Object Detection: `confidence_threshold` (slider 0.0–1.0), `model` (dropdown: yolov8n / yolov8m / yolov8l)
  - Resize: `width` (number input), `height` (number input), `maintain_aspect_ratio` (toggle)
  - Compress: `quality` (0–100 slider)
  - CLIP: `model_name` (dropdown)
- Changes are stored as `config_overrides` on the pipeline node instance (not overwriting the global node definition)
- Save/Cancel buttons at the bottom of the drawer

---

### Tab 2 — Node Library

```
│  Node Library                                         [ + Create Node ] │
│                                                                         │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐        │
│  │ Object Detection│  │ Scene Captioning│  │  CLIP Embedding │        │
│  │ [violet badge]  │  │ [cyan badge]    │  │  [teal badge]   │        │
│  │ System ·        │  │ System ·        │  │  System ·       │        │
│  │ in: image       │  │ in: image       │  │  in: image      │        │
│  │ out: detections │  │ out: caption    │  │  out: embeddings│        │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘        │
│  ┌─────────────────┐  ┌─────────────────┐                             │
│  │ My Custom Node  │  │ + Create Node   │                             │
│  │ [user badge]    │  │                 │                             │
│  │  [Edit] [Delete]│  │                 │                             │
│  └─────────────────┘  └─────────────────┘                             │
```

**Node Library** is a grid of all available nodes:
- **System nodes** (built-in, provided by PixQuery, not deletable): shown with "System" tag
- **User-created nodes**: shown with "Custom" tag, have Edit and Delete buttons
- Grid: 3–4 columns on desktop, 2 on tablet
- Each card: name, type badge, description, input/output keys, source tag
- "Create Node" button (top-right of section or as a grid cell): opens a create node modal
- Create node modal: name, description, node_type (dropdown), context_inputs (multi-tag input), context_outputs (multi-tag input), config_schema (JSON editor with syntax highlighting)

**Rationale for a "Node Library" tab** rather than just inline within the Pipeline editor: The node library is a shared resource — all pipelines reference the same nodes. Managing nodes (creating custom ones, understanding what's available) is a separate concern from composing pipelines. Keeping them on separate tabs prevents cognitive overload.

---

## Alternative Design Options

**Option A (current, recommended)**: Two-tab layout (Pipelines | Node Library). Simple navigation, no nesting.

**Option B — Unified view**: Collapse node library into a side panel within the pipeline editor. Show the full node library in a collapsible right panel while composing a pipeline. Better for power users; potentially overwhelming for new users.

**Option C — Visual flow graph (future)**: Replace the vertical card list with a visual DAG editor (like Retool, n8n, or LangFlow). Each node is a box on a canvas; users draw connections. This is the natural evolution for when pipelines support branching/conditional paths. For the current strictly-sequential model, the vertical list is simpler and clearer.

**Option D — Node search-first**: Instead of a fixed left list, open with a search/browse for nodes and auto-create a pipeline from a template. Better onboarding flow for first-time users.

---

---

# Page 4 — Workspace Definitions Page

## Purpose

Workspaces are the **input configuration** for PixQuery. Without a workspace, no images get indexed. This page is visited primarily during setup and occasionally to add new folders or change which pipeline a folder uses. It needs to be clear and actionable, not overwhelming.

---

## Context Recap

A **Workspace** = watched folder + file extensions + pipeline(s).

When a workspace is active:
1. The monitoring process (`monitoring_main.py`) watches the folder
2. When a new/changed image appears, a job is queued
3. The worker (`worker_main.py`) picks up the job and runs the assigned pipeline on the image
4. Results land in MongoDB and Weaviate, making the image searchable

---

## Layout

```
┌─────────────────────────────────────────────────────────────────────────┐
│  [App header / nav]                                                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Workspaces                          [ + New Workspace ]                │
│                                                                         │
│  ┌────────────────────────────────┐  ┌──────────────────────────────┐  │
│  │  Vacation Photos               │  │  Work Screenshots            │  │
│  │  ● Active                      │  │  ⬤ Paused                    │  │
│  │                                │  │                              │  │
│  │  📁 /home/alice/Photos/Vacations│  │  📁 C:\Users\Bob\Screenshots │  │
│  │                                │  │                              │  │
│  │  Pipelines:                    │  │  Pipelines:                  │  │
│  │  [Full Analysis] [CLIP Only]   │  │  [Quick Embed]               │  │
│  │                                │  │                              │  │
│  │  Extensions: .jpg .png .webp   │  │  Extensions: .png .jpg       │  │
│  │                                │  │                              │  │
│  │  [Scan Now]  [Edit]  [Delete]  │  │  [Scan Now]  [Edit]  [Delete]│  │
│  └────────────────────────────────┘  └──────────────────────────────┘  │
│                                                                         │
│  ┌────────────────────────────────┐                                    │
│  │  + Add Workspace               │  ← empty-state CTA card           │
│  └────────────────────────────────┘                                    │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Component Breakdown

### Page Header
- Title: "Workspaces" (left-aligned, bold)
- "New Workspace" button: top-right, violet, opens the create/edit drawer

### Workspace Card Grid
- 2–3 columns on desktop, 1 on mobile
- Each card (`WorkspaceCard`):

**Top section:**
- Workspace name (large, bold, truncated if long)
- Status badge (top-right): Green pill "● Active" with pulse dot OR grey "⬤ Paused"
- Active workspaces: top border has a thin violet/green left accent line or glowing top border

**Middle section:**
- Folder icon + full path in monospace font (`/home/alice/Photos/Vacations`)
  - Path is the most important piece of information; shown prominently
  - If path is very long, truncate with ellipsis and show full path in a tooltip

- "Pipelines:" label + pipeline chips (one pill per linked pipeline)
  - Each chip shows the pipeline name, small coloured dot
  - If a pipeline is missing/deleted, show a red "⚠ Missing" chip

- "Extensions:" label + extension tags
  - Small monospace chips: `.jpg` `.png` `.webp` etc.
  - If none set, show "All types" in muted text

**Bottom actions:**
- `[Scan Now]` button — triggers `POST /workspaces/{id}/scan`; shows loading state; on success, briefly shows "Scan triggered ✓" then reverts
- `[Edit]` button — opens right-side drawer with pre-populated form
- `[Delete]` button (destructive red) — shows confirmation dialog before deletion

### Empty State
If no workspaces exist yet:
```
┌─────────────────────────────────────────────────────────────────┐
│                      [folder icon]                              │
│               No workspaces configured yet                      │
│      Add a workspace to start indexing your photo library       │
│                                                                 │
│                   [ + Create First Workspace ]                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Create / Edit Drawer

Slides in from the right side of the screen. Width: ~480px. Blurred backdrop behind it.

```
┌──────────────────────────────────────────────┐
│  Create Workspace              [✕ Close]      │
├──────────────────────────────────────────────┤
│                                              │
│  NAME                                        │
│  [_________________________]                 │
│                                              │
│  FOLDER PATH                                 │
│  [_________________________] [Browse...]     │
│                                              │
│  EXTENSIONS                                  │
│  [.jpg ×] [.png ×] [.webp ×] [+ Add]        │
│                                              │
│  PIPELINES                                   │
│  [Full Analysis ×] [CLIP Only ×] [+ Add]     │
│                                              │
│  STATUS                                      │
│  [ Active ●──────────── ] toggle             │
│                                              │
│  [ Create Workspace ]  [ Cancel ]            │
└──────────────────────────────────────────────┘
```

### Form Fields in Drawer

**1. Name** (required)
- Free-text input
- Placeholder: "e.g. Vacation Photos, Work Archive"

**2. Folder Path** (required, most critical field)
- Text input (manual entry) + "Browse..." button
- Manual entry: user can type the full server path directly (`/home/alice/Photos` or `C:\Users\Alice\Photos`)
- "Browse..." button: opens the **Directory Browser Modal** (see below)
- Important: this is a **server-side path**, not the user's local machine path. The hint text should say: "Enter the absolute path on the server where PixQuery is running"
- Validation: check path format; backend validates existence on submit

**3. Extensions** (multi-select)
- Tag input style (chips with × remove buttons)
- Dropdown/autocomplete to add more: `.jpg`, `.jpeg`, `.png`, `.webp`, `.gif`, `.bmp`, `.tif`, `.tiff`, `.heic`, `.avif`
- Default: no selection = watch all supported types
- Max 10 chips shown, scrollable if more

**4. Pipelines** (multi-select)
- Dropdown to search/select from user's pipelines
- Multiple can be selected (each runs independently per image)
- Shows as chips: pipeline name + × remove
- Empty = no processing (image gets tracked but not analysed)
- Warning if no pipeline selected: "Without a pipeline, images will be tracked but not searchable"

**5. Active Toggle**
- On/Off toggle switch
- When Off (paused): workspace exists in DB but watcher ignores it; no new jobs are queued
- Useful for temporarily disabling a workspace without deleting it

**Submit button**: "Create Workspace" (create mode) / "Save Changes" (edit mode), full-width, violet

---

### Directory Browser Modal

A server-side filesystem browser, because browser `<input type="file">` cannot return server-side absolute paths.

```
┌────────────────────────────────────────────────────────┐
│  Browse Directory                       [✕ Close]       │
├────────────────────────────────────────────────────────┤
│  📍 /home/alice/Photos                                  │
│  ─────────────────────────────────────────────────────  │
│                                                        │
│  ↑ ../ (parent)                                        │
│                                                        │
│  📁 Vacations/          →  navigate into               │
│  📁 Work/               →  navigate into               │
│  📁 Screenshots/        →  navigate into               │
│  📄 photo001.jpg        (not clickable, grey)          │
│  📄 photo002.jpg        (not clickable, grey)          │
│                                                        │
│  [ Select This Folder: /home/alice/Photos ]  [Cancel]  │
└────────────────────────────────────────────────────────┘
```

- Modal dimensions: ~576px wide, scrollable entries
- Current path shown as breadcrumb at the top
- Entries: folders are clickable (navigate into), files are greyed out (non-interactive)
- "Parent" (`../`) entry at the top for navigating up
- Drive roots on Windows: `C:\`, `D:\` etc. shown as top-level options
- "Select This Folder" button: confirms the currently browsed path and populates the drawer's folder path input

---

## Alternative Design Options

**Option A (current, recommended)**: Card grid + right-side drawer. Standard for admin settings panels.

**Option B — Table view**: Replace cards with a data table (one row per workspace). More compact when there are many workspaces (10+). Sorting and filtering become easier. Less visual but more information-dense. **Recommended as an alternative view mode** (toggle between card grid and table).

**Option C — List with inline expand**: Click a workspace row to expand it and show edit controls in-place, without a drawer. Simpler, but harder to see multiple workspaces at once.

**Option D — Wizard for first workspace**: On first use, show a guided 3-step wizard: Step 1: Choose folder. Step 2: Select extensions. Step 3: Assign pipeline. Better onboarding; more work to implement.

---

---

# Page 5 — Statistics & Jobs Page

## Purpose

This page serves as a **health dashboard and operations monitor**. It answers the questions: "Is the system running? How many images have been processed? Are there any failures?" It's used occasionally — typically after setting up a workspace, when investigating why an image isn't searchable, or when something seems wrong.

---

## Layout

```
┌─────────────────────────────────────────────────────────────────────────┐
│  [App header / nav]                                                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Statistics & Jobs                          [↻ Refresh]                │
│  Last updated: 14 seconds ago                                           │
│                                                                         │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐  │
│  │  Total       │ │  Active      │ │  Pipelines   │ │  Processing  │  │
│  │  Images      │ │  Workspaces  │ │  Defined     │ │  Now         │  │
│  │              │ │              │ │              │ │              │  │
│  │    1,247     │ │      3       │ │      4       │ │    ●  2      │  │
│  │  across all  │ │  watching    │ │  configured  │ │  (violet     │  │
│  │  workspaces  │ │  4 folders   │ │              │ │  pulse dot)  │  │
│  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘  │
│  ┌──────────────┐ ┌──────────────┐                                     │
│  │  Jobs        │ │  Jobs        │                                     │
│  │  Completed   │ │  Failed      │                                     │
│  │              │ │              │                                     │
│  │    1,201     │ │     14       │                                     │
│  │  (green)     │ │  (red)       │                                     │
│  └──────────────┘ └──────────────┘                                     │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Recent Jobs                                          [Show: All ▾]     │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  FILE                  STATUS    PIPELINE        UPDATED        │   │
│  ├─────────────────────────────────────────────────────────────────┤   │
│  │  vacation_001.jpg   ● Processing  Full Analysis  2m ago         │   │
│  │  vacation_002.jpg   ✓ Completed   Full Analysis  3m ago         │   │
│  │  work_ss_045.png    ✗ Failed      Quick Embed    5m ago  [Retry]│   │
│  │  vacation_003.jpg   ● Processing  Full Analysis  6m ago         │   │
│  │  archive_img.jpg    ⌛ Queued     CLIP Only      8m ago         │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Component Breakdown

### Page Header
- Title: "Statistics & Jobs" (left)
- "↻ Refresh" button: top-right, manually triggers data reload
- Subtitle: "Last updated: X seconds ago" — auto-refreshes every 15 seconds when jobs are in processing state

### Stat Cards Row

6 stat cards in a responsive grid (3 per row on desktop, 2 on tablet, 1 on mobile):

| Card | Label | Value colour | Icon | Notes |
|---|---|---|---|---|
| Total Images | images indexed + active | Slate-200 white | Photo grid icon | All `image_assets` where `active=true` |
| Active Workspaces | workspaces currently active | Green | Folder-eye icon | `workspace_definitions` where `active=true` |
| Pipelines Defined | total pipelines | Blue | Pipeline/flow icon | Total `pipeline_definitions` |
| Jobs Completed | cumulative count | Green | Checkmark circle | From `processing_jobs` |
| Jobs Failed | cumulative count | Red | X circle | Failed jobs — actionable count |
| Processing Now | currently running | Violet (pulsing) | Spinning gear icon | Jobs in `processing` state — 0 when idle |

Each card:
- `bg-slate-900/60 border border-slate-800 rounded-2xl backdrop-blur`
- Icon in coloured square (top-right of card)
- Big number (3xl bold tabular mono font)
- Small subtext below the number
- "Processing Now" card: violet glow on border when > 0 (system is active)
- "Jobs Failed" card: red tint on border when > 0 (needs attention)

### Recent Jobs Table

**Table header:**
- "Recent Jobs" label (left) + "Show: All ▾" status filter dropdown (right)
- Status dropdown options: All | Queued | Processing | Completed | Failed

**Table columns:**
- `File` — filename (basename only, path truncated; full path shown in tooltip on hover)
- `Status` — pill badge with coloured dot
- `Pipeline` — which pipeline processed this image
- `Updated` — relative time ("2m ago", "3h ago") — sortable
- (Action) — "Retry" button for Failed rows only

**Status pills:**
| Status | Colours | Dot |
|---|---|---|
| `queued` | slate background, slate text | Static grey dot |
| `processing` | violet/indigo background, violet text | Animated pulse violet dot |
| `completed` | green dark background, green text | Solid green dot |
| `failed` | red dark background, red text | Solid red dot |

**Row interactions:**
- Clicking a row (on the file name cell): navigates to Image Detail for that asset
- "Retry" button on failed rows: calls `POST /jobs/{id}/requeue`; shows inline loading state; row status changes to `queued`; button disappears

**Sorting:**
- Click column headers to sort (Status, Updated)
- Default sort: `updated_at` descending (most recent first)
- Sort direction indicator: ▲/▼ icon next to sorted column, violet when active

**Live updates:**
- When any job is in `processing` state, the page auto-refreshes every 15 seconds
- Optional: WebSocket (`ws://localhost:8000/ws`) for real-time job status pushes (update rows without full re-fetch); when a job completes, its row status pill transitions from violet → green with a brief glow animation

**Empty state:**
- "No jobs yet. Create a workspace and scan a folder to start processing images."

---

## Alternative Design Options

**Option A (current, recommended)**: Stats at top, jobs table below. Standard operations-dashboard pattern. Simple and scannable.

**Option B — Tabbed layout**: Two tabs: `Overview` (stat cards only) | `Jobs` (full job log). Appropriate when the job log grows very large and needs its own space. Better separation of concerns.

**Option C — Timeline view**: Show jobs as a timeline/activity feed rather than a table. Better for understanding when bursts of processing happened. Complementary to the table, not a replacement.

**Option D — Live log terminal**: A "terminal" style output window showing job log lines in real time via WebSocket. Power-user-friendly; good for debugging. Could be an optional panel that you toggle open.

**Option E — Per-workspace drill-down**: Click a workspace from the stat cards section to see jobs filtered to only that workspace. Useful when debugging why images from a specific folder aren't appearing. Implement via a URL parameter: `/stats?workspace_id=...`.

---

---

# Summary Table

| Page | Primary User Goal | Complexity | Visit Frequency |
|---|---|---|---|
| Login/Signup | Authenticate | Low | Once per session |
| Search | Find photos | Low–Medium | Daily |
| Pipeline Manager | Design processing chains | High | Setup + occasional |
| Workspace Definitions | Configure watched folders | Medium | Setup + occasional |
| Statistics & Jobs | Monitor processing health | Medium | After changes, debugging |

---

# Navigation Flow

```
Landing (unauthenticated)
         ↓  login/register
App Shell (sticky nav)
    ├── /search          → Search Page
    │       └── /image/:id → Image Detail
    ├── /pipelines       → Pipeline Manager
    ├── /workspaces      → Workspace Definitions
    └── /stats           → Statistics & Jobs
```

---

# Cross-cutting UX Principles

1. **Dark-first, always**: `slate-950` background on every page. Never a white or light variant.
2. **Violet = primary action**: All CTAs, active states, focus rings. Blue/indigo for secondary.
3. **Glassmorphism for cards**: Backdrop blur + translucent dark background + subtle border. Not flat cards.
4. **No modal stacking**: Only one modal/drawer open at a time. Close before opening another.
5. **Inline feedback**: Form errors shown near the field, not only in a toast. Success shown transiently (2s toast or inline "✓ Saved").
6. **Empty states are helpful**: Every empty data state provides a clear CTA for the next step.
7. **Loading is animated**: Skeleton placeholders (not just a spinner) for grid/table loads. Spinner for button actions.
8. **Mobile is second-class but not broken**: Nav collapses; grid goes single-column; drawers go full-screen.
9. **Keyboard navigation**: Tab order logical on all forms. Esc closes modals. Enter submits forms.
10. **Progressive disclosure**: Advanced/destructive options (Delete, Config override) are accessible but not front-and-centre.
