import logging
import os
import uuid
from typing import List, Optional
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.chunk import DocumentChunk
from app.models.document import Document
from app.models.enums import IngestionStatus
from app.services.chunking.recursive_chunker import RecursiveTokenChunker
from app.services.embeddings.factory import get_embedding_adapter
from app.services.parsers.base import ParsedContent
from app.services.parsers.factory import get_parser_for_filename
from app.services.parsers.web_parser import WebParser

logger = logging.getLogger(__name__)


class IngestionPipeline:
    @classmethod
    async def process_document_task(
        cls,
        document_id: uuid.UUID,
        organization_id: uuid.UUID,
        file_bytes: Optional[bytes] = None,
        db: Optional[AsyncSession] = None,
    ) -> None:
        """
        Background task worker executing the end-to-end ingestion pipeline:
        Parse -> Chunk -> Embed -> Store pgvector chunks -> Update Document status.
        """
        if db is not None:
            await cls._run_pipeline(db, document_id, organization_id, file_bytes)
        else:
            async with AsyncSessionLocal() as session:
                await cls._run_pipeline(session, document_id, organization_id, file_bytes)

    @classmethod
    async def _run_pipeline(
        cls,
        db: AsyncSession,
        document_id: uuid.UUID,
        organization_id: uuid.UUID,
        file_bytes: Optional[bytes] = None,
    ) -> None:
        try:
            # 1. Fetch document and mark PROCESSING
            result = await db.execute(
                select(Document).where(
                    Document.id == document_id,
                    Document.organization_id == organization_id,
                )
            )
            doc = result.scalars().first()
            if not doc:
                logger.error(f"Document {document_id} not found for org {organization_id}")
                return

            doc.status = IngestionStatus.PROCESSING
            doc.error_message = None
            await db.commit()

            # 2. Parse file content or web URL
            parsed_contents: List[ParsedContent] = []

            if doc.file_type == "url" and doc.source_url:
                page_title, parsed_contents = await WebParser.fetch_and_parse(doc.source_url)
                if not doc.title or doc.title == doc.source_url:
                    doc.title = page_title
            else:
                raw_bytes = file_bytes
                if raw_bytes is None and doc.file_path and os.path.exists(doc.file_path):
                    with open(doc.file_path, "rb") as f:
                        raw_bytes = f.read()

                if not raw_bytes:
                    raise ValueError(f"No file bytes available for document {doc.title}")

                parser = get_parser_for_filename(doc.title)
                if not parser:
                    raise ValueError(f"Unsupported file type for {doc.title}")

                parsed_contents = parser.parse(raw_bytes, filename=doc.title)

            if not parsed_contents:
                raise ValueError("No extractable text found in document.")

            # 3. Recursive chunking
            chunker = RecursiveTokenChunker(
                chunk_size=settings.CHUNK_SIZE,
                chunk_overlap=settings.CHUNK_OVERLAP,
            )
            chunk_items = chunker.chunk_document(parsed_contents)

            if not chunk_items:
                raise ValueError("Document yielded 0 chunks after splitting.")

            # 4. Generate Embeddings (batch call to Gemini / Adapter)
            embedding_adapter = get_embedding_adapter()
            texts_to_embed = [c.content for c in chunk_items]
            embeddings = await embedding_adapter.embed_texts(texts_to_embed)

            # 5. Clear previous chunks if re-indexing
            await db.execute(
                delete(DocumentChunk).where(
                    DocumentChunk.document_id == document_id,
                    DocumentChunk.organization_id == organization_id,
                )
            )

            # 6. Bulk persist pgvector chunks
            chunk_records = []
            for idx, chunk_item in enumerate(chunk_items):
                vec = embeddings[idx] if idx < len(embeddings) else None
                chunk_rec = DocumentChunk(
                    document_id=document_id,
                    organization_id=organization_id,
                    chunk_index=chunk_item.chunk_index,
                    content=chunk_item.content,
                    embedding=vec,
                    page_number=chunk_item.page_number,
                    section=chunk_item.section,
                    token_count=chunk_item.token_count,
                    metadata_json=chunk_item.metadata_json,
                )
                chunk_records.append(chunk_rec)

            db.add_all(chunk_records)

            # 7. Finalize document status
            doc.status = IngestionStatus.COMPLETED
            doc.total_chunks = len(chunk_records)
            await db.commit()
            logger.info(f"Successfully ingested document '{doc.title}' with {len(chunk_records)} chunks.")

        except Exception as e:
            logger.exception(f"Failed to ingest document {document_id}: {e}")
            await db.rollback()
            fail_result = await db.execute(
                select(Document).where(
                    Document.id == document_id,
                    Document.organization_id == organization_id,
                )
            )
            fail_doc = fail_result.scalars().first()
            if fail_doc:
                fail_doc.status = IngestionStatus.FAILED
                fail_doc.error_message = str(e)
                await db.commit()
