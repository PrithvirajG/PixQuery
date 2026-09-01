"""Pure data access for the ``users`` collection."""

from __future__ import annotations

import re
from typing import Any

from src.models import User


class UsersRepository:
    def __init__(self, database):
        self.collection = database["users"]

    def ensure_indexes(self) -> None:
        self.collection.create_index("username", unique=True)

    def create(self, username: str, password_hash: str) -> dict[str, Any]:
        user = User(username=username, hashed_password=password_hash).to_doc()
        self.collection.insert_one(user)
        return user

    def get(self, user_id: str) -> dict[str, Any] | None:
        return self.collection.find_one({"_id": user_id})

    def get_by_username(self, username: str) -> dict[str, Any] | None:
        return self.collection.find_one({"username": username})

    def count(self) -> int:
        return self.collection.count_documents({})

    def search_by_username_prefix(
        self, prefix: str, *, exclude_ids: set[str] | None = None, limit: int = 10
    ) -> list[dict[str, Any]]:
        exclude_ids = exclude_ids or set()
        pattern = f"^{re.escape(prefix)}"
        cursor = self.collection.find({"username": {"$regex": pattern, "$options": "i"}})
        results: list[dict[str, Any]] = []
        for user in cursor:
            if user["_id"] in exclude_ids:
                continue
            results.append({"user_id": user["_id"], "username": user["username"]})
            if len(results) >= limit:
                break
        return results
