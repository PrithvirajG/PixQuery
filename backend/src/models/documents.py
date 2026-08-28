from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return str(uuid4())


DEFAULT_EXTENSIONS = [".jpg", ".jpeg", ".png", ".webp"]


class BaseDocument(BaseModel):
    """Base for top-level collection documents.

    - ``id`` maps to Mongo's ``_id`` (construct with ``id=`` or ``_id=``).
    - ``extra="ignore"`` keeps reads tolerant of fields from older schema versions.
    - ``to_doc()`` returns the dict to persist (keyed by ``_id``).
    """

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id: str = Field(default_factory=_new_id, alias="_id")

    def to_doc(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True)


class User(BaseDocument):
    username: str
    hashed_password: str
    created_at: datetime = Field(default_factory=utcnow)


class ImageAsset(BaseDocument):
    content_sha256: str
    # Assets are scoped per workspace: identity is (workspace_id, content_sha256).
    workspace_id: str | None = None
    mime_type: str | None = None
    size_bytes: int
    current_path: str
    active: bool = True
    owner_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    first_seen_at: datetime = Field(default_factory=utcnow)
    latest_seen_at: datetime = Field(default_factory=utcnow)


class FileObservation(BaseDocument):
    """Where an asset's bytes appear inside a workspace (path + liveness)."""

    asset_id: str
    workspace_id: str
    relative_path: str
    absolute_path: str
    content_sha256: str
    status: str = "active"  # "active" | "missing"
    first_seen_at: datetime = Field(default_factory=utcnow)
    last_seen_at: datetime = Field(default_factory=utcnow)
    missing_since: datetime | None = None


class ProcessingJob(BaseDocument):
    """One job per (workspace, asset, pipeline, version)."""

    workspace_id: str | None = None
    asset_id: str
    pipeline_id: str
    pipeline_version: str
    status: str = "queued"  # queued | processing | completed | failed
    attempt_count: int = 0
    last_error: dict[str, Any] | None = None
    next_attempt_at: datetime = Field(default_factory=utcnow)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class PipelineRun(BaseDocument):
    """One record per job execution attempt."""

    job_id: str
    asset_id: str
    pipeline_id: str
    pipeline_version: str
    status: str = "processing"  # processing | completed | failed
    error: dict[str, Any] | None = None
    started_at: datetime = Field(default_factory=utcnow)
    finished_at: datetime | None = None


class ModelOutput(BaseDocument):
    """A single node/model output for an asset within a pipeline run."""

    asset_id: str
    workspace_id: str | None = None
    pipeline_run_id: str
    # Denormalized so outputs can be grouped by pipeline without joining runs.
    pipeline_id: str | None = None
    pipeline_version: str | None = None
    model_name: str
    model_version: str
    output_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    node_id: str | None = None
    node_type: str | None = None
    order: int | None = None
    created_at: datetime = Field(default_factory=utcnow)


class WorkspaceMember(BaseModel):
    """Embedded member entry inside a workspace (not its own collection)."""

    model_config = ConfigDict(extra="ignore")

    user_id: str
    role: str = "viewer"  # "viewer" | "editor"  (owner is tracked via owner_id)
    added_at: datetime = Field(default_factory=utcnow)


class WorkspaceDefinition(BaseDocument):
    name: str
    workspace_path: str
    owner_id: str
    active: bool = True
    pipeline_ids: list[str] = Field(default_factory=list)
    extensions: list[str] = Field(default_factory=lambda: list(DEFAULT_EXTENSIONS))
    members: list[WorkspaceMember] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utcnow)


class PipelineNode(BaseDocument):
    """Reusable node-library entry (system-defined or user-defined)."""

    name: str
    description: str = ""
    node_type: str
    context_inputs: list[str] = Field(default_factory=list)
    context_outputs: list[str] = Field(default_factory=list)
    config_schema: dict[str, Any] = Field(default_factory=dict)
    default_config: dict[str, Any] = Field(default_factory=dict)
    owner_id: str  # "system" for built-ins
    created_at: datetime = Field(default_factory=utcnow)


class PipelineDefinition(BaseDocument):
    """A named DAG of pipeline-node references.

    ``nodes`` are the vertices — each ``{node_id, pipeline_node_id, config_overrides,
    position}`` — and ``edges`` are the wiring ``{edge_id, from_node_id, to_node_id,
    from_output?, to_input?}``. Both are built by ``PipelineService._build_graph``.
    A straight chain is just a DAG whose edges form one line; the executor
    topologically sorts and runs it.
    """

    name: str
    description: str = ""
    owner_id: str
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    edges: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
