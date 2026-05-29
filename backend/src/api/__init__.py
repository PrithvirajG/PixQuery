"""FastAPI application package."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.api.app import create_app

__all__ = ["create_app"]


def __getattr__(name):
    if name == "create_app":
        from src.api.app import create_app

        return create_app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
