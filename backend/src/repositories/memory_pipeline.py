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


class _DeleteResult:
    def __init__(self, deleted_count: int):
        self.deleted_count = deleted_count


class _MemoryCollection:
    def __init__(self):
        self.docs: list[dict[str, Any]] = []

    def create_index(self, *args, **kwargs):
        return None

    def drop_index(self, *args, **kwargs):
        return None

    def insert_one(self, doc):
        self.docs.append(deepcopy(doc))

    def count_documents(self, query):
        return sum(1 for doc in self.docs if _matches(doc, query))

    def delete_one(self, query):
        for i, doc in enumerate(self.docs):
            if _matches(doc, query):
                del self.docs[i]
                return _DeleteResult(1)
        return _DeleteResult(0)

    def delete_many(self, query):
        kept = [doc for doc in self.docs if not _matches(doc, query)]
        removed = len(self.docs) - len(kept)
        self.docs = kept
        return _DeleteResult(removed)

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
    def __init__(self, event_sink=None):
        # ``events`` collects everything emitted, so a test can assert on the live
        # updates a change produces without standing up a broker. Passing an
        # explicit sink still works and takes precedence.
        self.events: list = []
        super().__init__(_MemoryDatabase(), event_sink=event_sink or self.events.append)


def _matches(doc, query):
    import re

    for key, value in query.items():
        if key == "$or":
            if not any(_matches(doc, branch) for branch in value):
                return False
        elif "." in key:
            # Dot-notation, including "array.field" semantics (match if any element matches).
            head, tail = key.split(".", 1)
            container = doc.get(head)
            if isinstance(container, list):
                if not any(_matches(item, {tail: value}) for item in container):
                    return False
            elif isinstance(container, dict):
                if not _matches(container, {tail: value}):
                    return False
            else:
                return False
        elif isinstance(value, dict) and "$regex" in value:
            flags = re.IGNORECASE if "i" in value.get("$options", "") else 0
            if not re.search(value["$regex"], str(doc.get(key, "")), flags):
                return False
        elif isinstance(value, dict) and "$nin" in value:
            if doc.get(key) in value["$nin"]:
                return False
        elif isinstance(value, dict) and "$in" in value:
            field = doc.get(key)
            # Mongo's $in matches if an array field shares ANY element with the list.
            if isinstance(field, list):
                if not any(item in value["$in"] for item in field):
                    return False
            elif field not in value["$in"]:
                return False
        else:
            field = doc.get(key)
            # Equality against an array field is array-contains in Mongo
            # (e.g. {"pipeline_ids": "p1"} matches a doc whose list holds "p1").
            if isinstance(field, list) and not isinstance(value, list):
                if value not in field:
                    return False
            elif field != value:
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
