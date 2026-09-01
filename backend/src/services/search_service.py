from __future__ import annotations

from typing import Any, Literal

from src.infrastructure.vector_store.protocol import QueryEncoder, VectorSearchClient
from src.logging_config import get_logger
from src.repositories.file_observations_repository import FileObservationsRepository
from src.repositories.image_assets_repository import ImageAssetsRepository
from src.repositories.model_outputs_repository import ModelOutputsRepository
from src.repositories.workspace_definitions_repository import WorkspaceDefinitionsRepository
from src.services.access_scope import accessible_asset_ids, workspace_asset_ids
from src.services.document_serializer import serialize_document


SearchMode = Literal["semantic", "keyword", "hybrid"]

_logger = get_logger(__name__)

# Weaviate class holding caption/OCR text vectors — what a text query searches.
TEXT_EMBEDDING_CLASS = "TextEmbedding"


class SearchService:
    """Query routing and result ranking. Knows nothing about Weaviate or CLIP.

    The two external capabilities semantic search needs — embedding the query and
    finding nearest neighbours — arrive as injected collaborators rather than
    imports reached for mid-method, so the ranking and fusion logic here can be
    exercised against stubs. Both default to the real adapters and are built
    lazily: constructing a ``SearchService`` performs no I/O, and a deployment
    with no vector store still serves keyword search.
    """

    def __init__(
        self,
        *,
        assets: ImageAssetsRepository,
        observations: FileObservationsRepository,
        workspaces: WorkspaceDefinitionsRepository,
        outputs: ModelOutputsRepository,
        vector_store: VectorSearchClient | None = None,
        query_encoder: QueryEncoder | None = None,
    ):
        self.assets = assets
        self.observations = observations
        self.workspaces = workspaces
        self.outputs = outputs
        self._vector_store = vector_store
        self._query_encoder = query_encoder

    @property
    def vector_store(self) -> VectorSearchClient:
        if self._vector_store is None:
            from src.infrastructure.vector_store.weaviate import WeaviateSearchClient

            self._vector_store = WeaviateSearchClient()
        return self._vector_store

    @property
    def query_encoder(self) -> QueryEncoder:
        if self._query_encoder is None:
            from src.infrastructure.vector_store.query_encoder import ClipQueryEncoder

            self._query_encoder = ClipQueryEncoder()
        return self._query_encoder

    def search(
        self,
        *,
        query: str,
        user_id: str | None = None,
        mode: SearchMode = "keyword",
        top_k: int = 24,
        skip: int = 0,
        threshold: float = 0.0,
        workspace_id: str | None = None,
    ) -> list[dict[str, Any]]:
        # Empty query → browse all images (no text filtering, sorted by latest)
        if not query:
            return self._browse_all(
                user_id=user_id,
                workspace_id=workspace_id,
                top_k=top_k,
                skip=skip,
            )

        if mode == "semantic":
            return self._semantic_search(
                query=query,
                user_id=user_id,
                top_k=top_k,
                skip=skip,
                threshold=threshold,
                workspace_id=workspace_id,
            )
        if mode == "hybrid":
            return self._hybrid_search(
                query=query,
                user_id=user_id,
                top_k=top_k,
                skip=skip,
                threshold=threshold,
                workspace_id=workspace_id,
            )
        return self._keyword_search(
            query=query,
            user_id=user_id,
            top_k=top_k,
            skip=skip,
            workspace_id=workspace_id,
        )

    # ──────────────────────────────────────────────────────────────
    # Browse all (no query)

    def _browse_all(
        self,
        *,
        user_id: str | None,
        workspace_id: str | None,
        top_k: int,
        skip: int,
    ) -> list[dict[str, Any]]:
        captions = self._captions_map()
        assets = self._get_assets(
            user_id=user_id,
            workspace_id=workspace_id,
            limit=top_k,
            skip=skip,
        )
        return [
            {**serialize_document(a), "description": captions.get(a["_id"], "")}
            for a in assets
        ]

    # ──────────────────────────────────────────────────────────────
    # Keyword search

    def _keyword_search(
        self,
        *,
        query: str,
        user_id: str | None,
        top_k: int,
        skip: int,
        workspace_id: str | None,
    ) -> list[dict[str, Any]]:
        lowered = query.lower()
        # Fetch a larger pool to filter from, then paginate manually
        pool = self._get_assets(
            user_id=user_id,
            workspace_id=workspace_id,
            limit=2000,
            skip=0,
        )
        captions = self._captions_map()
        ocr_texts = self._ocr_map()

        matched: list[dict[str, Any]] = []
        for asset in pool:
            caption = captions.get(asset["_id"], "")
            ocr_text = ocr_texts.get(asset["_id"], "")
            path = asset.get("current_path", "")
            fields = []
            if lowered in path.lower():
                fields.append("filename")
            if lowered in caption.lower():
                fields.append("caption")
            if ocr_text and lowered in ocr_text.lower():
                fields.append("ocr")
            if fields:
                matched.append({
                    **serialize_document(asset),
                    "description": caption,
                    "score": 1.0,
                    "match_reason": {"mode": "keyword", "terms": [query], "fields": fields},
                })

        return matched[skip: skip + top_k]

    # ──────────────────────────────────────────────────────────────
    # Semantic search via Weaviate GraphQL

    def _semantic_search(
        self,
        *,
        query: str,
        user_id: str | None,
        top_k: int,
        skip: int,
        threshold: float,
        workspace_id: str | None,
    ) -> list[dict[str, Any]]:
        vector = self._encode_query(query)
        if vector is None:
            # The encoder has already logged *why* it could not encode.
            _logger.info("Semantic search falling back to keyword: query not encodable")
            return self._keyword_search(
                query=query, user_id=user_id,
                top_k=top_k, skip=skip, workspace_id=workspace_id,
            )

        try:
            hits = self.vector_store.near_vector(
                class_name=TEXT_EMBEDDING_CLASS,
                vector=vector,
                top_k=top_k + skip,
                certainty=threshold or 0.0,
            )
        except Exception:
            # A misconfigured or unreachable vector store must not take search
            # down, but it is an operational fault and looks nothing like "CLIP
            # isn't installed" — log it loudly enough to tell the two apart.
            _logger.warning(
                "Vector store query failed; falling back to keyword search",
                exc_info=True,
            )
            return self._keyword_search(
                query=query, user_id=user_id,
                top_k=top_k, skip=skip, workspace_id=workspace_id,
            )

        # hits → [{asset_id, certainty}]
        hits = hits[skip:]
        captions = self._captions_map()
        allowed_ids = self._allowed_asset_ids(user_id=user_id, workspace_id=workspace_id)

        results: list[dict[str, Any]] = []
        for hit in hits:
            asset_id = hit.get("asset_id")
            if allowed_ids is not None and asset_id not in allowed_ids:
                continue
            asset = self.assets.get(asset_id)
            if not asset or not asset.get("active"):
                continue
            certainty = hit.get("certainty", 0.0)
            results.append({
                **serialize_document(asset),
                "description": captions.get(asset_id, ""),
                "score": certainty,
                "match_reason": {"mode": "semantic", "similarity": round(certainty, 3)},
            })
            if len(results) >= top_k:
                break

        return results

    # ──────────────────────────────────────────────────────────────
    # Hybrid search

    def _hybrid_search(
        self,
        *,
        query: str,
        user_id: str | None,
        top_k: int,
        skip: int,
        threshold: float,
        workspace_id: str | None,
    ) -> list[dict[str, Any]]:
        kw = self._keyword_search(
            query=query, user_id=user_id,
            top_k=top_k * 2, skip=0, workspace_id=workspace_id,
        )
        sem = self._semantic_search(
            query=query, user_id=user_id,
            top_k=top_k * 2, skip=0,
            threshold=threshold, workspace_id=workspace_id,
        )
        # Index each signal's contribution so the fused result can explain itself.
        # (Semantic may have fallen back to keyword, so only trust true semantic hits.)
        kw_reason = {r["_id"]: r["match_reason"] for r in kw}
        sem_sim = {
            r["_id"]: r["match_reason"]["similarity"]
            for r in sem
            if r.get("match_reason", {}).get("mode") == "semantic"
        }

        merged = _reciprocal_rank_fusion([kw, sem])
        for result in merged:
            result["match_reason"] = _combine_match_reasons(
                kw_reason.get(result["_id"]), sem_sim.get(result["_id"])
            )
        return merged[skip: skip + top_k]

    # ──────────────────────────────────────────────────────────────
    # Helpers

    def _get_assets(
        self,
        *,
        user_id: str | None,
        workspace_id: str | None,
        limit: int,
        skip: int = 0,
    ) -> list[dict[str, Any]]:
        scope = self._allowed_asset_ids(user_id=user_id, workspace_id=workspace_id)
        if scope is None:
            return self.assets.list_all(active_only=True, limit=limit, skip=skip)
        return self.assets.list_by_ids(scope, limit=limit, skip=skip)

    def _allowed_asset_ids(
        self,
        *,
        user_id: str | None,
        workspace_id: str | None,
    ) -> set[str] | None:
        """Asset IDs this request may see, or None when wholly unrestricted.

        ``workspace_id`` is a *filter*, never a widening: it comes off the query
        string unvalidated, so the workspace's assets are intersected with the
        user's own accessible set rather than replacing it. Passing another
        user's workspace id therefore narrows the result to nothing instead of
        exposing their images.
        """
        workspace_scope = (
            workspace_asset_ids(self.workspaces, self.observations, workspace_id)
            if workspace_id else None
        )
        user_scope = (
            accessible_asset_ids(self.workspaces, self.observations, user_id)
            if user_id else None
        )
        if workspace_scope is None:
            return user_scope
        if user_scope is None:
            return workspace_scope
        return workspace_scope & user_scope

    def _captions_map(self) -> dict[str, str]:
        return self._text_map("caption")

    def _ocr_map(self) -> dict[str, str]:
        return self._text_map("ocr")

    def _text_map(self, output_type: str) -> dict[str, str]:
        """Map asset_id → the ``payload.text`` of its output of this type.

        Where an asset has several outputs of the same type (two pipelines both
        captioning it), the last one wins — search only needs one representative
        string per asset.
        """
        return {
            output["asset_id"]: output.get("payload", {}).get("text", "")
            for output in self.outputs.list_by_type(output_type)
        }

    def _encode_query(self, query: str) -> list[float] | None:
        """Encode a text query into the stored embeddings' vector space.

        Returns None when encoding is unavailable, which is the signal callers use
        to degrade to keyword search. The encoder itself logs the reason.
        """
        return self.query_encoder.encode(query)


# ──────────────────────────────────────────────────────────────────────────────
# Hybrid ranking — Reciprocal Rank Fusion

def _reciprocal_rank_fusion(
    result_lists: list[list[dict[str, Any]]],
    *,
    k: int = 60,
) -> list[dict[str, Any]]:
    """Fuse several ranked result lists into one ordering via RRF.

    RRF score for a document is the sum over each list it appears in of
    ``1 / (k + rank)``. It needs no score normalization, so it combines the
    keyword list (all scored 1.0) and the semantic list (certainty 0–1) robustly
    instead of letting the fixed keyword score dominate.

    The representative dict kept per document preserves a meaningful ``score`` for
    display: the keyword entry (exact match, 1.0) is preferred when present since
    earlier lists are visited first, otherwise the semantic certainty is used.
    """
    fused: dict[str, float] = {}
    representative: dict[str, dict[str, Any]] = {}
    for results in result_lists:
        for rank, item in enumerate(results):
            doc_id = item["_id"]
            fused[doc_id] = fused.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
            if doc_id not in representative:
                representative[doc_id] = item
            elif not representative[doc_id].get("description") and item.get("description"):
                representative[doc_id] = item
    ordered_ids = sorted(fused, key=lambda doc_id: fused[doc_id], reverse=True)
    return [representative[doc_id] for doc_id in ordered_ids]


def _combine_match_reasons(
    keyword_reason: dict[str, Any] | None,
    similarity: float | None,
) -> dict[str, Any]:
    """Merge a doc's keyword and semantic contributions into one explanation."""
    if keyword_reason and similarity is not None:
        return {
            "mode": "hybrid",
            "terms": keyword_reason.get("terms", []),
            "fields": keyword_reason.get("fields", []),
            "similarity": similarity,
        }
    if keyword_reason:
        return keyword_reason
    return {"mode": "semantic", "similarity": similarity or 0.0}
