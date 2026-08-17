from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


class NodeExecutionError(RuntimeError):
    """Raised when a node cannot be executed.

    Covers a missing/unimplemented executor and missing required context inputs.
    The worker treats this like any other processing error: the job is failed
    (and retried) with the message recorded.
    """


class PermanentNodeError(NodeExecutionError):
    """A node error that can never succeed on retry — a pipeline/config problem.

    Examples: an unknown or unimplemented node type, a node missing from the
    library, a graph cycle, or a required input no upstream node produces. The
    worker fails these jobs immediately instead of burning retries with backoff.
    """


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
