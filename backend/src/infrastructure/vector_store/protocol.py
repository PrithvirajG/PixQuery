"""Contracts for the vector-store adapters the service layer depends on.

Search needs only one operation — "give me the nearest neighbours of this
vector" — so that is all :class:`VectorSearchClient` asks for. Keeping it this
narrow is what lets ``SearchService`` be exercised against a stub instead of a
live Weaviate: an implementation is a single method, not an HTTP client.
"""

from __future__ import annotations

from typing import Any, Protocol, TypedDict, runtime_checkable


class VectorHit(TypedDict):
    """One nearest-neighbour result: which asset, and how close it scored."""

    asset_id: str
    certainty: float


@runtime_checkable
class VectorSearchClient(Protocol):
    def near_vector(
        self,
        *,
        class_name: str,
        vector: list[float],
        top_k: int,
        certainty: float = ...,
    ) -> list[VectorHit]:
        """Nearest neighbours of ``vector``, best first.

        Implementations raise on transport/backend failure rather than returning
        an empty list — the caller distinguishes "the store is down" (degrade and
        log) from "nothing matched" (a legitimately empty result).
        """
        ...


@runtime_checkable
class QueryEncoder(Protocol):
    def encode(self, text: str) -> list[float] | None:
        """Embed a search query into the image/caption vector space.

        Returns ``None`` when encoding is unavailable (model missing, load
        failure) so the caller can fall back to keyword search. Anything else is
        an unexpected error and should propagate.
        """
        ...
