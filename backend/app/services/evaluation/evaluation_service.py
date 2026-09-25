import logging
import re
import time
import uuid
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chunk import DocumentChunk
from app.models.document import Document
from app.models.evaluation import EvaluationRun
from app.schemas.evaluation import (
    ClaimVerdict,
    EvaluationItemResult,
    EvaluationRunOut,
    EvaluationRunRequest,
    EvaluationTestCase,
    SingleEvaluationRequest,
    SingleEvaluationResponse,
)
from app.schemas.retrieval import SearchQueryRequest
from app.services.evaluation.llm_judge import LLMJudge
from app.services.evaluation.retrieval_metrics import RetrievalMetricsCalculator
from app.services.generation.factory import get_generation_adapter
from app.services.rag.prompt_builder import build_system_prompt
from app.services.retrieval.retrieval_service import RetrievalService

logger = logging.getLogger(__name__)


class EvaluationService:
    @classmethod
    async def evaluate_single_query(
        cls,
        db: AsyncSession,
        org_id: uuid.UUID,
        request: SingleEvaluationRequest,
    ) -> SingleEvaluationResponse:
        start_time = time.perf_counter()

        # 1. Retrieve candidates
        search_req = SearchQueryRequest(
            query=request.question,
            limit=request.top_k,
            hybrid=request.hybrid,
            rerank=request.use_reranking,
        )
        search_res = await RetrievalService.search(db, org_id, search_req)
        retrieved_chunks = search_res.results

        # 2. Generate answer
        system_prompt = build_system_prompt(retrieved_chunks)
        adapter = get_generation_adapter()
        generated_answer = await adapter.generate(
            messages=[{"role": "user", "content": request.question}],
            system_instruction=system_prompt,
        )

        # 3. Calculate Retrieval Metrics
        retrieved_titles = [c.document_title for c in retrieved_chunks]
        relevant_titles = set(request.expected_doc_titles or [])

        # If expected_doc_titles is provided, evaluate precision/recall against it
        # Otherwise, if we have retrieved chunks, compute ground truth based on top score
        if not relevant_titles and retrieved_chunks:
            relevant_titles = {retrieved_chunks[0].document_title}

        prec = RetrievalMetricsCalculator.calculate_precision_at_k(retrieved_titles, relevant_titles, request.top_k)
        rec = RetrievalMetricsCalculator.calculate_recall_at_k(retrieved_titles, relevant_titles, request.top_k)
        mrr = RetrievalMetricsCalculator.calculate_mrr(retrieved_titles, relevant_titles)
        hit = RetrievalMetricsCalculator.calculate_hit_rate(retrieved_titles, relevant_titles, request.top_k)

        # 4. LLM-as-a-judge Faithfulness & Answer Relevance
        judge = LLMJudge()
        judge_res = await judge.evaluate(
            question=request.question,
            retrieved_chunks=retrieved_chunks,
            generated_answer=generated_answer,
            ground_truth_answer=request.ground_truth_answer,
        )

        latency = round((time.perf_counter() - start_time) * 1000, 2)

        claims = [
            ClaimVerdict(
                claim=c["claim"],
                supported=c["supported"],
                evidence_snippet=c.get("evidence_snippet"),
                reasoning=c.get("reasoning", ""),
            )
            for c in judge_res.get("claims", [])
        ]

        item_result = EvaluationItemResult(
            question=request.question,
            generated_answer=generated_answer,
            ground_truth_answer=request.ground_truth_answer,
            retrieved_chunks_count=len(retrieved_chunks),
            precision_at_k=round(prec, 3),
            recall_at_k=round(rec, 3),
            mrr=round(mrr, 3),
            hit_rate=round(hit, 3),
            faithfulness_score=round(judge_res.get("faithfulness_score", 1.0), 3),
            answer_relevance_score=round(judge_res.get("answer_relevance_score", 1.0), 3),
            claims=claims,
            verdict=judge_res.get("verdict", "FAITHFUL"),
            latency_ms=latency,
        )

        sources_out = [
            {
                "chunk_id": str(c.chunk_id),
                "document_title": c.document_title,
                "file_type": c.file_type,
                "page_number": c.page_number,
                "snippet": c.content[:300],
                "score": c.combined_score,
            }
            for c in retrieved_chunks
        ]

        return SingleEvaluationResponse(
            evaluation=item_result,
            retrieved_sources=sources_out,
        )

    @classmethod
    async def run_benchmark(
        cls,
        db: AsyncSession,
        org_id: uuid.UUID,
        user_id: Optional[uuid.UUID],
        request: EvaluationRunRequest,
    ) -> EvaluationRunOut:
        test_cases = request.test_cases

        # If no test cases provided, auto-generate synthetic benchmark questions from ingested documents
        if not test_cases:
            test_cases = await cls._generate_synthetic_test_cases(db, org_id)

        if not test_cases:
            # Fallback test cases if org has no docs yet
            test_cases = [
                EvaluationTestCase(
                    question="What are the enterprise system uptime guarantees?",
                    expected_keywords=["uptime", "sla", "availability"],
                ),
                EvaluationTestCase(
                    question="Explain the company data protection and encryption policy.",
                    expected_keywords=["encryption", "security", "data"],
                ),
            ]

        results: List[EvaluationItemResult] = []

        for tc in test_cases:
            single_req = SingleEvaluationRequest(
                question=tc.question,
                ground_truth_answer=tc.ground_truth_answer,
                expected_doc_titles=tc.ground_truth_doc_titles,
                top_k=request.top_k,
                hybrid=request.hybrid,
                use_reranking=request.use_reranking,
            )
            eval_res = await cls.evaluate_single_query(db, org_id, single_req)
            results.append(eval_res.evaluation)

        # Compute summary averages
        n = len(results) or 1
        mean_prec = round(sum(r.precision_at_k for r in results) / n, 3)
        mean_rec = round(sum(r.recall_at_k for r in results) / n, 3)
        mean_mrr = round(sum(r.mrr for r in results) / n, 3)
        mean_faith = round(sum(r.faithfulness_score for r in results) / n, 3)
        mean_rel = round(sum(r.answer_relevance_score for r in results) / n, 3)

        run_id = uuid.uuid4()
        run_record = EvaluationRun(
            id=run_id,
            organization_id=org_id,
            user_id=user_id,
            name=request.name or "Benchmark Evaluation Run",
            status="completed",
            dataset_size=len(results),
            mean_precision_at_k=mean_prec,
            mean_recall_at_k=mean_rec,
            mean_mrr=mean_mrr,
            mean_faithfulness=mean_faith,
            mean_answer_relevance=mean_rel,
            results_json=[r.model_dump(mode="json") for r in results],
        )

        db.add(run_record)
        await db.commit()
        await db.refresh(run_record)

        return EvaluationRunOut(
            id=run_record.id,
            organization_id=run_record.organization_id,
            user_id=run_record.user_id,
            name=run_record.name,
            status=run_record.status,
            dataset_size=run_record.dataset_size,
            mean_precision_at_k=run_record.mean_precision_at_k,
            mean_recall_at_k=run_record.mean_recall_at_k,
            mean_mrr=run_record.mean_mrr,
            mean_faithfulness=run_record.mean_faithfulness,
            mean_answer_relevance=run_record.mean_answer_relevance,
            created_at=run_record.created_at,
            results=results,
        )

    @classmethod
    async def list_runs(
        cls,
        db: AsyncSession,
        org_id: uuid.UUID,
    ) -> List[EvaluationRunOut]:
        stmt = (
            select(EvaluationRun)
            .where(EvaluationRun.organization_id == org_id)
            .order_by(desc(EvaluationRun.created_at))
            .limit(50)
        )
        res = await db.execute(stmt)
        runs = res.scalars().all()

        return [
            EvaluationRunOut(
                id=r.id,
                organization_id=r.organization_id,
                user_id=r.user_id,
                name=r.name,
                status=r.status,
                dataset_size=r.dataset_size,
                mean_precision_at_k=r.mean_precision_at_k,
                mean_recall_at_k=r.mean_recall_at_k,
                mean_mrr=r.mean_mrr,
                mean_faithfulness=r.mean_faithfulness,
                mean_answer_relevance=r.mean_answer_relevance,
                created_at=r.created_at,
                results=[EvaluationItemResult(**item) for item in r.results_json],
            )
            for r in runs
        ]

    @classmethod
    async def get_run(
        cls,
        db: AsyncSession,
        org_id: uuid.UUID,
        run_id: uuid.UUID,
    ) -> EvaluationRunOut:
        stmt = select(EvaluationRun).where(
            EvaluationRun.id == run_id,
            EvaluationRun.organization_id == org_id,
        )
        res = await db.execute(stmt)
        r = res.scalar_one_or_none()
        if not r:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Evaluation run not found.",
            )

        return EvaluationRunOut(
            id=r.id,
            organization_id=r.organization_id,
            user_id=r.user_id,
            name=r.name,
            status=r.status,
            dataset_size=r.dataset_size,
            mean_precision_at_k=r.mean_precision_at_k,
            mean_recall_at_k=r.mean_recall_at_k,
            mean_mrr=r.mean_mrr,
            mean_faithfulness=r.mean_faithfulness,
            mean_answer_relevance=r.mean_answer_relevance,
            created_at=r.created_at,
            results=[EvaluationItemResult(**item) for item in r.results_json],
        )

    @classmethod
    async def _generate_synthetic_test_cases(
        cls,
        db: AsyncSession,
        org_id: uuid.UUID,
        limit: int = 5,
    ) -> List[EvaluationTestCase]:
        """Auto-generates synthetic test queries from the organization's existing chunks."""
        stmt = (
            select(DocumentChunk, Document.title)
            .join(Document, DocumentChunk.document_id == Document.id)
            .where(
                DocumentChunk.organization_id == org_id,
                Document.organization_id == org_id,
            )
            .limit(limit)
        )
        res = await db.execute(stmt)
        rows = res.all()

        cases: List[EvaluationTestCase] = []
        for chk, doc_title in rows:
            # Extract first sentence or section to formulate query
            sentences = [s.strip() for s in re.split(r"[.!?]\s+", chk.content) if len(s.strip()) > 15]
            if sentences:
                clean_sentence = sentences[0].replace("#", "").strip()
                words = clean_sentence.split()[:8]
                query = f"What does {doc_title} state regarding {' '.join(words)}?"
                cases.append(
                    EvaluationTestCase(
                        question=query,
                        ground_truth_doc_titles=[doc_title],
                        ground_truth_answer=clean_sentence,
                    )
                )

        return cases
