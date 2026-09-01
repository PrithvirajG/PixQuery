---
project: PixQuery
type: knowledge-note
created: 2026-08-29
status: in-progress
---

# Backend Module Structure — Audit & Reorganisation Plan

**Date:** 2026-08-29
**Scope:** `backend/src/` module layout, naming, and layering
**Status:** In progress — Tier 3 implemented 2026-08-29 (`src/pipelines/` → `src/workers/`, tracked as git renames). Tiers 1 and 2 still planned; the layout diagrams and tables below are the pre-rename state and are kept as the historical record of what §3.4 was diagnosing — see the update note under §4.3 for what actually shipped.

Triggered by the question "why are `config.py` and `events.py` sitting at `src/` root so randomly?" The short answer is that one of them isn't random at all, and the things that *are* disorganised are elsewhere. This note records the full audit so the reorganisation can be done deliberately rather than by feel.

Related: [[Architecture Reality Map]] · [[Current Implementation Audit]] · [[Implementation Task Backlog]]

---

## 1. Current layout

```
backend/
  api_main.py  worker_main.py  monitoring_main.py   <- entry points
  src/
    config.py                    <- 43 lines, env-var defaults
    events.py                    <- 151 lines, domain event vocabulary
    api/
      app.py  router.py  dependencies.py  errors.py  security.py
      routes/  (auth, images, jobs, pipelines, pipeline_nodes,
                search, stats, status, websocket, workspaces)
    models/
      documents.py               <- Pydantic docs, one per collection
    repositories/
      protocol.py                <- PipelineRepository contract
      mongo_pipeline.py          <- 1082 lines
      memory_pipeline.py         <- in-memory fake for tests
    services/
      image_ job_ pipeline_ search_ stats_ workspace_service.py
      document_serializer.py
    pipelines/
      ingestion/   reconciler.py  watcher.py
      processing/  pipeline.py  rmq_processor.py  worker.py
                   executors/  models/
    infrastructure/
      messaging/     events.py  rabbitmq.py
      vector_store/  protocol.py  weaviate.py  query_encoder.py
    migrations/
      runner.py  __main__.py
```

## 2. Verdict on the two root modules

### `config.py` — correctly placed, leave it

It imports only `os`. It is a pure leaf with **zero internal dependencies**, and it is consumed by all six subpackages:

| Consumer | Files importing `src.config` |
|---|---|
| `api/` | `app.py`, `dependencies.py`, `routes/status.py`, `routes/websocket.py`, `routes/workspaces.py` |
| `infrastructure/` | `messaging/events.py`, `messaging/rabbitmq.py`, `vector_store/weaviate.py` |
| `pipelines/` | `ingestion/reconciler.py`, `ingestion/watcher.py`, `processing/pipeline.py`, `processing/rmq_processor.py`, `processing/executors/builtin.py` |
| `migrations/` | `__main__.py` |
| tests | `test_image_write_node.py` |

Moving it into any subpackage inverts a dependency. Putting it under `infrastructure/`, the most tempting option, would mean `pipelines/processing/pipeline.py` imports *infrastructure* purely to read `PIPELINE_OUTPUT_DIRNAME`. Root-level settings is also the prevailing convention (Django `settings.py`, Flask `config.py`).

**Action: none.** The only change needed is making the placement *look* deliberate — see §4.1.

### `events.py` — right layering, wrong ergonomics

The split is architecturally correct and worth preserving:

- `src/events.py` — the **contract**. `Event` dataclass, the three `EVENT_*` type constants, and the `*_event()` factories. Imports only `json`, `dataclasses`, `datetime`.
- `src/infrastructure/messaging/events.py` — the **transport**. `EventBus` / `EventSubscriber` over a RabbitMQ fanout exchange.

Keeping these apart is exactly why `repositories/mongo_pipeline.py` can emit domain events without knowing a broker exists — its `event_sink` is just `Callable[[Event], None]`. That is a genuinely good seam.

Three real flaws, though:

1. **Two files named `events.py`.** `from src.events import Event` vs `from src.infrastructure.messaging.events import EventBus`. You must read the full path to know which layer you are in.
2. **Domain types split across two granularities with no stated rule.** Documents get a package (`models/`), events get a loose module. Same layer, same role, inconsistent shape.
3. **`src/__init__.py`'s `__all__` lists only the five subpackages** — `config` and `events` appear nowhere. That omission is the actual reason they read as leftovers rather than as deliberate leaves.

## 3. The larger structural problems

These matter more than file placement and should be sequenced ahead of any cosmetic move.

### 3.1 `mongo_pipeline.py` is a 1082-line god object

By a wide margin the largest file in the backend (next is `processing/pipeline.py` at 461). One class handles **eleven aggregates**: assets, file observations, processing jobs, pipeline runs, model outputs, users, pipeline nodes, pipeline definitions, workspaces, workspace membership, and statistics — plus index management and system-node seeding.

The `PipelineRepository` protocol added on 2026-08-29 now declares 43 methods, which makes the size concrete and measurable. That protocol is also the enabler for splitting it: per-aggregate repositories can be composed behind the existing public name without touching a single caller.

### 3.2 Both repository files are misnamed

Neither is about pipelines — they hold *every* collection. `memory_pipeline.py` is in truth a miniature fake Mongo driver (`_MemoryCollection`, `_Cursor`, `_matches`, `_apply_update`), which the name gives no hint of.

- `mongo_pipeline.py` → `mongo.py`
- `memory_pipeline.py` → `in_memory.py`

### 3.3 A genuine layering violation in `job_service.py`

```python
# backend/src/services/job_service.py:1
from src.pipelines.ingestion.reconciler import pipeline_version_hash
```

A service reaching **outward** into the ingestion layer for a pure function about pipeline identity. `pipeline_version_hash` is domain logic — it hashes a DAG's nodes and edges into a version string — and has no business living in the filesystem reconciler. Both `JobService` and `FilesystemReconciler` should import it from a neutral domain module.

This is the only inward/outward inversion in the codebase. Verified clean otherwise: no repository imports `api`/`services`/`pipelines`, and no `pipelines/` module imports `services/`.

(`search_service.py` importing `infrastructure.vector_store.protocol` is *not* a violation — it imports only the abstraction, which is the DIP working as intended. Worth revisiting if a "ports live in the domain" convention is ever adopted, but it is correct as-is.)

### 3.4 "Pipeline" is overloaded four ways

| Usage | Means |
|---|---|
| `src/pipelines/` package | the two background processes |
| `PipelineDefinition` | a user-authored DAG |
| `PipelineService`, `pipeline_service.py` | the CRUD service for those DAGs |
| `processing/pipeline.py` → `DynamicPipeline` | the DAG executor |

Compounding it, `pipelines/ingestion/` contains no pipeline at all — it is the filesystem watcher and job dispatcher. Renaming the package `workers/` (holding `ingestion/` and `processing/`) would leave "pipeline" meaning exactly one thing: a user's DAG.

This is the highest-value rename and the widest blast radius — every `src.pipelines.*` import, all three entry points, and the three Dockerfiles.

## 4. Target structure

### 4.1 Tier 1 — naming and placement (low risk, pure moves)

```
src/
  __init__.py          <- __all__ names config + domain explicitly
  config.py            <- UNCHANGED, now documented as a deliberate leaf
  domain/
    __init__.py
    documents.py       <- from models/documents.py
    events.py          <- from src/events.py
    versioning.py      <- pipeline_version_hash, out of the reconciler
  repositories/
    protocol.py
    mongo.py           <- from mongo_pipeline.py
    in_memory.py       <- from memory_pipeline.py
  infrastructure/
    messaging/
      event_bus.py     <- from messaging/events.py
      rabbitmq.py
    vector_store/      <- unchanged
```

Fixes: the `events.py` collision, the domain-type granularity split, the `job_service` layering violation, and the misleading repository names. Resolves every complaint that prompted this note.

Open choice: `domain/` vs. keeping `models/` and adding `events.py` to it. `domain/` is clearer about holding more than Pydantic documents; `models/` avoids a rename and is already referenced throughout `CLAUDE.md`.

### 4.2 Tier 2 — split the god repository

```
repositories/
  protocol.py
  mongo/
    __init__.py     <- composes MongoPipelineRepository from the mixins
    assets.py       <- assets, observations, activity refresh
    jobs.py         <- jobs, runs, lifecycle transitions, events
    outputs.py      <- model outputs, clearing
    pipelines.py    <- definitions, nodes, system-node seeding
    workspaces.py   <- workspaces, membership
    users.py
    stats.py
    indexes.py      <- ensure_indexes
  in_memory.py
```

`MongoPipelineRepository` stays the public name and the composed facade, so no caller changes. The `PipelineRepository` protocol is the safety net — conformance is checkable after each extraction.

### 4.3 Tier 3 — disambiguate "pipeline"

`src/pipelines/` → `src/workers/`, keeping `ingestion/` and `processing/` beneath it. Mechanical but wide: every import, the three `*_main.py` entry points, `Dockerfile.worker`, `Dockerfile.monitor`, and the `CLAUDE.md` architecture table.

> **Done — 2026-08-29.** `git mv src/pipelines src/workers`; every import updated (25 files: `src/`, `tests/`, `worker_main.py`, `monitoring_main.py`, including string-based `mock.patch` targets and the one literal path string in `yolo.py`'s default write path); `src/__init__.py`'s `__all__` and `CLAUDE.md`'s architecture table updated. Git tracked the move as renames (`git status` shows `R`/`RM`), so history follows the files. Dockerfiles needed no change — both `COPY ./src` wholesale. Verified: full backend suite still 200 tests with the identical 11 pre-existing environmental errors (missing `cv2`/CLIP-torch in the dev env) both before and after; `src.workers.*` modules import successfully outside the suite too (`reconciler`, `DynamicPipeline`, the executor registry, `JobService`, `ClipQueryEncoder`). `monitoring_main.py`'s own import chain still needs the optional `watchdog` package, same as before the rename — not a regression, just not installed in this dev environment.
>
> Tiers 1 and 2 are unaffected by this and remain as described above — §4.1's `pipelines/` references there are pre-rename and should read `workers/` when acted on.

## 5. Recommended sequence

1. **Tier 1** — answers the original question, low risk, unblocks nothing else. *(not yet done)*
2. ~~**Tier 3**~~ — done 2026-08-29, ahead of Tier 2 as recommended, while `pipelines/` (now `workers/`) was still a small surface.
3. **Tier 2** — the real SRP work, done last against the now-stable `workers/` layout. *(not yet done)*

Each tier should land as its own commit with the full backend suite green (200 tests as of 2026-08-29; 11 pre-existing environmental errors from missing `cv2` and CLIP/torch in the dev env — the baseline to diff against, not regressions).

## 6. Non-goals

- Moving `config.py`. It is already right.
- Splitting `services/`. Largest is `search_service.py` at 382 lines and it has a clear single responsibility since the vector-store and encoder extraction.
- Touching `api/routes/`. The `router.py` aggregator + one module per resource is a clean, conventional shape.
- Entry points at `backend/` root. `api_main.py` / `worker_main.py` / `monitoring_main.py` as thin process launchers outside `src/` is correct and matches the Dockerfiles.
