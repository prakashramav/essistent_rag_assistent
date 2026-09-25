import uuid
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field
from app.models.enums import SenderType


class CreateConversationRequest(BaseModel):
    title: Optional[str] = Field("New Conversation", max_length=255, description="Optional title for the conversation")


class UpdateConversationRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255, description="Updated conversation title")


class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=4000, description="User query or message content")
    top_k: int = Field(5, ge=1, le=20, description="Number of context chunks to retrieve for generation")
    hybrid: bool = Field(True, description="Enable hybrid dense + full-text search")
    alpha: float = Field(0.7, ge=0.0, le=1.0, description="Dense vector weight (1.0 = pure vector)")
    use_reranking: bool = Field(True, description="Apply reranker model on top retrieved chunks")
    
    # Metadata filters
    filter_document_ids: Optional[List[uuid.UUID]] = Field(None, description="Scope query to specific documents")
    filter_tags: Optional[List[str]] = Field(None, description="Scope query to documents with specific tags")


class CitationOut(BaseModel):
    id: uuid.UUID
    message_id: uuid.UUID
    chunk_id: Optional[uuid.UUID] = None
    document_id: uuid.UUID
    document_title: str
    file_type: Optional[str] = None
    snippet: str
    page_number: Optional[int] = None
    score: Optional[float] = None


class MessageOut(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    organization_id: uuid.UUID
    sender_type: SenderType
    content: str
    metadata_json: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    citations: List[CitationOut] = Field(default_factory=list)


class ConversationOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    user_id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0


class ConversationDetailOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    user_id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime
    messages: List[MessageOut] = Field(default_factory=list)


class StreamEvent(BaseModel):
    type: Literal["retrieval_status", "sources", "delta", "done", "error"]
    data: Any
