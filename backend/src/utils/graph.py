"""Generic directed-graph helpers: topological ordering and cycle detection.

Consolidates what used to be two independent implementations of Kahn's
algorithm — ``pipeline_execution_service.py``'s ``_topological_order`` and
``pipeline_service.py``'s ``_assert_acyclic`` — over the same node-id/edge-dict
shape (edges keyed by ``from_node_id``/``to_node_id``). Both still exist as
thin, domain-specific wrappers that call :func:`topological_order` and
translate its exceptions into their own service's error type; the algorithm
itself now lives in exactly one place.
"""

from __future__ import annotations

from typing import Any, Iterable

from src.errors.graph import GraphCycleError, UnknownNodeError


def topological_order(node_ids: Iterable[str], edges: list[dict[str, Any]]) -> list[str]:
    """Kahn's algorithm. Raises :class:`UnknownNodeError` or :class:`GraphCycleError`.

    Zero-indegree nodes are processed in insertion order, so a linear chain
    comes back in its authored order and the result is deterministic.
    """
    node_ids = list(node_ids)
    known = set(node_ids)
    indegree = {nid: 0 for nid in node_ids}
    adjacency: dict[str, list[str]] = {nid: [] for nid in node_ids}
    for edge in edges:
        frm, to = edge["from_node_id"], edge["to_node_id"]
        if frm not in known or to not in known:
            raise UnknownNodeError(f"Edge references an unknown node ({frm} → {to})")
        adjacency[frm].append(to)
        indegree[to] += 1

    ready = [nid for nid in node_ids if indegree[nid] == 0]
    order: list[str] = []
    while ready:
        nid = ready.pop(0)
        order.append(nid)
        for nxt in adjacency[nid]:
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                ready.append(nxt)

    if len(order) != len(node_ids):
        raise GraphCycleError("Graph has a cycle")
    return order
