import logging
import time
import uuid
from typing import Dict, List, Optional
from sqlalchemy import desc, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chunk import DocumentChunk
from app.models.document import Document
from app.schemas.retrieval import SearchQueryRequest, SearchResponse, SearchResultChunk
from app.services.embeddings.factory import get_embedding_adapter
from app.services.reranking.base import CandidateChunk
from app.services.reranking.factory import get_reranker

logger = logging.getLogger(__name__)


class RetrievalService:
    @classmethod
    async def search(
        cls,
        db: AsyncSession,
        org_id: uuid.UUID,
        request: SearchQueryRequest,
    ) -> SearchResponse:
        start_time = time.perf_counter()
        embedding_adapter = get_embedding_adapter()

        # Step 1: Execute Dense Vector Search if enabled
        dense_candidates: Dict[uuid.UUID, CandidateChunk] = {}
        dense_ranks: Dict[uuid.UUID, int] = {}

        query_vector = await embedding_adapter.embed_query(request.query)

        try:
            dense_stmt = (
                select(
                    DocumentChunk,
                    Document.title.label("document_title"),
                    Document.file_type.label("file_type"),
                    (1 - DocumentChunk.embedding.cosine_distance(query_vector)).label("dense_score"),
                )
                .join(Document, DocumentChunk.document_id == Document.id)
                .where(
                    DocumentChunk.organization_id == org_id,
                    Document.organization_id == org_id,
                    DocumentChunk.embedding.isnot(None),
                )
            )
            dense_stmt = cls._apply_metadata_filters(dense_stmt, request)
            dense_stmt = dense_stmt.order_by(
                DocumentChunk.embedding.cosine_distance(query_vector)
            ).limit(request.candidate_k)

            dense_res = await db.execute(dense_stmt)
            for rank, row in enumerate(dense_res.all()):
                chk: DocumentChunk = row[0]
                doc_title: str = row[1]
                file_type: str = row[2]
                score: float = float(row[3]) if row[3] is not None else 0.0

                cand = CandidateChunk(
                    chunk_id=chk.id,
                    document_id=chk.document_id,
                    document_title=doc_title,
                    file_type=file_type,
                    content=chk.content,
                    page_number=chk.page_number,
                    section=chk.section,
                    token_count=chk.token_count,
                    dense_score=round(score, 4),
                    metadata_json=chk.metadata_json,
                )
                dense_candidates[chk.id] = cand
                dense_ranks[chk.id] = rank

        except Exception as e:
            logger.warning(f"Dense vector search failed: {e}. Falling back to sparse search.")

        # Step 2: Execute Sparse Full-Text Search (tsvector / ts_rank) if hybrid
        fts_candidates: Dict[uuid.UUID, CandidateChunk] = {}
        fts_ranks: Dict[uuid.UUID, int] = {}

        if request.hybrid:
            try:
                ts_query = func.plainto_tsquery("english", request.query)
                ts_vector = func.to_tsvector("english", DocumentChunk.content)
                rank_col = func.ts_rank(ts_vector, ts_query).label("fts_score")

                fts_stmt = (
                    select(
                        DocumentChunk,
                        Document.title.label("document_title"),
                        Document.file_type.label("file_type"),
                        rank_col,
                    )
                    .join(Document, DocumentChunk.document_id == Document.id)
                    .where(
                        DocumentChunk.organization_id == org_id,
                        Document.organization_id == org_id,
                        ts_vector.op("@@")(ts_query),
                    )
                )
                fts_stmt = cls._apply_metadata_filters(fts_stmt, request)
                fts_stmt = fts_stmt.order_by(desc(rank_col)).limit(request.candidate_k)

                fts_res = await db.execute(fts_stmt)
                for rank, row in enumerate(fts_res.all()):
                    chk: DocumentChunk = row[0]
                    doc_title: str = row[1]
                    file_type: str = row[2]
                    score: float = float(row[3]) if row[3] is not None else 0.0

                    cand = CandidateChunk(
                        chunk_id=chk.id,
                        document_id=chk.document_id,
                        document_title=doc_title,
                        file_type=file_type,
                        content=chk.content,
                        page_number=chk.page_number,
                        section=chk.section,
                        token_count=chk.token_count,
                        fts_score=round(score, 4),
                        metadata_json=chk.metadata_json,
                    )
                    fts_candidates[chk.id] = cand
                    fts_ranks[chk.id] = rank

            except Exception as e:
                logger.warning(f"Postgres full-text search failed: {e}")

        # Step 3: Reciprocal Rank Fusion (RRF) & Score Blending
        all_candidate_ids = set(dense_candidates.keys()).union(set(fts_candidates.keys()))
        merged_candidates: List[CandidateChunk] = []
        k_rrf = 60.0

        for cid in all_candidate_ids:
            base_chunk = dense_candidates.get(cid) or fts_candidates.get(cid)
            dense_rank = dense_ranks.get(cid)
            fts_rank = fts_ranks.get(cid)

            # RRF score
            rrf_score = 0.0
            if dense_rank is not None:
                rrf_score += request.alpha * (1.0 / (k_rrf + dense_rank))
            if fts_rank is not None:
                rrf_score += (1.0 - request.alpha) * (1.0 / (k_rrf + fts_rank))

            # Normalize RRF score to 0..1 scale
            base_chunk.combined_score = round(rrf_score * 100, 4)
            if cid in dense_candidates:
                base_chunk.dense_score = dense_candidates[cid].dense_score
            if cid in fts_candidates:
                base_chunk.fts_score = fts_candidates[cid].fts_score

            merged_candidates.append(base_chunk)

        merged_candidates.sort(key=lambda c: c.combined_score, reverse=True)

        # Step 4: Reranking on top candidates
        final_candidates: List[CandidateChunk] = []
        if request.rerank and merged_candidates:
            reranker = get_reranker()
            top_candidates = merged_candidates[: request.candidate_k]
            final_candidates = await reranker.rerank(request.query, top_candidates, top_k=request.limit)
        else:
            final_candidates = merged_candidates[: request.limit]

        exec_time = round((time.perf_counter() - start_time) * 1000, 2)

        results = [
            SearchResultChunk(
                chunk_id=c.chunk_id,
                document_id=c.document_id,
                document_title=c.document_title,
                file_type=c.file_type,
                content=c.content,
                page_number=c.page_number,
                section=c.section,
                token_count=c.token_count,
                dense_score=c.dense_score,
                fts_score=c.fts_score,
                combined_score=c.combined_score,
                rerank_score=c.rerank_score,
                metadata_json=c.metadata_json,
            )
            for c in final_candidates
        ]

        mode = "hybrid" if request.hybrid else "vector_only"
        return SearchResponse(
            query=request.query,
            search_mode=mode,
            total_candidates=len(all_candidate_ids),
            results=results,
            execution_time_ms=exec_time,
        )

    @classmethod
    def _apply_metadata_filters(cls, stmt, request: SearchQueryRequest):
        """Applies document IDs, tags, uploader, and date range filters at the database query level."""
        if request.document_ids:
            stmt = stmt.where(Document.id.in_(request.document_ids))
        if request.uploader_id:
            stmt = stmt.where(Document.uploader_id == request.uploader_id)
        if request.date_from:
            stmt = stmt.where(Document.created_at >= request.date_from)
        if request.date_to:
            stmt = stmt.where(Document.created_at <= request.date_to)
        if request.tags:
            # PostgreSQL JSONB array containment
            for tag in request.tags:
                stmt = stmt.where(
                    Document.metadata_json["tags"].astext.contains(tag)
                )
        return stmt
