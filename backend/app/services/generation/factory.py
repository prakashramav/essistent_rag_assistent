from typing import Optional
from app.core.config import settings
from app.services.generation.base import BaseGenerationAdapter
from app.services.generation.gemini_adapter import GeminiGenerationAdapter
from app.services.generation.openai_adapter import OpenAIGenerationAdapter


def get_generation_adapter(
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
    api_key: Optional[str] = None,
) -> BaseGenerationAdapter:
    """
    Factory function returning the configured LLM generation adapter.
    Defaults to Gemini ('gemini-1.5-pro' / 'gemini-2.0-flash').
    """
    prov = (provider or ("openai" if settings.OPENAI_API_KEY and not settings.GEMINI_API_KEY else "gemini")).lower()

    if prov == "openai":
        return OpenAIGenerationAdapter(
            api_key=api_key or settings.OPENAI_API_KEY,
            model_name=model_name or "gpt-4o-mini",
        )
    
    # Default to Gemini
    return GeminiGenerationAdapter(
        api_key=api_key or settings.GEMINI_API_KEY,
        model_name=model_name or settings.DEFAULT_CHAT_MODEL or "gemini-1.5-pro",
    )
