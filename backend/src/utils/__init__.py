"""Generic, domain-agnostic helpers shared across services/repositories/consumers.

Nothing here may import from ``src.services``, ``src.repositories``, or
``src.consumer`` — that's the dividing line from a domain-specific "utility"
module like ``services/access_scope.py`` or ``services/document_serializer.py``,
which stay where they are precisely because they're coupled to PixQuery's own
models. A function belongs here only if it would make sense in a project that
had never heard of workspaces or pipelines.
"""
