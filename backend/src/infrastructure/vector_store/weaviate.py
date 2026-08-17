from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from src.config import WEAVIATE_URL


class WeaviateEmbeddingStore:
    def __init__(self, url: str = WEAVIATE_URL):
        self.url = url.rstrip("/")
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
            if exc.code == 409:
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

