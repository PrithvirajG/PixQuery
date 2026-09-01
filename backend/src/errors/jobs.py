"""Errors raised by ``services.job_service``."""


class JobConflictError(RuntimeError):
    """Raised when a job cannot be dispatched in its current state."""
