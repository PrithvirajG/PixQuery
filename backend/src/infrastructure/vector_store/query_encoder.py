"""Encoding a text query into the vector space the stored embeddings live in."""

from __future__ import annotations

from src.logging_config import get_logger

_logger = get_logger(__name__)


class ClipQueryEncoder:
    """Encode search text with the same CLIP model the worker embeds images with.

    Query and image/caption vectors must come from one model or the distances are
    meaningless, so this deliberately reuses the worker's shared ``ClipModel``
    (ViT-B/32). The model is cached by ``get_clip_model``, so it loads once per
    process rather than per request.

    Implements :class:`~src.infrastructure.vector_store.protocol.QueryEncoder`.
    """

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
            vector = get_clip_model().embed_text(text)
        except Exception:
            _logger.warning("CLIP failed to encode the query", exc_info=True)
            return None

        if vector is None:
            _logger.warning("CLIP returned no embedding for the query")
            return None
        return [float(v) for v in vector]
