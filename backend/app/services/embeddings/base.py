from abc import ABC, abstractmethod
from typing import List


class BaseEmbeddingAdapter(ABC):
    @property
    @abstractmethod
    def dimension(self) -> int:
        """The dimensionality of the vector embeddings produced by this model."""
        pass

    @abstractmethod
    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate embedding vectors for a list of document chunk texts."""
        pass

    @abstractmethod
    async def embed_query(self, query: str) -> List[float]:
        """Generate an embedding vector for a retrieval search query."""
        pass
