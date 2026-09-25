import os
import shutil
import uuid
from typing import List, Optional
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy import delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.chunk import DocumentChunk
from app.models.document import Document
from app.models.enums import IngestionStatus
from app.routers.dependencies import AuthContext, RequireMember, RequireViewer
from app.schemas.common import MessageResponse
from app.schemas.document import (
    ChunkOut,
    DocumentOut,
    DocumentStatusResponse,
    DocumentUploadResponse,
    UrlIngestRequest,
)
from app.services.ingestion.pipeline import IngestionPipeline

router = APIRouter(prefix="/documents", tags=["Documents"])

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".md", ".json", ".csv"}
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    tags: Optional[str] = Form(None),
    context: AuthContext = Depends(RequireMember),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a document (PDF, DOCX, TXT) and dispatch async ingestion in the background.
    Strictly isolated to the authenticated user's organization.
    """
    filename = file.filename or "uploaded_file"
    ext = os.path.splitext(filename)[1].lower()

    if ext not in ALLOWED_EXTENSIONS:
        allowed_str = ", ".join(ALLOWED_EXTENSIONS)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{ext}'. Allowed types: {allowed_str}",
        )

    # Read bytes and validate size limit
    file_bytes = await file.read()
    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    if len(file_bytes) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum allowed size of {settings.MAX_FILE_SIZE_MB}MB",
        )

    # Save to local uploads folder
    org_folder = os.path.join(UPLOAD_DIR, str(context.organization_id))
    os.makedirs(org_folder, exist_ok=True)
    stored_filename = f"{uuid.uuid4()}_{filename}"
    file_path = os.path.join(org_folder, stored_filename)
    with open(file_path, "wb") as f:
        f.write(file_bytes)

    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

    # Create Document record
    doc = Document(
        organization_id=context.organization_id,
        uploader_id=context.user.id,
        title=filename,
        file_type=ext.lstrip("."),
        file_path=file_path,
        status=IngestionStatus.PENDING,
        metadata_json={
            "original_filename": filename,
            "size_bytes": len(file_bytes),
            "tags": tag_list,
            "uploader_email": context.user.email,
        },
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    # Queue background task for parse -> chunk -> embed -> pgvector storage
    background_tasks.add_task(
        IngestionPipeline.process_document_task,
        doc.id,
        context.organization_id,
        file_bytes,
    )

    return doc


@router.post("/url", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def ingest_url(
    data: UrlIngestRequest,
    background_tasks: BackgroundTasks,
    context: AuthContext = Depends(RequireMember),
    db: AsyncSession = Depends(get_db),
):
    """
    Ingest a website URL as an organization document and trigger async web scraping.
    """
    doc_title = data.title or str(data.url)
    doc = Document(
        organization_id=context.organization_id,
        uploader_id=context.user.id,
        title=doc_title,
        file_type="url",
        source_url=str(data.url),
        status=IngestionStatus.PENDING,
        metadata_json={
            "source_url": str(data.url),
            "tags": data.tags,
            "uploader_email": context.user.email,
        },
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    background_tasks.add_task(
        IngestionPipeline.process_document_task,
        doc.id,
        context.organization_id,
    )

    return doc


@router.get("", response_model=List[DocumentOut])
async def list_documents(
    status_filter: Optional[IngestionStatus] = Query(None, alias="status"),
    file_type: Optional[str] = Query(None),
    context: AuthContext = Depends(RequireViewer),
    db: AsyncSession = Depends(get_db),
):
    """List all documents for the current organization, optionally filtered."""
    query = (
        select(Document)
        .where(Document.organization_id == context.organization_id)
        .order_by(desc(Document.created_at))
    )
    if status_filter:
        query = query.where(Document.status == status_filter)
    if file_type:
        query = query.where(Document.file_type == file_type)

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document(
    document_id: uuid.UUID,
    context: AuthContext = Depends(RequireViewer),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve details of a single document. Enforces organization tenant boundary."""
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.organization_id == context.organization_id,
        )
    )
    doc = result.scalars().first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found in your organization",
        )
    return doc


@router.get("/{document_id}/status", response_model=DocumentStatusResponse)
async def get_document_status(
    document_id: uuid.UUID,
    context: AuthContext = Depends(RequireViewer),
    db: AsyncSession = Depends(get_db),
):
    """Fast polling endpoint for ingestion progress."""
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.organization_id == context.organization_id,
        )
    )
    doc = result.scalars().first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found in your organization",
        )
    return doc


@router.get("/{document_id}/chunks", response_model=List[ChunkOut])
async def get_document_chunks(
    document_id: uuid.UUID,
    context: AuthContext = Depends(RequireViewer),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve all ingested chunks for a document, ordered by index."""
    # Ensure document belongs to this organization
    doc_res = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.organization_id == context.organization_id,
        )
    )
    if not doc_res.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found in your organization",
        )

    chunks_res = await db.execute(
        select(DocumentChunk)
        .where(
            DocumentChunk.document_id == document_id,
            DocumentChunk.organization_id == context.organization_id,
        )
        .order_by(DocumentChunk.chunk_index)
    )
    return chunks_res.scalars().all()


@router.post("/{document_id}/reindex", response_model=DocumentUploadResponse)
async def reindex_document(
    document_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    context: AuthContext = Depends(RequireMember),
    db: AsyncSession = Depends(get_db),
):
    """Re-trigger the ingestion and chunking pipeline for an existing document."""
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.organization_id == context.organization_id,
        )
    )
    doc = result.scalars().first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found in your organization",
        )

    doc.status = IngestionStatus.PENDING
    doc.error_message = None
    await db.commit()

    background_tasks.add_task(
        IngestionPipeline.process_document_task,
        doc.id,
        context.organization_id,
    )

    return doc


@router.delete("/{document_id}", response_model=MessageResponse)
async def delete_document(
    document_id: uuid.UUID,
    context: AuthContext = Depends(RequireMember),
    db: AsyncSession = Depends(get_db),
):
    """Delete a document and all associated chunks within this organization."""
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.organization_id == context.organization_id,
        )
    )
    doc = result.scalars().first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found in your organization",
        )

    # Delete physical file if present
    if doc.file_path and os.path.exists(doc.file_path):
        try:
            os.remove(doc.file_path)
        except Exception:
            pass

    await db.delete(doc)
    await db.commit()

    return MessageResponse(message=f"Document '{doc.title}' deleted successfully")
