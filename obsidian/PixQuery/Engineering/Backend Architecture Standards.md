# Backend Architecture Standards

The layering, naming, and dependency rules the PixQuery backend now follows,
and — more usefully — *why* each one exists. Every rule here was arrived at by
hitting the problem it prevents.

A condensed, machine-facing version lives as a Claude Code skill at
`~/.claude/skills/backend-service-architecture/SKILL.md`, so it applies in any
repository. This document is the human reference: same rules, but with the
arguments and the worked examples kept in.

Related: [[Backend Module Structure — Audit & Reorganisation Plan]] (the audit
that kicked the restructure off), [[Architecture Reality Map]].

---

## The shape

```
backend/src/
  api/
    routes/rest/     HTTP handlers, one file per resource
    routes/ws/       WebSocket handlers, one file per endpoint
    dependencies.py  DI wiring
    security.py      JWT + hashing + authenticate_from_token
    errors.py        error-envelope machinery (APIError lives here)
  services/          business logic, composes 2+ repositories
  repositories/      9 of them, one per MongoDB collection, pure CRUD
  consumer/          every RabbitMQ consumer (processing/, ingestion/, events/)
  publisher/         every named RabbitMQ publisher (events/)
  infrastructure/    generic adapters (messaging/, ml/, vector_store/)
  errors/            every custom exception, one module per flow
  utils/             domain-agnostic helpers
  models/            Pydantic documents
  migrations/        append-only versioned migrations
```

Three processes: `api_main.py`, `pipeline_worker_main.py`,
`file_watcher_main.py`.

---

## 1. A repository wraps exactly one collection

Pure CRUD. No cascades, no policy, no event emission, no reading a second
collection. There is no god-repository and no shared base class — just
`SomeRepository(database)` against a pymongo `Database`.

**Why it matters:** it buys a guarantee a reader can rely on — *"if I've read
this repository, I know everything that touches this collection."* Exactly one
cross-collection method destroys that guarantee for the entire class, and the
reader has no way to know it's been destroyed without reading every method.

This is what the migration off `MongoPipelineRepository` was for. The old god
repository could reach any collection from anywhere, so nothing about a call
site told you what it touched.

### The corollary that comes up constantly

Anything touching two collections is a **service** concern, even when it's
three lines. The tempting escapes all fail:

- **Instance method on one of the repos** → that repo now imports the other.
  Repo-to-repo coupling is a two-node god-repository.
- **`@staticmethod` on one of the repos** → syntax, not architecture. The
  second dependency doesn't disappear; you've just hidden it in a class body
  and arbitrarily declared one collection the owner.
- **A wrapper repository over both** → a smaller god-repository with extra
  steps, and it breaks the "repository = one collection" invariant that makes
  all nine legible.

`services/access_scope.py` is the worked example: computing "which assets can
this user see" needs `workspace_definitions` *and* `file_observations`.
Neither repository can own it, so it's a service-layer composition.

---

## 2. Services own orchestration, events, and policy

A service takes the **specific** repositories it needs as constructor keyword
arguments.

**Why not just pass the `db` handle down?** Because the constructor signature
is an audit trail. Reading

```python
ImageService(*, assets, observations, workspaces, pipelines, jobs, runs, outputs)
```

tells you exactly which collections this service touches without opening a
single method. A `db: Database` parameter tells you nothing — any method could
reach anything, and you'd have to read the whole file to find out.

Three more reasons the repository layer earns its keep over raw `db` access:

- **Encapsulation.** `ImageAssetsRepository.upsert()` is the single place that
  knows assets are unique on `(workspace_id, content_sha256)`. Inline
  `db.image_assets.update_one(...)` calls would reimplement that rule at every
  write site, with drift risk.
- **Testability.** The suite injects `FakeDatabase`-backed repos via
  `tests/repo_factory.py::new_repos()` and runs with no MongoDB at all. Faking
  a narrow repository interface is tractable; faking pymongo's entire
  query/update surface is not.
- **Intent.** `jobs.get_or_create(asset_id=..., pipeline_id=...)` says what's
  happening. `find_one_and_update({...}, {"$setOnInsert": {...}}, upsert=True)`
  makes you re-derive it every time.

Services own: cascading deletes (`WorkspaceService.delete_workspace`), retry
policy (`PipelineExecutionService.RETRY_DELAYS`), domain-event emission, and
authorization decisions. Repositories persist the outcome; they never decide
it.

---

## 3. The utils test

`utils/` is for helpers that would make sense **in a project that had never
heard of workspaces or pipelines**. Topological sort, SHA-256 file hashing, L2
vector normalization, EXIF parsing — yes. `accessible_workspace_ids` — no.

Enforced mechanically by a rule written into `utils/__init__.py`: nothing here
may import from `src.services`, `src.repositories`, or `src.consumer`.

### The distinction people get wrong

"It doesn't do any DI or construction, it just takes its inputs as parameters"
is **not** the test. Two properties are orthogonal:

| | Does its own DI/construction? | Domain-agnostic? |
|---|---|---|
| `access_scope.py` | No | **No** |
| `utils/graph.py::topological_order` | No | Yes |

Both are plain functions receiving plain arguments. You could paste
`topological_order` into an unrelated codebase and it works. `accessible_
workspace_ids` has no meaning outside this domain — no matter how it's typed.

A module of plain functions with no class can still be deeply domain-coupled.
That's why `access_scope.py`, `document_serializer.py`, and
`pipeline_versioning.py` live in `services/` despite having no `Service` class.

---

## 4. Name the whole chain

File name, class name, and DI provider agree:

- `image_assets_repository.py` ↔ `ImageAssetsRepository` ↔
  `get_image_assets_repository()`
- `image_service.py` ↔ `ImageService` ↔ `get_image_service()`

Exceptions are documented explicitly so they read as decisions rather than
oversights: the three plain-function modules above skip the `_service.py`
suffix because there's no class to match.

**Renaming a process means renaming every level of it.** When `worker` and
`monitor` were replaced with `pipeline-worker` and `file-watcher`, that meant:
Dockerfile, entry script, requirements file, `pyproject.toml` extra, compose
service, container name, *and* the bootstrap function
(`start_worker` → `start_pipeline_worker`). Renaming only the Dockerfile would
have relocated the generic name rather than removed it.

The one deliberate hold-out: the per-package bootstrap file stays `worker.py`
in both `consumer/processing/` and `consumer/ingestion/`, because the package
name already disambiguates it and `file_watcher.py` would have collided with
ingestion's existing `filesystem_watcher.py`.

---

## 5. One home per kind, regardless of which process runs it

`consumer/` holds **every** RabbitMQ consumer — including `EventConsumer`,
which isn't a standalone process at all but is instantiated lazily inside the
API process by the WebSocket route. Who runs it doesn't change what it is, and
one predictable home beats proximity to the caller.

`publisher/` mirrors it exactly. `infrastructure/messaging/` keeps only the
generic primitives: `RabbitPublisher`, `RabbitConsumer`, their shared
`rabbitmq_connection.py`, and `EventSink`.

---

## 6. Inherit for interface, not for code reuse

`EventConsumer(RabbitConsumer)` overrides `connect()` and `start_consuming()`
**entirely** — fanout pub/sub against an anonymous, exclusive, auto-delete
queue is a genuinely different pattern from a named durable work queue with
competing consumers. Calling `super().connect()` would declare the wrong kind
of queue.

It still subclasses. The payoff is one discoverable family and one lifecycle
contract (`connect`/`start_consuming`/`on_message`/`close`), not shared method
bodies. "It wouldn't reuse the body" is not a reason to skip the base class —
overriding a method wholesale is ordinary inheritance.

`EventPublisher(RabbitPublisher)` is the same story on the publish side.

Both carry a docstring explaining *why* the override exists, so nobody "fixes"
it later by adding a `super()` call.

---

## 7. Every custom exception lives in `errors/`

One module per owning flow: `errors/graph.py`, `errors/files.py`,
`errors/executors.py`, `errors/pipelines.py`, `errors/jobs.py`,
`errors/workspaces.py`.

**Why:** a route handler translating a failure into a 403 shouldn't need to
know that `WorkspaceAccessError` happens to be defined in
`services/workspace_service.py`. It needs one predictable import path.

No re-export shims left behind in the original modules — one canonical path or
the centralization achieved nothing. (A package `__init__.py` may still
re-export as part of its public API; `services/executors/__init__.py` does.)

The deliberate exception: `api/errors.py`'s `APIError` stays put. It isn't a
marker class raised in one place and caught in another — it's the anchor of
that file's own FastAPI exception-handler registration, and separating them
would split one cohesive mechanism across two files.

---

## 8. Cache stateless dependencies, uniformly

Every provider in `api/dependencies.py` is `@lru_cache`d — repositories and
services alike — making each a per-process singleton.

**Safe because** they hold collaborators, never per-request data. Request data
arrives as method arguments. `MongoClient` is explicitly designed to be shared
(it's a connection pool). `lru_cache` itself guards against the
two-first-callers race with an internal lock.

**Don't mix policies.** An earlier iteration had some providers cached and some
not; the comment in `dependencies.py` records why that was unified — the mix
"implied a distinction that did not exist." Service `__init__` is attribute
assignment with no I/O, so per-request construction costs nothing *and* buys
nothing.

**The footgun:** if a service ever stores per-request state on `self`
(`self.current_user_id = ...`), the shared singleton becomes a real concurrency
bug — concurrent requests clobber each other. That's the moment *that one
service* drops `@lru_cache`, not a reason to change the default.

---

## 9. Extract for reuse and consistency, not for purity

Two sequential queries are not automatically worth a function. `access_scope.py`
exists because four services need the identical two-step fetch — that's reuse,
plainly.

But the weighting changes for **authorization** logic. Four hand-rolled copies
of "what can this user see" isn't untidy duplication; it's four chances for one
copy to drift. `workspace_asset_ids` carries a fallback to the legacy
`watch_root_id` field — if that lived inline in four services, one of them
missing it would silently mis-scope what a user can see. That's a security
bug born of inconsistency, and it's why one canonical implementation matters
more here than ordinary DRY.

**Don't split a dependent query chain** into "fetch, then decide."
`accessible_asset_ids` uses the workspace ids as a *database-side* filter
(`{"workspace_id": {"$in": ws_ids}}`). Restructuring it to receive pre-fetched
data means either pulling every observation in the system into memory, or
making every caller re-derive the ordering — which is exactly what the helper
exists to prevent.

---

## 10. Verify against a fixed baseline

Record the exact baseline before restructuring: total test count and the set of
already-failing tests. Diff against it after **every** step.

**Watch the total count, not just pass/fail.** A module that fails to import
silently drops its entire test class from the run. During the `errors/`
migration the suite went 248 → 202 with *fewer* reported errors — a missed
import in a test file. "No new failures" would have hidden it completely.

**Sweep exhaustively.** That same miss happened because an earlier search
matched import *paths* rather than symbol *names*, so
`from src.services.executors.base import NodeExecutionError` slipped past a
pattern looking for `from src.services.executors import ...`.

Baseline for this codebase: **248 tests, 11 pre-existing environmental errors**
(missing `cv2`, `torch`/`clip`, `watchdog`, `fastapi`, `aio_pika` in the dev
shell — these are optional extras, not regressions).

---

## 11. Documentation moves in the same change

`CLAUDE.md` gets updated in the same commit as the restructure, not later. A
docstring cross-reference pointing at a moved file is a bug — fix it when
passing through. Several were caught that way this pass (`src/events.py`
references surviving the rename to `domain_events.py`, `websocket.py` paths
after the `rest/`+`ws/` split, "the old god-repository's own sink" comments
long after that facade was deleted).

Historical records — audit notes, decision logs in this vault — deliberately
keep referring to the old names. They describe the past; they aren't
instructions.

---

## Starting a new repo with this shape

1. `models/` (schema) and `repositories/` (one per collection) first.
2. `services/` the moment anything touches two collections.
3. `errors/` at the first custom exception, not the tenth.
4. `consumer/`/`publisher/` at the first queue binding, generic base classes in
   `infrastructure/`.
5. `utils/` only when a helper passes the Rule 3 test. An empty `utils/`
   invites domain logic to leak in.
6. One `dependencies.py`, all providers cached.
