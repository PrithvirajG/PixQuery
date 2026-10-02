"""Encoding a text query into the vector space the stored embeddings live in."""

from __future__ import annotations

from src.logging_config import get_logger

_logger = get_logger(__name__)


class ClipQueryEncoder:
    """Encode search text with the same CLIP variant the worker embeds images with.

    Query and image/caption vectors must come from one model or the distances are
    meaningless, so this deliberately reuses the worker's shared ``ClipModel``
    for ``model_name`` (cached process-wide by ``get_clip_model``, so it loads
    once regardless of how many ``ClipQueryEncoder`` instances ask for it).
    ``SearchService`` builds one of these per text-capable embedding model (see
    ``registry.embedding_model_specs``), since a workspace's assets may have
    been embedded with more than one CLIP variant.

    Implements :class:`~src.infrastructure.vector_store.protocol.QueryEncoder`.
    """

    def __init__(self, model_name: str = "ViT-B/32"):
        self.model_name = model_name

    def encode(self, text: str) -> list[float] | None:
        # Imported per call, not at module scope: CLIP pulls in torch, which must
        # not become an import-time requirement of the API process (it is optional
        # for anything but semantic search).
        try:
            from src.infrastructure.ml.clip import get_clip_model
        except Exception:
            _logger.warning(
                "CLIP is unavailable, so semantic search will degrade to keyword search. "
                "Install the worker extras to enable it.",
                exc_info=True,
            )
            return None

        try:
            vector = get_clip_model(self.model_name).embed_text(text)
        except Exception:
            _logger.warning(
                "CLIP (%s) failed to encode the query", self.model_name, exc_info=True
            )
            return None

        if vector is None:
            _logger.warning("CLIP (%s) returned no embedding for the query", self.model_name)
            return None
        return [float(v) for v in vector]
