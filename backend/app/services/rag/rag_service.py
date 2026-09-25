import json
import logging
import uuid
from typing import AsyncGenerator, List, Optional
from fastapi import HTTPException, status
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.citation import Citation
from app.models.conversation import Conversation
from app.models.document import Document
from app.models.enums import SenderType
from app.models.message import Message
from app.schemas.chat import (
    CitationOut,
    ConversationDetailOut,
    ConversationOut,
    MessageOut,
    SendMessageRequest,
)
from app.schemas.common import PaginatedResponse
from app.schemas.retrieval import SearchQueryRequest
from app.services.generation.factory import get_generation_adapter
from app.services.rag.citation_service import CitationService
from app.services.rag.prompt_builder import (
    build_conversation_history,
    build_system_prompt,
)
from app.services.retrieval.retrieval_service import RetrievalService

logger = logging.getLogger(__name__)


class RAGService:
    @classmethod
    async def create_conversation(
        cls,
        db: AsyncSession,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        title: Optional[str] = "New Conversation",
    ) -> ConversationOut:
        conv = Conversation(
            id=uuid.uuid4(),
            organization_id=org_id,
            user_id=user_id,
            title=(title or "New Conversation")[:255],
        )
        db.add(conv)
        await db.commit()
        await db.refresh(conv)

        return ConversationOut(
            id=conv.id,
            organization_id=conv.organization_id,
            user_id=conv.user_id,
            title=conv.title,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
            message_count=0,
        )

    @classmethod
    async def list_conversations(
        cls,
        db: AsyncSession,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedResponse[ConversationOut]:
        offset = (page - 1) * page_size

        total_stmt = (
            select(func.count(Conversation.id))
            .where(
                Conversation.organization_id == org_id,
                Conversation.user_id == user_id,
            )
        )
        total_res = await db.execute(total_stmt)
        total = total_res.scalar() or 0

        # Subquery to count messages per conversation
        msg_count_sub = (
            select(
                Message.conversation_id,
                func.count(Message.id).label("cnt"),
            )
            .where(Message.organization_id == org_id)
            .group_by(Message.conversation_id)
            .subquery()
        )

        stmt = (
            select(
                Conversation,
                func.coalesce(msg_count_sub.c.cnt, 0).label("msg_count"),
            )
            .outerjoin(msg_count_sub, Conversation.id == msg_count_sub.c.conversation_id)
            .where(
                Conversation.organization_id == org_id,
                Conversation.user_id == user_id,
            )
            .order_by(desc(Conversation.updated_at))
            .offset(offset)
            .limit(page_size)
        )

        res = await db.execute(stmt)
        items = []
        for conv, count in res.all():
            items.append(
                ConversationOut(
                    id=conv.id,
                    organization_id=conv.organization_id,
                    user_id=conv.user_id,
                    title=conv.title,
                    created_at=conv.created_at,
                    updated_at=conv.updated_at,
                    message_count=count,
                )
            )

        total_pages = (total + page_size - 1) // page_size if total > 0 else 1

        return PaginatedResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    @classmethod
    async def get_conversation(
        cls,
        db: AsyncSession,
        org_id: uuid.UUID,
        conversation_id: uuid.UUID,
    ) -> ConversationDetailOut:
        stmt = (
            select(Conversation)
            .options(
                selectinload(Conversation.messages)
                .selectinload(Message.citations)
                .selectinload(Citation.document)
            )
            .where(
                Conversation.id == conversation_id,
                Conversation.organization_id == org_id,
            )
        )
        res = await db.execute(stmt)
        conv = res.scalar_one_or_none()

        if not conv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found or access denied.",
            )

        messages_out: List[MessageOut] = []
        for msg in sorted(conv.messages, key=lambda m: m.created_at):
            citations_out: List[CitationOut] = []
            for cite in msg.citations:
                doc_title = cite.document.title if cite.document else "Unknown Document"
                doc_type = cite.document.file_type if cite.document else None
                citations_out.append(
                    CitationOut(
                        id=cite.id,
                        message_id=cite.message_id,
                        chunk_id=cite.chunk_id,
                        document_id=cite.document_id,
                        document_title=doc_title,
                        file_type=doc_type,
                        snippet=cite.snippet,
                        page_number=cite.page_number,
                    )
                )

            messages_out.append(
                MessageOut(
                    id=msg.id,
                    conversation_id=msg.conversation_id,
                    organization_id=msg.organization_id,
                    sender_type=msg.sender_type,
                    content=msg.content,
                    metadata_json=msg.metadata_json or {},
                    created_at=msg.created_at,
                    citations=citations_out,
                )
            )

        return ConversationDetailOut(
            id=conv.id,
            organization_id=conv.organization_id,
            user_id=conv.user_id,
            title=conv.title,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
            messages=messages_out,
        )

    @classmethod
    async def delete_conversation(
        cls,
        db: AsyncSession,
        org_id: uuid.UUID,
        conversation_id: uuid.UUID,
    ) -> bool:
        stmt = select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.organization_id == org_id,
        )
        res = await db.execute(stmt)
        conv = res.scalar_one_or_none()

        if not conv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found or access denied.",
            )

        await db.delete(conv)
        await db.commit()
        return True

    @classmethod
    async def update_conversation_title(
        cls,
        db: AsyncSession,
        org_id: uuid.UUID,
        conversation_id: uuid.UUID,
        title: str,
    ) -> ConversationOut:
        stmt = select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.organization_id == org_id,
        )
        res = await db.execute(stmt)
        conv = res.scalar_one_or_none()

        if not conv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found or access denied.",
            )

        conv.title = title.strip()[:255]
        await db.commit()
        await db.refresh(conv)

        return ConversationOut(
            id=conv.id,
            organization_id=conv.organization_id,
            user_id=conv.user_id,
            title=conv.title,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
            message_count=0,
        )

    @classmethod
    async def send_message(
        cls,
        db: AsyncSession,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
        request: SendMessageRequest,
    ) -> MessageOut:
        # Validate conversation ownership & tenant isolation
        conv_stmt = (
            select(Conversation)
            .options(selectinload(Conversation.messages))
            .where(
                Conversation.id == conversation_id,
                Conversation.organization_id == org_id,
            )
        )
        conv_res = await db.execute(conv_stmt)
        conv = conv_res.scalar_one_or_none()
        if not conv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found or access denied.",
            )

        # 1. Save User Message
        user_msg = Message(
            id=uuid.uuid4(),
            conversation_id=conversation_id,
            organization_id=org_id,
            sender_type=SenderType.USER,
            content=request.content.strip(),
            metadata_json={},
        )
        db.add(user_msg)

        # Auto-update conversation title if it's the first message
        if conv.title == "New Conversation" and not conv.messages:
            words = request.content.strip().split()
            conv.title = " ".join(words[:6])[:60]

        await db.flush()

        # 2. Retrieve relevant context passages
        search_req = SearchQueryRequest(
            query=request.content.strip(),
            limit=request.top_k,
            hybrid=request.hybrid,
            alpha=request.alpha,
            rerank=request.use_reranking,
            document_ids=request.filter_document_ids,
            tags=request.filter_tags,
        )
        search_res = await RetrievalService.search(db, org_id, search_req)
        retrieved_chunks = search_res.results

        # 3. Construct prompt with context & history window
        system_prompt = build_system_prompt(retrieved_chunks)
        history_msgs = build_conversation_history(conv.messages)
        history_msgs.append({"role": "user", "content": request.content.strip()})

        # 4. Generate Answer via configured Adapter
        adapter = get_generation_adapter()
        generated_content = await adapter.generate(
            messages=history_msgs,
            system_instruction=system_prompt,
        )

        # 5. Save Assistant Message
        assistant_msg_id = uuid.uuid4()
        assistant_msg = Message(
            id=assistant_msg_id,
            conversation_id=conversation_id,
            organization_id=org_id,
            sender_type=SenderType.ASSISTANT,
            content=generated_content,
            metadata_json={
                "retrieved_chunk_count": len(retrieved_chunks),
                "hybrid": request.hybrid,
            },
        )
        db.add(assistant_msg)
        await db.flush()

        # 6. Extract & Persist Citations
        citations = await CitationService.create_citations_for_message(
            db=db,
            message_id=assistant_msg_id,
            organization_id=org_id,
            generated_text=generated_content,
            retrieved_chunks=retrieved_chunks,
        )

        conv.updated_at = func.now()
        await db.commit()

        return MessageOut(
            id=assistant_msg.id,
            conversation_id=conversation_id,
            organization_id=org_id,
            sender_type=assistant_msg.sender_type,
            content=assistant_msg.content,
            metadata_json=assistant_msg.metadata_json,
            created_at=assistant_msg.created_at,
            citations=citations,
        )

    @classmethod
    async def stream_message(
        cls,
        db: AsyncSession,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
        request: SendMessageRequest,
    ) -> AsyncGenerator[str, None]:
        """
        Yields Server-Sent Events (SSE) lines in `data: {...}\n\n` format.
        """
        try:
            # Validate conversation ownership & tenant isolation
            conv_stmt = (
                select(Conversation)
                .options(selectinload(Conversation.messages))
                .where(
                    Conversation.id == conversation_id,
                    Conversation.organization_id == org_id,
                )
            )
            conv_res = await db.execute(conv_stmt)
            conv = conv_res.scalar_one_or_none()
            if not conv:
                err_event = json.dumps({"type": "error", "data": {"detail": "Conversation not found or access denied."}})
                yield f"data: {err_event}\n\n"
                return

            # Save User Message
            user_msg = Message(
                id=uuid.uuid4(),
                conversation_id=conversation_id,
                organization_id=org_id,
                sender_type=SenderType.USER,
                content=request.content.strip(),
                metadata_json={},
            )
            db.add(user_msg)

            if conv.title == "New Conversation" and not conv.messages:
                words = request.content.strip().split()
                conv.title = " ".join(words[:6])[:60]

            await db.flush()

            # SSE Event: Status - Retrieving documents
            status_event = json.dumps({
                "type": "retrieval_status",
                "data": {"status": "Searching internal knowledge base...", "query": request.content.strip()},
            })
            yield f"data: {status_event}\n\n"

            # Execute Hybrid Retrieval
            search_req = SearchQueryRequest(
                query=request.content.strip(),
                limit=request.top_k,
                hybrid=request.hybrid,
                alpha=request.alpha,
                rerank=request.use_reranking,
                document_ids=request.filter_document_ids,
                tags=request.filter_tags,
            )
            search_res = await RetrievalService.search(db, org_id, search_req)
            retrieved_chunks = search_res.results

            # SSE Event: Sources discovered
            sources_data = [
                {
                    "chunk_id": str(c.chunk_id),
                    "document_id": str(c.document_id),
                    "document_title": c.document_title,
                    "file_type": c.file_type,
                    "snippet": c.content[:300].strip(),
                    "page_number": c.page_number,
                    "score": c.combined_score,
                }
                for c in retrieved_chunks
            ]
            sources_event = json.dumps({"type": "sources", "data": sources_data})
            yield f"data: {sources_event}\n\n"

            # Build grounded prompt & sliding history
            system_prompt = build_system_prompt(retrieved_chunks)
            history_msgs = build_conversation_history(conv.messages)
            history_msgs.append({"role": "user", "content": request.content.strip()})

            # Stream generation tokens
            adapter = get_generation_adapter()
            accumulated_tokens = []

            async for token in adapter.generate_stream(
                messages=history_msgs,
                system_instruction=system_prompt,
            ):
                accumulated_tokens.append(token)
                delta_event = json.dumps({"type": "delta", "data": {"content": token}})
                yield f"data: {delta_event}\n\n"

            full_text = "".join(accumulated_tokens)

            # Persist Assistant Message and Citations
            assistant_msg_id = uuid.uuid4()
            assistant_msg = Message(
                id=assistant_msg_id,
                conversation_id=conversation_id,
                organization_id=org_id,
                sender_type=SenderType.ASSISTANT,
                content=full_text,
                metadata_json={
                    "retrieved_chunk_count": len(retrieved_chunks),
                    "hybrid": request.hybrid,
                },
            )
            db.add(assistant_msg)
            await db.flush()

            citations = await CitationService.create_citations_for_message(
                db=db,
                message_id=assistant_msg_id,
                organization_id=org_id,
                generated_text=full_text,
                retrieved_chunks=retrieved_chunks,
            )

            conv.updated_at = func.now()
            await db.commit()

            # SSE Event: Done with final payload
            done_payload = {
                "type": "done",
                "data": {
                    "message_id": str(assistant_msg_id),
                    "content": full_text,
                    "citations": [c.model_dump(mode="json") for c in citations],
                },
            }
            yield f"data: {json.dumps(done_payload)}\n\n"

        except Exception as e:
            logger.error(f"Error during RAG message streaming: {e}", exc_info=True)
            err_event = json.dumps({"type": "error", "data": {"detail": str(e)}})
            yield f"data: {err_event}\n\n"
