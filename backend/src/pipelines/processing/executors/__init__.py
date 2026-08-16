"""Pipeline node executors.

A node executor turns one pipeline node into a runnable step: it reads keys from
the shared context, performs work, and returns the keys it adds. The registry
maps a node's ``node_type`` to its executor.

Importing this package is intentionally lightweight — heavy model dependencies
(torch, ultralytics, transformers, clip) are imported lazily inside executors
only when they actually run.
"""

from src.pipelines.processing.executors.base import (
    BaseNodeExecutor,
    NodeExecutionError,
    NodeExecutor,
    PermanentNodeError,
)
from src.pipelines.processing.executors.registry import get_executor

__all__ = [
    "BaseNodeExecutor",
    "NodeExecutionError",
    "NodeExecutor",
    "PermanentNodeError",
    "get_executor",
]
