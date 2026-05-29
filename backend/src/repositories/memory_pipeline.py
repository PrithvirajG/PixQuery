from __future__ import annotations

from copy import deepcopy
from typing import Any

from src.repositories.mongo_pipeline import MongoPipelineRepository, utcnow


class _Cursor:
    def __init__(self, docs: list[dict[str, Any]]):
        self.docs = docs

    def sort(self, field: str, direction: int):
        reverse = direction < 0
        self.docs.sort(key=lambda doc: doc.get(field) or "", reverse=reverse)
        return self

    def skip(self, count: int):
        self.docs = self.docs[count:]
        return self

    def limit(self, count: int):
        self.docs = self.docs[:count]
        return self

    def __iter__(self):
        return iter(deepcopy(self.docs))


class _MemoryCollection:
    def __init__(self):
        self.docs: list[dict[str, Any]] = []

    def create_index(self, *args, **kwargs):
        return None

    def insert_one(self, doc):
        self.docs.append(deepcopy(doc))

    def find_one(self, query):
        for doc in self.docs:
            if _matches(doc, query):
                return deepcopy(doc)
        return None

    def find(self, query):
        return _Cursor([deepcopy(doc) for doc in self.docs if _matches(doc, query)])

    def update_one(self, query, update, upsert=False):
        for doc in self.docs:
            if _matches(doc, query):
                _apply_update(doc, update)
                return
        if upsert:
            doc = dict(query)
            _apply_update(doc, update, inserting=True)
            self.docs.append(doc)

    def update_many(self, query, update):
        for doc in self.docs:
            if _matches(doc, query):
                _apply_update(doc, update)

    def find_one_and_update(self, query, update, return_document=True):
        for doc in self.docs:
            if _matches(doc, query):
                _apply_update(doc, update)
                return deepcopy(doc)
        return None

    def distinct(self, field, query):
        return list({doc.get(field) for doc in self.docs if _matches(doc, query)})


class _MemoryDatabase(dict):
    def __getitem__(self, name):
        if name not in self:
            self[name] = _MemoryCollection()
        return dict.__getitem__(self, name)


class InMemoryPipelineRepository(MongoPipelineRepository):
    def __init__(self):
        super().__init__(_MemoryDatabase())


def _matches(doc, query):
    for key, value in query.items():
        if key == "$or":
            if not any(_matches(doc, branch) for branch in value):
                return False
        elif isinstance(value, dict) and "$nin" in value:
            if doc.get(key) in value["$nin"]:
                return False
        elif isinstance(value, dict) and "$in" in value:
            if doc.get(key) not in value["$in"]:
                return False
        elif doc.get(key) != value:
            return False
    return True


def _apply_update(doc, update, inserting=False):
    for key, value in update.get("$set", {}).items():
        doc[key] = value
    if inserting:
        for key, value in update.get("$setOnInsert", {}).items():
            doc[key] = value
    for key, value in update.get("$inc", {}).items():
        doc[key] = doc.get(key, 0) + value
    doc.setdefault("updated_at", utcnow())
