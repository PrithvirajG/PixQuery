from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.api.router import api_router
from src.config import WATCH_ROOT


def create_app() -> FastAPI:
    app = FastAPI(title="PixQuery API")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    photo_dir = Path(WATCH_ROOT)
    photo_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/images_source", StaticFiles(directory=str(photo_dir)), name="images_source")
    app.include_router(api_router)
    return app

