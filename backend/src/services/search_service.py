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

        matched: list[dict[str, Any]] = []
        for asset in pool:
            caption = captions.get(asset["_id"], "")
            haystack = f"{asset.get('current_path', '')} {caption}".lower()
            if lowered in haystack:
                matched.append(
                    {**serialize_document(asset), "description": caption, "score": 1.0}
                )

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
            results.append({
                **serialize_document(asset),
                "description": captions.get(asset_id, ""),
                "score": hit.get("certainty", 0.0),
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
        seen: set[str] = set()
        merged: list[dict[str, Any]] = []
        for r in kw + sem:
            if r["_id"] not in seen:
                seen.add(r["_id"])
                merged.append(r)
        merged.sort(key=lambda r: r.get("score", 0.0), reverse=True)
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
        outputs = self.repository.model_outputs.find({"output_type": "caption"})
        return {
            output["asset_id"]: output.get("payload", {}).get("text", "")
            for output in outputs
        }

    def _encode_query(self, query: str) -> list[float] | None:
        """Encode text query to CLIP vector. Returns None if CLIP unavailable."""
        try:
            from transformers import CLIPProcessor, CLIPModel
            import torch
            model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
            processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
            inputs = processor(text=[query], return_tensors="pt", padding=True)
            with torch.no_grad():
                text_features = model.get_text_features(**inputs)
            return text_features[0].tolist()
        except Exception:
            return None


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
