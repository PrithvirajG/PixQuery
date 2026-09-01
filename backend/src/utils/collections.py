"""Generic list/collection helpers.

Moved out of ``services/image_service.py`` — ranking items by frequency has
nothing image- or detection-specific about it.
"""

from __future__ import annotations


def top_by_frequency(items: list, limit: int = 3) -> str:
    """Rank items by frequency and render as ``"a×3, b×2, c"`` (``×1`` omitted)."""
    counts: dict = {}
    for item in items:
        if item:
            counts[item] = counts.get(item, 0) + 1
    ordered = sorted(counts.items(), key=lambda kv: -kv[1])[:limit]
    return ", ".join(f"{name}×{n}" if n > 1 else name for name, n in ordered)
