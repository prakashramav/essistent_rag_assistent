import uuid
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from app.core.database import Base


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    name = Column(String(255), default="Benchmark Evaluation Run", nullable=False)
    status = Column(String(50), default="completed", nullable=False)
    dataset_size = Column(Integer, default=0, nullable=False)

    # Aggregated Metrics
    mean_precision_at_k = Column(Float, default=0.0, nullable=False)
    mean_recall_at_k = Column(Float, default=0.0, nullable=False)
    mean_mrr = Column(Float, default=0.0, nullable=False)
    mean_faithfulness = Column(Float, default=0.0, nullable=False)
    mean_answer_relevance = Column(Float, default=0.0, nullable=False)

    # Detailed query-level results and claim breakdown
    results_json = Column(JSONB, default=list, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    organization = relationship("Organization")
    user = relationship("User")
