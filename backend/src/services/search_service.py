from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Literal

from src.services.document_serializer import serialize_document


SearchMode = Literal["semantic", "keyword", "hybrid"]


class SearchService:
    def __init__(self, repository):
        self.repository = repository

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
            return self._keyword_search(
                query=query, user_id=user_id,
                top_k=top_k, skip=skip, workspace_id=workspace_id,
            )

        try:
            from src.config import WEAVIATE_URL
            hits = _weaviate_near_vector(
                url=WEAVIATE_URL,
                class_name="TextEmbedding",
                vector=vector,
                top_k=top_k + skip,
                certainty=threshold or 0.0,
            )
        except Exception:
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
            asset = self.repository.get_asset(asset_id)
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
        if workspace_id:
            workspace = self.repository.get_workspace(workspace_id)
            if workspace:
                ws_id = workspace["_id"]
                # Support both new (workspace_id) and legacy (watch_root_id) field names
                obs = list(
                    self.repository.file_observations.find(
                        {"$or": [
                            {"workspace_id": ws_id},
                            {"watch_root_id": workspace.get("watch_root_id", "__none__")},
                        ], "status": "active"}
                    )
                )
                asset_ids = [o["asset_id"] for o in obs]
                return list(
                    self.repository.image_assets.find(
                        {"_id": {"$in": asset_ids}, "active": True}
                    )
                    .sort("latest_seen_at", -1)
                    .skip(skip)
                    .limit(limit)
                )
        return self.repository.list_active_assets(user_id=user_id, limit=limit, skip=skip)

    def _allowed_asset_ids(
        self,
        *,
        user_id: str | None,
        workspace_id: str | None,
    ) -> set[str] | None:
        """Return the set of asset IDs visible to this user/workspace, or None for no restriction."""
        if workspace_id:
            workspace = self.repository.get_workspace(workspace_id)
            if workspace:
                ws_id = workspace["_id"]
                obs = list(
                    self.repository.file_observations.find(
                        {"$or": [
                            {"workspace_id": ws_id},
                            {"watch_root_id": workspace.get("watch_root_id", "__none__")},
                        ], "status": "active"}
                    )
                )
                return {o["asset_id"] for o in obs}
        if user_id:
            assets = self.repository.list_active_assets(user_id=user_id, limit=10000)
            return {a["_id"] for a in assets}
        return None

    def _captions_map(self) -> dict[str, str]:
        return self._text_output_map("caption")

    def _ocr_map(self) -> dict[str, str]:
        return self._text_output_map("ocr")

    def _text_output_map(self, output_type: str) -> dict[str, str]:
        outputs = self.repository.model_outputs.find({"output_type": output_type})
        return {
            output["asset_id"]: output.get("payload", {}).get("text", "")
            for output in outputs
        }

    def _encode_query(self, query: str) -> list[float] | None:
        """Encode a text query to a CLIP vector. Returns None if CLIP unavailable.

        Uses the same shared ``ClipModel`` (clip ViT-B/32) that the worker uses to
        embed images, so the query and the stored image/caption embeddings live in
        one vector space. The model is cached, so it loads once — not per request.
        """
        try:
            from src.pipelines.processing.models.clip import get_clip_model

            vector = get_clip_model().embed_text(query)
            if vector is None:
                return None
            return [float(v) for v in vector]
        except Exception:
            return None


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


# ──────────────────────────────────────────────────────────────────────────────
# Weaviate helper — raw GraphQL nearVector query

def _weaviate_near_vector(
    *,
    url: str,
    class_name: str,
    vector: list[float],
    top_k: int,
    certainty: float,
) -> list[dict[str, Any]]:
    gql = {
        "query": f"""
        {{
          Get {{
            {class_name}(
              nearVector: {{
                vector: {json.dumps(vector)}
                certainty: {certainty}
              }}
              limit: {top_k}
            ) {{
              asset_id
              text
              _additional {{ certainty id }}
            }}
          }}
        }}
        """
    }
    data = json.dumps(gql).encode("utf-8")
    req = urllib.request.Request(
        f"{url.rstrip('/')}/v1/graphql",
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        body = json.loads(resp.read().decode("utf-8"))

    hits = body.get("data", {}).get("Get", {}).get(class_name, []) or []
    return [
        {
            "asset_id": h.get("asset_id"),
            "certainty": h.get("_additional", {}).get("certainty", 0.0),
        }
        for h in hits
        if h.get("asset_id")
    ]
