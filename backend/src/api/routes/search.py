from typing import Literal

from fastapi import APIRouter, Depends, Query

from src.api.dependencies import get_current_user, get_search_service
from src.services import SearchService

router = APIRouter(tags=["search"])

SearchMode = Literal["semantic", "keyword", "hybrid"]

PAGE_SIZE = 24


@router.get("/search")
async def search(
    query: str = Query(default=""),
    mode: SearchMode = "keyword",
    top_k: int = PAGE_SIZE,
    skip: int = 0,
    threshold: float = 0.0,
    workspace_id: str | None = None,
    search_service: SearchService = Depends(get_search_service),
    current_user: dict = Depends(get_current_user),
):
    results = search_service.search(
        query=query.strip(),
        user_id=current_user["_id"],
        mode=mode,
        top_k=top_k,
        skip=skip,
        threshold=threshold,
        workspace_id=workspace_id,
    )
    return results
