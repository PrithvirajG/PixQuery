from typing import Any


def serialize_document(document: dict[str, Any]) -> dict[str, Any]:
    clean = {}
    for key, value in document.items():
        if hasattr(value, "isoformat"):
            clean[key] = value.isoformat()
        else:
            clean[key] = value
    return clean


def serialize_documents(documents) -> list[dict[str, Any]]:
    return [serialize_document(document) for document in documents]

