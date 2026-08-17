"""Lightweight, dependency-free MongoDB migration runner.

Each migration has a stable ``id`` and an ``upgrade(db)`` function. Applied ids are
recorded in the ``schema_migrations`` collection, so every migration runs exactly
once and in order. Add a new migration by appending to ``MIGRATIONS`` (keep ids
sortable, e.g. ``0002_...``); never edit or reorder an already-released migration.

Run on deploy via ``python -m src.migrations`` (or automatically at API startup —
see ``RUN_MIGRATIONS_ON_STARTUP``).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable

from src.models import utcnow

logger = logging.getLogger("migrations")

MIGRATIONS_COLLECTION = "schema_migrations"


@dataclass(frozen=True)
class Migration:
    id: str
    description: str
    upgrade: Callable[[Any], None]


def _baseline(db: Any) -> None:
    """Establish the current schema: indexes + seeded system nodes.

    Delegates to the repository so the index definitions live in exactly one place
    (``MongoPipelineRepository.ensure_indexes``); both are idempotent. The seed set
    and the partial-unique index on system ``node_type`` mean a fresh DB comes up
    correct with no follow-up cleanup migrations.
    """
    from src.repositories.mongo_pipeline import MongoPipelineRepository

    MongoPipelineRepository(db)  # __init__ → ensure_indexes() + _seed_system_nodes()


# Ordered list of all migrations. Append-only.
MIGRATIONS: list[Migration] = [
    Migration(
        id="0001_baseline",
        description="Baseline: workspace-scoped indexes + seeded system pipeline nodes.",
        upgrade=_baseline,
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
