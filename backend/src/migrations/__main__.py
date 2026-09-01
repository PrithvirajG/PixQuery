"""CLI entrypoint: ``python -m src.migrations`` applies pending migrations."""

from __future__ import annotations

import sys

from src.config import MONGO_DB_NAME, MONGO_URI
from src.logging_config import configure_logging
from src.migrations import MIGRATIONS, applied_migration_ids, run_migrations


def main(argv: list[str] | None = None) -> int:
    configure_logging(process_name="migrations")
    argv = argv if argv is not None else sys.argv[1:]

    from pymongo import MongoClient

    db = MongoClient(MONGO_URI)[MONGO_DB_NAME]

    if "--status" in argv:
        applied = applied_migration_ids(db)
        for migration in MIGRATIONS:
            mark = "applied" if migration.id in applied else "pending"
            print(f"[{mark:>7}] {migration.id} — {migration.description}")
        return 0

    ran = run_migrations(db)
    print(f"Applied {len(ran)} migration(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
