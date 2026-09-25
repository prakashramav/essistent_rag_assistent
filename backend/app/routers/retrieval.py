from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.routers.dependencies import AuthContext, RequireViewer
from app.schemas.retrieval import SearchQueryRequest, SearchResponse
from app.services.retrieval.retrieval_service import RetrievalService

router = APIRouter(prefix="/retrieval", tags=["Retrieval"])


@router.post("/search", response_model=SearchResponse)
async def search_documents(
    request: SearchQueryRequest,
    context: AuthContext = Depends(RequireViewer),
    db: AsyncSession = Depends(get_db),
):
    """
    Perform hybrid vector + full-text search with metadata filtering and reranking.
    Enforces strict organization tenant boundaries.
    """
    return await RetrievalService.search(
        db=db,
        org_id=context.organization_id,
        request=request,
    )


@router.get("/search", response_model=SearchResponse)
async def search_documents_get(
    q: str = Query(..., min_length=1, description="Query string"),
    limit: int = Query(5, ge=1, le=50),
    hybrid: bool = Query(True),
    rerank: bool = Query(True),
    tags: Optional[str] = Query(None, description="Comma-separated tags"),
    context: AuthContext = Depends(RequireViewer),
    db: AsyncSession = Depends(get_db),
):
    """Convenience GET endpoint for search with query parameters."""
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None
    req = SearchQueryRequest(
        query=q,
        limit=limit,
        hybrid=hybrid,
        rerank=rerank,
        tags=tag_list,
    )
    return await RetrievalService.search(
        db=db,
        org_id=context.organization_id,
        request=req,
    )
