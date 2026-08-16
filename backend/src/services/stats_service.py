from __future__ import annotations

from typing import Any

from src.services.document_serializer import serialize_document, serialize_documents


class StatsService:
    def __init__(self, repository):
        self.repository = repository

    def get_overview(self, *, owner_id: str) -> dict[str, Any]:
        return self.repository.get_stats_overview(owner_id=owner_id)

    def list_recent_jobs(self, *, user_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        jobs = self.repository.list_recent_jobs(user_id=user_id, limit=limit)
        return serialize_documents(jobs)
