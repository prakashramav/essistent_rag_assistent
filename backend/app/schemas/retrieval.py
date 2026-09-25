import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SearchQueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000, description="Search query string")
    limit: int = Field(5, ge=1, le=50, description="Top K results to return after reranking")
    candidate_k: int = Field(20, ge=1, le=100, description="Number of candidates to gather from hybrid search before rerank")
    hybrid: bool = Field(True, description="Enable hybrid search combining pgvector dense search with Postgres FTS")
    alpha: float = Field(0.7, ge=0.0, le=1.0, description="Weight for dense vector vs sparse full-text search (1.0 = pure vector)")
    rerank: bool = Field(True, description="Apply reranking model on top candidates")
    
    # Metadata filters
    document_ids: Optional[List[uuid.UUID]] = Field(None, description="Filter search to specific document IDs")
    tags: Optional[List[str]] = Field(None, description="Filter by document tags")
    uploader_id: Optional[uuid.UUID] = Field(None, description="Filter by uploader user ID")
    date_from: Optional[datetime] = Field(None, description="Filter documents uploaded after this timestamp")
    date_to: Optional[datetime] = Field(None, description="Filter documents uploaded before this timestamp")


class SearchResultChunk(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_title: str
    file_type: str
    content: str
    page_number: Optional[int] = None
    section: Optional[str] = None
    token_count: int
    dense_score: Optional[float] = None
    fts_score: Optional[float] = None
    combined_score: float
    rerank_score: Optional[float] = None
    metadata_json: Dict[str, Any] = Field(default_factory=dict)


class SearchResponse(BaseModel):
    query: str
    search_mode: str
    total_candidates: int
    results: List[SearchResultChunk]
    execution_time_ms: float
