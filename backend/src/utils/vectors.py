"""Generic numeric vector helper.

Moved out of ``services/pipeline_execution_service.py`` — L2-normalizing a
vector has no pipeline/embedding-specific knowledge in it.
"""

from __future__ import annotations

import math


def normalize(vector) -> list[float] | None:
    """L2-normalize a vector (numpy array or list) to a plain list of floats."""
    if vector is None:
        return None
    values = [float(v) for v in vector]
    norm = math.sqrt(sum(v * v for v in values))
    if norm == 0:
        return values
    return [v / norm for v in values]
