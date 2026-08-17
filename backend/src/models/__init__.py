"""Pydantic v2 models for every MongoDB collection.

These are the single source of truth for document shapes. The repository builds
documents via ``Model(...).to_doc()`` (which dumps with the ``_id`` alias) instead
of hand-assembling dicts, so the schema is typed, validated, and centralized.

Models are deliberately tolerant on read (``extra="ignore"``) so documents written
under older schema versions still parse; migrations (see ``src.migrations``) bring
stored data forward over time.
"""

from src.models.documents import (
    DEFAULT_EXTENSIONS,
    BaseDocument,
    FileObservation,
    ImageAsset,
    ModelOutput,
    PipelineDefinition,
    PipelineNode,
    PipelineRun,
    ProcessingJob,
    User,
    WorkspaceDefinition,
    WorkspaceMember,
    utcnow,
)

__all__ = [
    "DEFAULT_EXTENSIONS",
    "BaseDocument",
    "FileObservation",
    "ImageAsset",
    "ModelOutput",
    "PipelineDefinition",
    "PipelineNode",
    "PipelineRun",
    "ProcessingJob",
    "User",
    "WorkspaceDefinition",
    "WorkspaceMember",
    "utcnow",
]
