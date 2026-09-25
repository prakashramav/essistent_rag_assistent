from typing import Optional
from app.core.config import settings
from app.services.embeddings.base import BaseEmbeddingAdapter
from app.services.embeddings.gemini_adapter import GeminiEmbeddingAdapter
from app.services.embeddings.openai_adapter import OpenAIEmbeddingAdapter


def get_embedding_adapter(provider: Optional[str] = None) -> BaseEmbeddingAdapter:
    prov = (provider or "gemini").lower()
    if prov == "openai":
        return OpenAIEmbeddingAdapter()
    return GeminiEmbeddingAdapter()
