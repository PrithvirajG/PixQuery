"""Generic time helper.

Moved out of ``models/documents.py`` — timezone-aware "now" has nothing to do
with document schema, it was just defined there first and every repository
ended up importing a models module just to get the current time.
"""

from __future__ import annotations

from datetime import datetime, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
