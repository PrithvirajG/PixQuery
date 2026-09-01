from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from src.config import WEAVIATE_URL
from src.infrastructure.vector_store.protocol import VectorHit


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
        self.ensure_schema()

    def ensure_schema(self) -> None:
        for class_name, properties in {
            "ImageEmbedding": [
                {"name": "asset_id", "dataType": ["text"]},
                {"name": "content_sha256", "dataType": ["text"]},
                {"name": "workspace_id", "dataType": ["text"]},
                {"name": "pipeline_id", "dataType": ["text"]},
                {"name": "pipeline_version", "dataType": ["text"]},
                {"name": "active", "dataType": ["boolean"]},
            ],
            "TextEmbedding": [
                {"name": "asset_id", "dataType": ["text"]},
                {"name": "content_sha256", "dataType": ["text"]},
                {"name": "workspace_id", "dataType": ["text"]},
                {"name": "text", "dataType": ["text"]},
                {"name": "pipeline_id", "dataType": ["text"]},
                {"name": "pipeline_version", "dataType": ["text"]},
                {"name": "active", "dataType": ["boolean"]},
            ],
        }.items():
            if self._exists(f"/v1/schema/{class_name}"):
                continue
            self._request(
                "POST",
                "/v1/schema",
                {
                    "class": class_name,
                    "vectorizer": "none",
                    "properties": properties,
                },
            )

    def upsert_image_embedding(self, *, vector: list[float], properties: dict[str, Any]) -> None:
        self._upsert("ImageEmbedding", "image", vector, properties)

    def upsert_text_embedding(self, *, vector: list[float], properties: dict[str, Any]) -> None:
        self._upsert("TextEmbedding", "text", vector, properties)

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

