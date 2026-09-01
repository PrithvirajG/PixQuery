"""Vector store adapters."""

from src.infrastructure.vector_store.protocol import (
    QueryEncoder,
    VectorHit,
    VectorSearchClient,
)
from src.infrastructure.vector_store.query_encoder import ClipQueryEncoder
from src.infrastructure.vector_store.weaviate import (
    WeaviateEmbeddingStore,
    WeaviateSearchClient,
)

__all__ = [
    "ClipQueryEncoder",
    "QueryEncoder",
    "VectorHit",
    "VectorSearchClient",
    "WeaviateEmbeddingStore",
    "WeaviateSearchClient",
]
