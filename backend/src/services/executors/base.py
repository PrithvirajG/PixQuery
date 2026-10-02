from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from src.errors.executors import PermanentNodeError


@runtime_checkable
class NodeExecutor(Protocol):
    """Structural type for a pipeline node executor."""

    node_type: str

    def run(self, context: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        """Run the node and return only the context keys it adds or replaces."""
        ...


@dataclass(frozen=True)
class ModelSpec:
    """One selectable model for a node type.

    ``id`` is the stable value stored on a pipeline node and sent over the API;
    ``label`` is what the inspector's Model dropdown shows; ``version`` is recorded
    as output provenance alongside ``id``.
    """

    id: str
    label: str
    version: str = ""
    # False for a vision-only model (e.g. DINOv2) that can embed an image but has
    # no text tower — it can never answer a text search query, only Embedding
    # reads this today, to decide whether to call the model's embed_text() and
    # whether search should build a query encoder for it at all.
    supports_text: bool = True
    # False for a fixed-task model (BLIP: always produces one unconditioned
    # caption, no instruction-following) vs. a true prompt-following VLM
    # (Qwen2-VL, Moondream2). Only VisionLanguageModel reads this today, to
    # decide whether to pass the node's configured prompt to the model at all,
    # and the inspector uses it to decide whether the Prompt field matters for
    # the currently-selected model.
    supports_prompt: bool = False


class BaseNodeExecutor:
    """Convenience base for built-in executors.

    Subclasses set ``node_type`` and implement :meth:`run`. Model-backed nodes also
    declare ``models`` (the choices the pipeline editor offers) and
    ``default_model``; the chosen id reaches :meth:`run` as ``config["model"]``,
    injected by ``PipelineExecutionService`` from the pipeline node's own ``model``
    field. This class is the single source of truth for which models a node type
    supports — the API advertises exactly this list, so a model only shows up in
    the UI once there's code here that can run it.

    Nodes without a model list set ``model_name`` / ``model_version`` directly for
    output provenance.
    """

    node_type: str = ""
    # "model" (AI inference — the editor shows a Model dropdown and styles it as an
    # intelligence node) or "transform" (image processing / IO).
    kind: str = "transform"
    # Human-readable description of what the node emits, for the inspector — the
    # raw context keys (``detections``, ``labels``) stay in ``context_outputs``.
    outputs_label: str = ""
    models: tuple[ModelSpec, ...] = ()
    default_model: str | None = None
    model_name: str = ""
    model_version: str = ""

    def run(self, context: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def resolve_model(self, config: dict[str, Any]) -> ModelSpec | None:
        """The model this run should use: ``config["model"]``, else the default.

        An id this executor doesn't know is a permanent failure — retrying can't
        make an unsupported model appear. Pipeline saves validate the id up front,
        so reaching this means the model was removed after the pipeline was saved.
        """
        if not self.models:
            return None
        model_id = config.get("model") or self.default_model
        for spec in self.models:
            if spec.id == model_id:
                return spec
        supported = ", ".join(spec.id for spec in self.models)
        raise PermanentNodeError(
            f"Node '{self.node_type}' has no model '{model_id}' (supported: {supported})"
        )

    def provenance(self, config: dict[str, Any]) -> tuple[str, str]:
        """``(model_name, model_version)`` recorded on this run's model_outputs."""
        spec = self.resolve_model(config)
        if spec is not None:
            return spec.id, spec.version
        return self.model_name, self.model_version

    @classmethod
    def describe(cls) -> dict[str, Any]:
        """What the pipeline editor needs to know about this node type."""
        return {
            "kind": cls.kind,
            "executor": cls.__name__,
            "outputs_label": cls.outputs_label,
            "models": [
                {"id": m.id, "label": m.label, "supports_prompt": m.supports_prompt}
                for m in cls.models
            ],
            "default_model": cls.default_model,
        }
