from app.services.reranking.base import BaseReranker
from app.services.reranking.llm_reranker import LLMReranker


def get_reranker() -> BaseReranker:
    return LLMReranker()
