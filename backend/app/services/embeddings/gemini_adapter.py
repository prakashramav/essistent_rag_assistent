import hashlib
import logging
import math
from typing import List
import httpx
from app.core.config import settings
from app.services.embeddings.base import BaseEmbeddingAdapter

logger = logging.getLogger(__name__)


def _generate_deterministic_vector(text: str, dim: int = 768) -> List[float]:
    """Generates a pseudo-random, deterministic unit vector of given dimension from text."""
    seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:12], 16)
    vec = []
    for i in range(dim):
        val = math.sin((seed + i * 31) % 10000)
        vec.append(val)
    # Normalize to unit length for cosine distance
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


class GeminiEmbeddingAdapter(BaseEmbeddingAdapter):
    """
    Adapter for Google Gemini text-embedding-004 model (768 dimensions).
    Uses async httpx with automatic chunk batching up to 100 items per call.
    """
    def __init__(self, api_key: str = "", model_name: str = "text-embedding-004"):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model_name = model_name
        self._dim = 768

    @property
    def dimension(self) -> int:
        return self._dim

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        # Fallback to deterministic vectors if API key is not supplied
        if not self.api_key:
            logger.info("GEMINI_API_KEY not set. Using deterministic pseudo-embeddings for testing/offline.")
            return [_generate_deterministic_vector(t, self._dim) for t in texts]

        # Google Gemini batchEmbedContents endpoint accepts up to 100 requests per batch
        batch_size = 100
        all_embeddings: List[List[float]] = []

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:batchEmbedContents?key={self.api_key}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            for i in range(0, len(texts), batch_size):
                batch_slice = texts[i : i + batch_size]
                payload = {
                    "requests": [
                        {
                            "model": f"models/{self.model_name}",
                            "content": {"parts": [{"text": t}]},
                            "taskType": "RETRIEVAL_DOCUMENT",
                        }
                        for t in batch_slice
                    ]
                }

                try:
                    resp = await client.post(url, json=payload)
                    resp.raise_for_status()
                    data = resp.json()
                    for entry in data.get("embeddings", []):
                        values = entry.get("values", [])
                        all_embeddings.append(values)
                except Exception as e:
                    logger.warning(f"Gemini embedding API call failed: {e}. Falling back to deterministic vectors.")
                    for t in batch_slice:
                        all_embeddings.append(_generate_deterministic_vector(t, self._dim))

        return all_embeddings

    async def embed_query(self, query: str) -> List[float]:
        if not self.api_key:
            return _generate_deterministic_vector(query, self._dim)

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:embedContent?key={self.api_key}"
        payload = {
            "model": f"models/{self.model_name}",
            "content": {"parts": [{"text": query}]},
            "taskType": "RETRIEVAL_QUERY",
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
                return data.get("embedding", {}).get("values", [])
            except Exception as e:
                logger.warning(f"Gemini query embedding failed: {e}. Falling back to deterministic vector.")
                return _generate_deterministic_vector(query, self._dim)
