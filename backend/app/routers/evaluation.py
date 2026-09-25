import uuid
from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.routers.dependencies import AuthContext, RequireViewer
from app.schemas.evaluation import (
    EvaluationRunOut,
    EvaluationRunRequest,
    SingleEvaluationRequest,
    SingleEvaluationResponse,
)
from app.services.evaluation.evaluation_service import EvaluationService

router = APIRouter(prefix="/evaluation", tags=["Evaluation & Benchmarking"])


@router.post("/single", response_model=SingleEvaluationResponse)
async def evaluate_single_query(
    request: SingleEvaluationRequest,
    context: AuthContext = Depends(RequireViewer),
    db: AsyncSession = Depends(get_db),
):
    """
    On-demand single query evaluation:
    Calculates Precision@K, Recall@K, MRR, LLM-as-a-judge Faithfulness, and Answer Relevance.
    """
    return await EvaluationService.evaluate_single_query(
        db=db,
        org_id=context.organization_id,
        request=request,
    )


@router.post("/run", response_model=EvaluationRunOut, status_code=status.HTTP_201_CREATED)
async def run_benchmark(
    request: EvaluationRunRequest = EvaluationRunRequest(),
    context: AuthContext = Depends(RequireViewer),
    db: AsyncSession = Depends(get_db),
):
    """
    Execute a full benchmark evaluation suite against tenant ingested documents.
    If no test cases are specified, synthetic benchmark queries are automatically generated.
    """
    return await EvaluationService.run_benchmark(
        db=db,
        org_id=context.organization_id,
        user_id=context.user.id,
        request=request,
    )


@router.get("/runs", response_model=List[EvaluationRunOut])
async def list_evaluation_runs(
    context: AuthContext = Depends(RequireViewer),
    db: AsyncSession = Depends(get_db),
):
    """List historical evaluation runs for the active organization."""
    return await EvaluationService.list_runs(
        db=db,
        org_id=context.organization_id,
    )


@router.get("/runs/{run_id}", response_model=EvaluationRunOut)
async def get_evaluation_run(
    run_id: uuid.UUID,
    context: AuthContext = Depends(RequireViewer),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve detailed query-level breakdown and claims verification for an evaluation run."""
    return await EvaluationService.get_run(
        db=db,
        org_id=context.organization_id,
        run_id=run_id,
    )
