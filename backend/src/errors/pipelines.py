"""Errors raised by ``services.pipeline_service``."""


class PipelineValidationError(ValueError):
    """Raised when a pipeline graph is malformed (bad edge ref or a cycle)."""


class PipelineNodeCreationDisabledError(PermissionError):
    """Raised when a user tries to add a new node type to the shared node library.

    Node *library* creation (a brand-new ``node_type``) is disabled for every
    user for now — configuring an existing node's settings on a specific
    pipeline (``config_overrides``) is unaffected and stays fully open.
    """
