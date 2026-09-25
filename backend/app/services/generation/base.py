from abc import ABC, abstractmethod
from typing import AsyncGenerator, Dict, List


class BaseGenerationAdapter(ABC):
    """Abstract interface for LLM text generation adapters."""

    @abstractmethod
    async def generate(
        self,
        messages: List[Dict[str, str]],
        system_instruction: str = "",
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> str:
        """Generates a complete response for given conversation messages and system instructions."""
        pass

    @abstractmethod
    async def generate_stream(
        self,
        messages: List[Dict[str, str]],
        system_instruction: str = "",
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> AsyncGenerator[str, None]:
        """Streams response tokens asynchronously."""
        pass
