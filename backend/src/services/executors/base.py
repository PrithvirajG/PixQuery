from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class NodeExecutor(Protocol):
    """Structural type for a pipeline node executor."""

    node_type: str

    def run(self, context: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        """Run the node and return only the context keys it adds or replaces."""
        ...


class BaseNodeExecutor:
    """Convenience base for built-in executors.

    Subclasses set ``node_type`` (and optionally ``model_name`` /
    ``model_version`` for output provenance) and implement :meth:`run`.
    """

    node_type: str = ""
    model_name: str = ""
    model_version: str = ""

    def run(self, context: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError
