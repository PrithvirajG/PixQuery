"""Deriving a pipeline definition's version from its shape.

Pure domain logic — no I/O, no framework — used by both the API side
(``JobService``, to resolve the current version before dispatching a manual
reprocess) and the ingestion side (to decide whether an edited pipeline should
reprocess existing assets). It lives in ``services/`` rather than under the
ingestion entry-point layer so a service importing it isn't reaching into a
process it has no business depending on.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def pipeline_version_hash(
    nodes: list[dict[str, Any]], edges: list[dict[str, Any]] | None = None
) -> str:
    """Stable short version string derived from a pipeline's nodes, wiring + config.

    Includes ``edges`` so re-wiring the graph (not just editing a node) yields a new
    version and reprocesses affected assets.
    """
    node_payload = sorted(
        (
            {
                "node_id": node.get("node_id"),
                "pipeline_node_id": node.get("pipeline_node_id"),
                "config_overrides": node.get("config_overrides", {}),
            }
            for node in nodes
        ),
        key=lambda n: (n["node_id"] or "", n["pipeline_node_id"] or ""),
    )
    edge_payload = sorted(
        (
            {
                "from_node_id": edge.get("from_node_id"),
                "to_node_id": edge.get("to_node_id"),
                "from_output": edge.get("from_output"),
                "to_input": edge.get("to_input"),
            }
            for edge in (edges or [])
        ),
        key=lambda e: (e["from_node_id"] or "", e["to_node_id"] or ""),
    )
    digest = hashlib.sha256(
        json.dumps(
            {"nodes": node_payload, "edges": edge_payload}, sort_keys=True, default=str
        ).encode("utf-8")
    ).hexdigest()
    return f"p-{digest[:12]}"
