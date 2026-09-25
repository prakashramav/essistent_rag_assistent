import uuid
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class EvaluationTestCase(BaseModel):
    question: str = Field(..., min_length=2, max_length=1000)
    ground_truth_answer: Optional[str] = Field(None, description="Expected ground truth answer text")
    ground_truth_doc_titles: Optional[List[str]] = Field(None, description="Expected relevant document titles")
    expected_keywords: Optional[List[str]] = Field(None, description="Keywords expected in relevant passages or answer")


class ClaimVerdict(BaseModel):
    claim: str
    supported: bool
    evidence_snippet: Optional[str] = None
    reasoning: str


class EvaluationItemResult(BaseModel):
    question: str
    generated_answer: str
    ground_truth_answer: Optional[str] = None
    retrieved_chunks_count: int
    precision_at_k: float
    recall_at_k: float
    mrr: float
    hit_rate: float
    faithfulness_score: float
    answer_relevance_score: float
    claims: List[ClaimVerdict] = Field(default_factory=list)
    verdict: Literal["FAITHFUL", "BORDERLINE", "HALLUCINATION_DETECTED"]
    latency_ms: float


class EvaluationRunRequest(BaseModel):
    name: Optional[str] = Field("Benchmark Evaluation Run", max_length=255)
    test_cases: Optional[List[EvaluationTestCase]] = Field(
        None,
        description="List of test cases to benchmark. If omitted, benchmark queries are automatically generated from ingested documents."
    )
    top_k: int = Field(5, ge=1, le=10, description="Top K context chunks")
    hybrid: bool = Field(True, description="Enable hybrid dense + full-text search")
    use_reranking: bool = Field(True, description="Enable reranking model")


class EvaluationRunOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    user_id: Optional[uuid.UUID] = None
    name: str
    status: str
    dataset_size: int
    mean_precision_at_k: float
    mean_recall_at_k: float
    mean_mrr: float
    mean_faithfulness: float
    mean_answer_relevance: float
    created_at: datetime
    results: List[EvaluationItemResult] = Field(default_factory=list)


class SingleEvaluationRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=1000)
    ground_truth_answer: Optional[str] = None
    expected_doc_titles: Optional[List[str]] = None
    top_k: int = Field(5, ge=1, le=10)
    hybrid: bool = Field(True)
    use_reranking: bool = Field(True)


class SingleEvaluationResponse(BaseModel):
    evaluation: EvaluationItemResult
    retrieved_sources: List[Dict[str, Any]] = Field(default_factory=list)
