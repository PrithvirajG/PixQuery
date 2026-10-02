"""Pipeline node executors.

A node executor turns one pipeline node into a runnable step: it reads keys from
the shared context, performs work, and returns the keys it adds. The registry
maps a node's ``node_type`` to its executor.

Importing this package is intentionally lightweight — heavy model dependencies
(torch, ultralytics, transformers, clip) are imported lazily inside executors
only when they actually run.
"""

from src.errors.executors import NodeExecutionError, PermanentNodeError
from src.services.executors.base import BaseNodeExecutor, ModelSpec, NodeExecutor
from src.services.executors.registry import (
    describe_node_type,
    embedding_model_specs,
    get_executor,
    supported_model_ids,
)

__all__ = [
    "BaseNodeExecutor",
    "ModelSpec",
    "NodeExecutionError",
    "NodeExecutor",
    "PermanentNodeError",
    "describe_node_type",
    "embedding_model_specs",
    "get_executor",
    "supported_model_ids",
]
