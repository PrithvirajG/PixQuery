from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any

from src.config import WEAVIATE_URL
from src.infrastructure.vector_store.protocol import VectorHit

# Every embedding-class property list shares this shape; TextEmbedding adds `text`.
_IMAGE_PROPERTIES = [
    {"name": "asset_id", "dataType": ["text"]},
    {"name": "content_sha256", "dataType": ["text"]},
    {"name": "workspace_id", "dataType": ["text"]},
    {"name": "pipeline_id", "dataType": ["text"]},
    {"name": "pipeline_version", "dataType": ["text"]},
    {"name": "active", "dataType": ["boolean"]},
]
_TEXT_PROPERTIES = [
    {"name": "asset_id", "dataType": ["text"]},
    {"name": "content_sha256", "dataType": ["text"]},
    {"name": "workspace_id", "dataType": ["text"]},
    {"name": "text", "dataType": ["text"]},
    {"name": "pipeline_id", "dataType": ["text"]},
    {"name": "pipeline_version", "dataType": ["text"]},
    {"name": "active", "dataType": ["boolean"]},
]

# "clip" is the one embedding model id that predates per-model classes — every
# vector ever written for it lives in the plain "ImageEmbedding"/"TextEmbedding"
# classes, so it keeps those exact names rather than getting a suffixed one.
# Weaviate has no rename-class operation, so this is what makes adding a new
# embedding model migration-free: existing data and queries for "clip" are
# untouched, and every other model just gets its own freshly-created class.
_LEGACY_IMAGE_CLASS = {"clip": "ImageEmbedding"}
_LEGACY_TEXT_CLASS = {"clip": "TextEmbedding"}


def image_class_name(model_id: str) -> str:
    """The Weaviate class an embedding model's image vectors live in.

    One class per model, never shared: Weaviate's HNSW index requires every
    vector in a class to have the same length, and different embedding models
    produce different-length (or same-length but not comparable — CLIP vs.
    DINOv2 both happen to be 768-d) vectors. Mixing them in one class either
    fails the insert outright or makes nearest-neighbour queries meaningless.
    """
    return _LEGACY_IMAGE_CLASS.get(model_id) or f"ImageEmbedding{_pascal(model_id)}"


def text_class_name(model_id: str) -> str:
    """The Weaviate class an embedding model's text (caption) vectors live in.

    Only ever called for a model with ``ModelSpec.supports_text`` — a model with
    no text tower (DINOv2) never has caption vectors to store or query.
    """
    return _LEGACY_TEXT_CLASS.get(model_id) or f"TextEmbedding{_pascal(model_id)}"


def _pascal(model_id: str) -> str:
    """``"clip_vit_l14"`` -> ``"ClipVitL14"`` — a valid Weaviate class-name suffix."""
    return "".join(part.capitalize() for part in re.split(r"[_\-]+", model_id) if part)


class _WeaviateHttp:
    """Shared REST/GraphQL transport for the Weaviate adapters.

    Construction is deliberately side-effect free — no schema calls, no
    connection — so a read-only client can be built cheaply on any code path,
    including ones that must not touch the network at import time.
    """

    def __init__(self, url: str = WEAVIATE_URL):
        self.url = url.rstrip("/")

    def _request(self, method: str, path: str, body: dict[str, Any] | None = None):
        data = None if body is None else json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            f"{self.url}{path}",
            data=data,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                response_body = response.read()
                if not response_body:
                    return None
                return json.loads(response_body.decode("utf-8"))
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise urllib.error.HTTPError(
                exc.url, exc.code,
                f"{exc.reason} — {error_body}",
                exc.headers, None,
            ) from None


class WeaviateSearchClient(_WeaviateHttp):
    """Read-only nearest-neighbour queries — the search half of the store.

    Split from :class:`WeaviateEmbeddingStore` (the write half) so that reading
    never triggers schema creation: search is a query path and has no business
    mutating the store's shape. Implements
    :class:`~src.infrastructure.vector_store.protocol.VectorSearchClient`.
    """

    def near_vector(
        self,
        *,
        class_name: str,
        vector: list[float],
        top_k: int,
        certainty: float = 0.0,
    ) -> list[VectorHit]:
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
        body = self._request("POST", "/v1/graphql", gql) or {}
        hits = body.get("data", {}).get("Get", {}).get(class_name, []) or []
        return [
            VectorHit(
                asset_id=hit["asset_id"],
                certainty=hit.get("_additional", {}).get("certainty", 0.0),
            )
            for hit in hits
            if hit.get("asset_id")
        ]


class WeaviateEmbeddingStore(_WeaviateHttp):
    def __init__(self, url: str = WEAVIATE_URL):
        super().__init__(url)
        # Classes confirmed to exist this process, so a busy pipeline worker
        # doesn't re-check schema on every single upsert — see _ensure_class.
        self._known_classes: set[str] = set()
        self.ensure_schema()

    def ensure_schema(self) -> None:
        # Only the legacy default-model classes are created eagerly, matching
        # what every deployment already has. Every other embedding model's
        # classes are created lazily, on that model's first upsert (_ensure_class)
        # — so adding a model to EmbeddingExecutor never requires a schema-side
        # deploy step here.
        self._ensure_class("ImageEmbedding", _IMAGE_PROPERTIES)
        self._ensure_class("TextEmbedding", _TEXT_PROPERTIES)

    def upsert_image_embedding(
        self, *, vector: list[float], properties: dict[str, Any], model_id: str = "clip"
    ) -> None:
        class_name = image_class_name(model_id)
        self._ensure_class(class_name, _IMAGE_PROPERTIES)
        self._upsert(class_name, "image", vector, properties)

    def upsert_text_embedding(
        self, *, vector: list[float], properties: dict[str, Any], model_id: str = "clip"
    ) -> None:
        class_name = text_class_name(model_id)
        self._ensure_class(class_name, _TEXT_PROPERTIES)
        self._upsert(class_name, "text", vector, properties)

    def close(self) -> None:
        return None

    def _upsert(
        self,
        class_name: str,
        prefix: str,
        vector: list[float],
        properties: dict[str, Any],
    ) -> None:
        obj_id = _stable_uuid(prefix, properties)
        body = {
            "id": obj_id,
            "class": class_name,
            "properties": properties,
            "vector": vector,
        }
        try:
            # Try to create first
            self._request("POST", "/v1/objects", body)
        except urllib.error.HTTPError as exc:
            # Duplicate-id responses: 409 per the REST spec, but this Weaviate
            # version actually answers 422 with an "already exists" message —
            # handle both rather than just the documented one.
            if exc.code in (409, 422):
                # Object already exists — update it in place
                self._request("PUT", f"/v1/objects/{obj_id}", body)
            else:
                raise

    def _ensure_class(self, class_name: str, properties: list[dict[str, Any]]) -> None:
        if class_name in self._known_classes:
            return
        if not self._exists(f"/v1/schema/{class_name}"):
            self._request(
                "POST",
                "/v1/schema",
                {"class": class_name, "vectorizer": "none", "properties": properties},
            )
        self._known_classes.add(class_name)

    def _exists(self, path: str) -> bool:
        try:
            self._request("GET", path)
            return True
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return False
            raise


def _stable_uuid(prefix: str, properties: dict[str, Any]) -> str:
    import uuid

    key = ":".join(
        [
            prefix,
            properties["asset_id"],
            properties["pipeline_id"],
            properties["pipeline_version"],
        ]
    )
    return str(uuid.uuid5(uuid.NAMESPACE_URL, key))

