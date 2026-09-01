"""Errors raised by ``services.workspace_service``."""


class WorkspaceAccessError(PermissionError):
    """Raised when the acting user lacks the role required for an operation."""


class WorkspaceValidationError(ValueError):
    """Raised when an operation is invalid for the workspace's current state."""
