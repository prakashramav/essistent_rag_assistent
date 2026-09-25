import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class CandidateChunk:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_title: str
    file_type: str
    content: str
    page_number: Optional[int] = None
    section: Optional[str] = None
    token_count: int = 0
    dense_score: Optional[float] = None
    fts_score: Optional[float] = None
    combined_score: float = 0.0
    rerank_score: Optional[float] = None
    metadata_json: Dict[str, Any] = field(default_factory=dict)


class BaseReranker(ABC):
    @abstractmethod
    async def rerank(
        self, query: str, candidates: List[CandidateChunk], top_k: int
    ) -> List[CandidateChunk]:
        """Rerank candidate chunks according to query relevance and return top_k candidates."""
        pass
