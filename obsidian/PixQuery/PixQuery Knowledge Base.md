# PixQuery Knowledge Base

This folder is maintained as an Obsidian-openable markdown knowledge base for PixQuery.

## Start here

- [[Product Vision & Roadmap]]
- [[UI Design Vision (Aperture)]]
- [[Current Implementation Audit]]
- [[Architecture Reality Map]]
- [[Market & Technical Landscape Analysis]]
- [[Implementation Task Backlog]]
- [[Backend Module Structure — Audit & Reorganisation Plan]] — `backend/src/` layout, naming, and layering; three tiers, Tier 3 (`pipelines/` → `workers/`) done, Tiers 1–2 planned (2026-08-29)

## Decisions

- [[Workspace Sharing & Access Control]] — workspace-level tenancy, RBAC (owner/editor/viewer), and per-workspace processing isolation (2026-05-30)
- [[Remote Access — Tailscale]] — chosen approach for secure remote access to the local instance; planned, not yet implemented (2026-08-26)

## Parked / exploratory

- [[Cloud SaaS & On-Prem — Scope Exploration]] — what a public cloud SaaS + packaged on-prem offering would require; parked against the local-first thesis (2026-08-26)

## Diagrams

- [[System Architecture.excalidraw|System Architecture]] — processes, infrastructure, and data flow
- [[Processing and Search Flow.excalidraw|Processing & Search Flow]] — ingestion → pipeline node chain → stores, and the search modes
- [[PixQuery UI — Navigation Map.excalidraw|UI Navigation & Screen Map]] — shell, six surfaces, modals/drawers
- [[PixQuery UI — Search Screen Wireframe.excalidraw|UI Search Screen Wireframe]] — the hero screen, annotated
- [[PixQuery UI — Claude Design Workflow.excalidraw|Claude Design Feeding Workflow]] — how to generate the UI from the spec

## Directory convention

- `Product/` — product vision, positioning, roadmap, scope decisions.
- `Design/` — UI/UX design vision, design system, screen specs, and UI diagrams.
- `Engineering/` — architecture, implementation audits, system maps, technical decisions.
- `Research/` — market, competitor, model, technology, and trend research.
- `Decisions/` — ADR-style decisions and rationale.
- `Meetings/` — future discussion notes, if needed.

## Maintenance rule

Whenever PixQuery is maintained, new documents should be written as linked Markdown notes in this Obsidian directory, with clear titles and wikilinks.
