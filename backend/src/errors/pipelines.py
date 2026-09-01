"""Errors raised by ``services.pipeline_service``."""


class PipelineValidationError(ValueError):
    """Raised when a pipeline graph is malformed (bad edge ref or a cycle)."""
