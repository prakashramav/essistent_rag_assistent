import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, HttpUrl, Field
from app.models.enums import IngestionStatus


class DocumentUploadResponse(BaseModel):
    id: uuid.UUID
    title: str
    file_type: str
    status: IngestionStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class UrlIngestRequest(BaseModel):
    url: HttpUrl
    title: Optional[str] = Field(None, max_length=255)
    tags: List[str] = Field(default_factory=list)


class DocumentOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    uploader_id: Optional[uuid.UUID] = None
    title: str
    file_type: str
    source_url: Optional[str] = None
    status: IngestionStatus
    error_message: Optional[str] = None
    total_chunks: int
    metadata_json: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentStatusResponse(BaseModel):
    id: uuid.UUID
    status: IngestionStatus
    total_chunks: int
    error_message: Optional[str] = None
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChunkOut(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    organization_id: uuid.UUID
    chunk_index: int
    content: str
    page_number: Optional[int] = None
    section: Optional[str] = None
    token_count: int
    metadata_json: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = {"from_attributes": True}
