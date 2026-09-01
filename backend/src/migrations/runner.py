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
