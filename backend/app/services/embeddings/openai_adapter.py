import logging
from typing import List
import httpx
from app.core.config import settings
from app.services.embeddings.base import BaseEmbeddingAdapter
from app.services.embeddings.gemini_adapter import _generate_deterministic_vector

logger = logging.getLogger(__name__)


class OpenAIEmbeddingAdapter(BaseEmbeddingAdapter):
    """
    Adapter for OpenAI text-embedding-3-small (swappable adapter interface).
    """
    def __init__(self, api_key: str = "", model_name: str = "text-embedding-3-small"):
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.model_name = model_name
        self._dim = 768  # dimensions parameter can be configured to 768 or 1536

    @property
    def dimension(self) -> int:
        return self._dim

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        if not self.api_key:
            return [_generate_deterministic_vector(t, self._dim) for t in texts]

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        url = "https://api.openai.com/v1/embeddings"
        payload = {
            "model": self.model_name,
            "input": texts,
            "dimensions": self._dim,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
                return [item["embedding"] for item in data.get("data", [])]
            except Exception as e:
                logger.warning(f"OpenAI embedding call failed: {e}. Falling back to deterministic vectors.")
                return [_generate_deterministic_vector(t, self._dim) for t in texts]

    async def embed_query(self, query: str) -> List[float]:
        res = await self.embed_texts([query])
        return res[0] if res else _generate_deterministic_vector(query, self._dim)
