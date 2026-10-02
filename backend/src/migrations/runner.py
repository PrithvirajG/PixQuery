"""Lightweight, dependency-free MongoDB migration runner.

Each migration has a stable ``id`` and an ``upgrade(db)`` function. Applied ids are
recorded in the ``schema_migrations`` collection, so every migration runs exactly
once and in order. Add a new migration by appending to ``MIGRATIONS`` (keep ids
sortable, e.g. ``0002_...``); never edit or reorder an already-released migration.

Run on deploy via ``python -m src.migrations`` (or automatically at API startup —
see ``RUN_MIGRATIONS_ON_STARTUP``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from src.logging_config import get_logger
from src.utils.time import utcnow

logger = get_logger(__name__)

MIGRATIONS_COLLECTION = "schema_migrations"


@dataclass(frozen=True)
class Migration:
    id: str
    description: str
    upgrade: Callable[[Any], None]


def _baseline(db: Any) -> None:
    """Establish the current schema: indexes + seeded system nodes.

    The seed set and the partial-unique index on system ``node_type`` mean a
    fresh DB comes up correct with no follow-up cleanup migrations.
    """
    from src.repositories.bootstrap import ensure_schema

    ensure_schema(db)


def _rename_captioning_to_vision_language_model(db: Any) -> None:
    """Rename the system Captioning node's identity to "vision_language_model".

    The node's job widened from "always produce one unconditioned caption"
    (BLIP only) to "run a configurable prompt through a vision-language model"
    (now also Qwen2-VL-2B-Instruct) — the old name undersold what it does.

    This only moves the node's *identity* (``node_type``, the registry key
    executors are resolved by): the ``_id`` is preserved, so every existing
    pipeline's ``nodes[].pipeline_node_id`` reference — which points at that
    _id, never at the node_type string — keeps resolving to the same row and
    is transparently upgraded to the new capability (with the default prompt
    written into that row's ``default_config`` by the next seed, since an
    existing node's ``config_overrides`` for this stage is ``{}``). The
    managed fields themselves (name, config_schema, default_config, ...) are
    re-applied by ``seed_system_nodes()`` afterward, same as any other
    code-owned field change — this migration's only job is the rename.

    Handles both possible orderings, because ``seed_system_nodes()`` runs on
    every process start (api/pipeline-worker/file-watcher), independent of
    migrations — there is no guarantee this migration runs before some
    process has already seeded a brand-new "vision_language_model" row under
    the new code:
      - Migration-first: only the old "captioning" row exists -> rename it.
      - Seed-first: a fresh "vision_language_model" row already exists (no
        pipeline could reference it yet — it didn't exist before) alongside
        the original "captioning" row (which existing pipelines DO
        reference) -> discard the fresh duplicate, rename the original. The
        partial-unique index on system node_type would otherwise reject the
        rename while both rows exist, so the duplicate must go first.
      - Already migrated / fresh install with no legacy row: no-op.
    """
    nodes = db["pipeline_nodes"]
    old = nodes.find_one({"node_type": "captioning", "owner_id": "system"})
    if old is None:
        return  # nothing to migrate
    new = nodes.find_one({"node_type": "vision_language_model", "owner_id": "system"})
    if new is not None and new["_id"] != old["_id"]:
        nodes.delete_one({"_id": new["_id"]})
    nodes.update_one({"_id": old["_id"]}, {"$set": {"node_type": "vision_language_model"}})


def _resync_system_nodes(db: Any) -> None:
    """Refresh system nodes that were frozen at their original seed.

    ``seed_system_nodes`` used ``$setOnInsert`` for every field, so a node seeded
    by an older build kept that build's schema forever. Face Detection was left
    advertising ``min_confidence`` (a YOLO knob its executor never reads) and
    declaring a ``faces`` output port while the executor emits ``detections`` —
    so the pipeline editor showed a control that did nothing and hid the three
    that work. Seeding now ``$set``s the code-owned fields, so re-running it
    re-applies them to existing rows.

    Identical effect to ``_baseline`` — both just call the same idempotent
    ``ensure_schema`` — kept as separate migration ids since they were recorded
    separately in ``schema_migrations`` on already-deployed databases.
    """
    from src.repositories.bootstrap import ensure_schema

    ensure_schema(db)


# Ordered list of all migrations. Append-only.
MIGRATIONS: list[Migration] = [
    Migration(
        id="0001_baseline",
        description="Baseline: workspace-scoped indexes + seeded system pipeline nodes.",
        upgrade=_baseline,
    ),
    Migration(
        id="0002_resync_system_nodes",
        description="Re-apply code-owned fields to system pipeline nodes frozen at first seed.",
        upgrade=_resync_system_nodes,
    ),
    Migration(
        id="0003_rename_captioning_to_vision_language_model",
        description="Rename the Captioning system node's identity to vision_language_model "
        "(same _id, so existing pipelines keep resolving it) ahead of its widened, "
        "prompt-configurable, multi-model capability.",
        upgrade=_rename_captioning_to_vision_language_model,
    ),
]


def applied_migration_ids(db: Any) -> set[str]:
    return {doc["_id"] for doc in db[MIGRATIONS_COLLECTION].find({})}


def run_migrations(db: Any) -> list[str]:
    """Apply all pending migrations in order. Returns the ids that ran."""
    applied = applied_migration_ids(db)
    ran: list[str] = []
    for migration in MIGRATIONS:
        if migration.id in applied:
            continue
        logger.info("Applying migration %s — %s", migration.id, migration.description)
        migration.upgrade(db)
        db[MIGRATIONS_COLLECTION].insert_one(
            {
                "_id": migration.id,
                "description": migration.description,
                "applied_at": utcnow(),
            }
        )
        ran.append(migration.id)
    if ran:
        logger.info("Applied %d migration(s): %s", len(ran), ", ".join(ran))
    else:
        logger.info("Schema up to date — no migrations to apply.")
    return ran
