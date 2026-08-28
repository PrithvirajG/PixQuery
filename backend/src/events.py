"""Domain events broadcast to connected UIs in real time.

Events are deliberately **thin**: one names *what changed* and carries just enough
identity to route it (workspace / asset / pipeline) plus the new state. They never
carry a pipeline's output payloads (detections arrays, OCR text, embeddings).

Why thin rather than fat:

* **Authorization stays in one place.** ``GET /images/{id}/detail`` already enforces
  workspace membership. Pushing payloads down a socket would mean re-deriving that
  check per event, per field.
* **Payloads are unbounded.** A detections output can be tens of KB; fanning that to
  every connected tab, for every stage, is a lot of traffic for data the client may
  not even be displaying.
* **Events are lossy, refetches are self-healing.** A tab that was asleep, or that
  reconnected after a drop, converges on the truth by refetching — it never has to
  replay a missed event stream to be correct.

So the contract is: *the socket tells you something changed; the REST endpoint tells
you what it is.* The one exception is ``data`` carrying small scalar facts already
needed to render the transition itself (state name, node type, error message,
delete counts) — enough that a client can update its status pill and shimmer without
a round-trip, while the substantive content still comes from a refetch.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

# The (asset, pipeline) pair moved to a new lifecycle state. `data.state` is one of
# the states in `src.services.image_service` (not_started/queued/processing/…).
EVENT_PIPELINE_STATE = "pipeline_state"

# One node inside a running pipeline finished. Emitted per node so a UI can show
# progress *within* a run rather than a single opaque "processing" span.
EVENT_PIPELINE_STAGE = "pipeline_stage"

# Stored outputs were deleted — for a whole workspace+pipeline, for a single asset,
# or as a side effect of deleting the pipeline itself.
EVENT_OUTPUTS_CLEARED = "outputs_cleared"


@dataclass
class Event:
    """One broadcastable change.

    ``workspace_id`` is the routing/authorization key: the API only forwards an
    event to a socket whose user can reach that workspace.
    """

    type: str
    workspace_id: str | None = None
    asset_id: str | None = None
    pipeline_id: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
    ts: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "workspace_id": self.workspace_id,
            "asset_id": self.asset_id,
            "pipeline_id": self.pipeline_id,
            "data": self.data,
            "ts": self.ts,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_json(cls, raw: str | bytes) -> "Event":
        payload = json.loads(raw)
        return cls(
            type=payload.get("type", ""),
            workspace_id=payload.get("workspace_id"),
            asset_id=payload.get("asset_id"),
            pipeline_id=payload.get("pipeline_id"),
            data=payload.get("data") or {},
            ts=payload.get("ts") or "",
        )


def pipeline_state_event(
    *,
    workspace_id: str | None,
    asset_id: str | None,
    pipeline_id: str | None,
    state: str,
    job_id: str | None = None,
    error: dict[str, Any] | None = None,
) -> Event:
    data: dict[str, Any] = {"state": state}
    if job_id:
        data["job_id"] = job_id
    if error:
        # Only the human-readable message travels — never the stack trace.
        data["error"] = {"message": error.get("message"), "class": error.get("class")}
    return Event(
        type=EVENT_PIPELINE_STATE,
        workspace_id=workspace_id,
        asset_id=asset_id,
        pipeline_id=pipeline_id,
        data=data,
    )


def pipeline_stage_event(
    *,
    workspace_id: str | None,
    asset_id: str | None,
    pipeline_id: str | None,
    node_id: str | None,
    node_type: str,
    index: int,
    total: int,
) -> Event:
    return Event(
        type=EVENT_PIPELINE_STAGE,
        workspace_id=workspace_id,
        asset_id=asset_id,
        pipeline_id=pipeline_id,
        data={
            "node_id": node_id,
            "node_type": node_type,
            # 1-based "stage 2 of 5", ready to render without off-by-one juggling.
            "index": index,
            "total": total,
        },
    )


def outputs_cleared_event(
    *,
    workspace_id: str | None,
    pipeline_id: str | None,
    asset_id: str | None = None,
    counts: dict[str, int] | None = None,
) -> Event:
    return Event(
        type=EVENT_OUTPUTS_CLEARED,
        workspace_id=workspace_id,
        asset_id=asset_id,
        pipeline_id=pipeline_id,
        # `asset_id: None` means "every asset in this workspace" — the client
        # refetches whatever it currently has open.
        data={"counts": counts or {}, "scope": "asset" if asset_id else "workspace"},
    )
