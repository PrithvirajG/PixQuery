---
project: PixQuery
type: knowledge-note
created: 2026-08-27
status: parked
---

# Cloud SaaS & On-Prem — Scope Exploration

**Date discussed:** 2026-08-26
**Status:** Parked exploratory thinking — not a decision, not scheduled. Captured so the reasoning isn't lost between sessions.
**Related:** [[Remote Access — Tailscale]] · [[Product Vision & Roadmap]] · [[Architecture Reality Map]] · [[Current Implementation Audit]]

## Tension with the existing thesis

[[Product Vision & Roadmap]] frames PixQuery as **local-first** and explicitly *not* "another Google Photos replacement." A public multi-tenant SaaS is the opposite instinct — it should be treated as a deliberate pivot/expansion to weigh against that thesis, not a natural next step. This note assumes the question is "what would it cost/take," not "we're doing this."

## The one fact that reshapes everything

PixQuery's ingestion model is: watch a folder on this machine, hash files, process them. That works for local/on-prem — the customer's files stay on their own hardware. It **cannot work for cloud SaaS** — there's no folder to watch on a shared server for a stranger's laptop. Cloud SaaS requires **upload + blob storage** as a hard prerequisite, not an enhancement. This is exactly the blob-storage question parked in an earlier session — it's the fork in the road between the two deployment modes, not an independent nice-to-have.

Two deployment paths sharing one processing core:

| | On-prem (today, packaged) | Cloud SaaS (new) |
|---|---|---|
| Ingestion | Watch local folder (as now) | Upload → object storage (S3/R2) |
| Storage | Local disk | Object storage + CDN |
| Tenancy | Single customer, single install | Many customers, one shared deployment |
| Ops burden | Customer's problem | **PixQuery's** problem — uptime, backups, breaches |

## Architecture changes, by layer

**Storage/ingestion** — add an upload path alongside the watcher; `ImageAsset.current_path` becomes "path or blob key," and the thumbnail/detail routes need a storage-backend abstraction instead of `FileResponse(local_path)`.

**Multi-tenancy** — already half-exists. Workspaces have `owner_id` + `members` with owner/editor/viewer roles (see [[Workspace Sharing & Access Control]]) — real tenant scoping today, but app-level only (every query filters by it; nothing enforces it at the DB layer). For paying strangers' data that needs hardening:
- Weaviate has **native multi-tenancy** (a tenant key per class) — adopt directly rather than re-inventing row-level scoping in a vector DB.
- Mongo: shared collections + strict `tenant_id`/`workspace_id` scoping is realistic for an MVP (DB-per-tenant is overkill early), but a scoping bug goes from "annoying" to "data breach" once tenants are paying strangers.

**Compute for the ML models** — the biggest architectural and cost risk. YOLO/BLIP/CLIP/MobileNet inference is CPU/GPU-heavy; today it runs once, locally, for one user.
- The RabbitMQ + worker pattern already in place is exactly the right shape — it horizontally scales by adding worker replicas. Survives unchanged.
- CPU inference at real user volume is slow and expensive; GPU instances are the usual answer and become the dominant cost line (see below).

**Auth/billing** — JWT auth exists and covers login. Net-new: email verification, password reset, per-user subscription tier (Stripe or similar), usage quotas (storage GB, images/month, pipeline runs) enforced at job-creation time, and metering to bill against those quotas.

**Packaging for on-prem** — today "on-prem" means "clone the repo, run three Python processes plus docker-compose." Fine for a developer, not shippable to a customer. Needs a single bundled Docker image/compose stack, config via env vars, and a first-run setup wizard (create admin, pick watched folder) instead of manual setup. This step alone is valuable independent of the SaaS decision.

## What the cloud deployment itself would look like

Given the existing shape (3 processes + Mongo + RabbitMQ + Weaviate), the pragmatic MVP path is **managed services over self-hosted infra** — trades margin for far less ops burden:

- **API + worker containers** → a PaaS like Render/Railway/Fly.io (Docker + background workers with much less ops than raw Kubernetes; only move to EKS/GKE if actual scale demands it)
- **MongoDB** → MongoDB Atlas (managed, has a free tier for early testing)
- **RabbitMQ** → CloudAMQP (free low-throughput tier exists)
- **Weaviate** → Weaviate Cloud (free sandbox tier)
- **Object storage** → Cloudflare R2 over S3 specifically because R2 has **no egress fees** — for an image-serving app, egress is exactly what kills you on S3
- **GPU inference** → the wildcard. Self-hosted GPU instances run real money per hour; at low volume this may be the single largest cost, larger than everything else combined.

## Non-engineering requirements

Easy to underweight against the architecture work, but real: Terms of Service / Privacy Policy (photos are personal, potentially sensitive data — GDPR applies with any EU users), backups/disaster recovery as PixQuery's liability instead of the customer's, and — a real legal obligation in most jurisdictions once strangers can upload images publicly — some form of abuse/CSAM detection (e.g. hash-matching against known-bad databases). Not something to bolt on after launch.

## Suggested sequencing, if ever pursued

1. **Storage backend abstraction** (local disk vs. S3-compatible) — unlocks on-prem-with-remote-storage-option *and* is the literal prerequisite for cloud SaaS.
2. **Formalize multi-tenancy** (Weaviate tenant keys, audited Mongo scoping) — valuable for on-prem multi-user setups too, not SaaS-only.
3. **Package on-prem properly** (single compose stack + setup wizard) — might satisfy a lot of demand without ever building the SaaS side.
4. Only then: billing, quotas, public-facing hardening, cloud deploy.

Steps 1–3 improve the product either way; the SaaS cost/liability surface (step 4) is only committed to at the end, deliberately.
