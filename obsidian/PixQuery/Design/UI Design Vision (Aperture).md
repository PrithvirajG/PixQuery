 # UI Design Vision — "Aperture"

The full, first-principles design specification for the PixQuery frontend revamp lives at the repo root as **`UI-Design-Description.md`** (kept at root because it is the artifact fed directly to Claude Design). This note is the Obsidian-side home: the summary, the diagrams, and the link.

> **One line:** *A private darkroom for your memories — calm and photographic, with intelligence that glows when it works.*

## The idea in brief

- **Theme name:** Aperture. Metaphor: an aperture / observatory — a dark, recessive instrument where the only light comes from your **photographs** and from **moments of intelligence** (search, matching, processing).
- **Two moods, one system:** the **Gallery** (Search, Image Detail) is warm, spacious, content-first; the **Control Room** (Workspaces, Pipelines, Jobs) is precise and data-dense. Same tokens.
- **Color:** cool near-black "Carbon" neutrals (`#0A0C14` canvas) + a violet→indigo "Lumen" intelligence accent (`#7C5CFC`, gradient to `#5B8DEF`) + a rare warm "Ember" accent (`#FF9E57`) for human/memory highlights.
- **Type:** Geist (display), Inter (UI), Geist Mono (paths/IDs/JSON).
- **Signature elements:** match-reason chips, the node chain, the provenance panel, the aperture glow, and a ⌘K command palette.
- **Principles:** content is the light source · calm by default, alive on intelligence · one accent used with discipline · explain the magic · privacy you can feel.

## Diagrams

- [[PixQuery UI — Navigation Map.excalidraw|Navigation & Screen Map]] — the shell, the six surfaces, and the modals/drawers under each.
- [[PixQuery UI — Search Screen Wireframe.excalidraw|Search Screen Wireframe]] — the hero screen, annotated (search bar, mode pills, match-reason chips).
- [[PixQuery UI — Claude Design Workflow.excalidraw|Claude Design Feeding Workflow]] — the step-by-step process for generating the UI and revamping the frontend.

## Pages

Landing/Auth · Search · Image Detail · Workspaces · Pipelines · Jobs/Activity · Settings — all detailed in the root `UI-Design-Description.md` (§8), plus the Style Foundation prompt block and the screen-by-screen generation prompts in §10.

## Related

- [[Product Vision & Roadmap]]
- [[Workspace Sharing & Access Control]]
- [[Architecture Reality Map]]
