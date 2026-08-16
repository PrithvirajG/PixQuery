"""MongoDB schema migrations for PixQuery.

Usage:
    python -m src.migrations        # apply pending migrations against MONGO_URI/MONGO_DB_NAME

See ``src/migrations/runner.py`` for how to add a migration.
"""

from src.migrations.runner import (
    MIGRATIONS,
    MIGRATIONS_COLLECTION,
    Migration,
    applied_migration_ids,
    run_migrations,
)

__all__ = [
    "MIGRATIONS",
    "MIGRATIONS_COLLECTION",
    "Migration",
    "applied_migration_ids",
    "run_migrations",
]
