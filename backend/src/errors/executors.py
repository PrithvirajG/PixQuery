"""Errors raised by pipeline node executors (``services.executors``)."""


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
