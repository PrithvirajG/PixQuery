"""Every custom exception in the backend, one module per owning flow/service.

Centralized so a route handler (or anything else translating a failure into a
response) has one predictable place to import an error type from, instead of
needing to know which service/util module happens to define it. Each module
here still belongs conceptually to the flow it's named after — ``jobs.py``'s
``JobConflictError`` is still "a job-service error" — this package just holds
the class definitions themselves, not the logic that raises or handles them.
"""

from src.errors.executors import NodeExecutionError, PermanentNodeError
from src.errors.files import FileNotStableError
from src.errors.graph import GraphCycleError, UnknownNodeError
from src.errors.jobs import JobConflictError
from src.errors.pipelines import PipelineValidationError
from src.errors.workspaces import WorkspaceAccessError, WorkspaceValidationError

__all__ = [
    "FileNotStableError",
    "GraphCycleError",
    "JobConflictError",
    "NodeExecutionError",
    "PermanentNodeError",
    "PipelineValidationError",
    "UnknownNodeError",
    "WorkspaceAccessError",
    "WorkspaceValidationError",
]
