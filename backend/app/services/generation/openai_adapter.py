import asyncio
import json
import logging
from typing import AsyncGenerator, Dict, List
import httpx
from app.core.config import settings
from app.services.generation.base import BaseGenerationAdapter
from app.services.generation.gemini_adapter import GeminiGenerationAdapter

logger = logging.getLogger(__name__)


class OpenAIGenerationAdapter(BaseGenerationAdapter):
    """
    Adapter for OpenAI chat completions models (e.g. gpt-4o, gpt-4o-mini).
    Supports live SSE streaming and delegates to deterministic fallback if key is missing.
    """

    def __init__(self, api_key: str = "", model_name: str = "gpt-4o-mini"):
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.model_name = model_name
        self._fallback_adapter = GeminiGenerationAdapter(api_key="", model_name="")

    async def generate(
        self,
        messages: List[Dict[str, str]],
        system_instruction: str = "",
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> str:
        collected = []
        async for chunk in self.generate_stream(
            messages=messages,
            system_instruction=system_instruction,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            collected.append(chunk)
        return "".join(collected)

    async def generate_stream(
        self,
        messages: List[Dict[str, str]],
        system_instruction: str = "",
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> AsyncGenerator[str, None]:
        if not self.api_key:
            async for chunk in self._fallback_adapter.generate_stream(
                messages=messages,
                system_instruction=system_instruction,
                temperature=temperature,
                max_tokens=max_tokens,
            ):
                yield chunk
            return

        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        formatted_messages = []
        if system_instruction:
            formatted_messages.append({"role": "system", "content": system_instruction})
        formatted_messages.extend(messages)

        payload = {
            "model": self.model_name,
            "messages": formatted_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                async with client.stream("POST", url, headers=headers, json=payload) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        if line.startswith("data: "):
                            data_str = line[6:].strip()
                            if data_str == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data_str)
                                delta = chunk["choices"][0]["delta"].get("content", "")
                                if delta:
                                    yield delta
                            except (json.JSONDecodeError, KeyError, IndexError):
                                continue
        except Exception as e:
            logger.warning(f"OpenAI stream failed: {e}. Using deterministic synthesis fallback.")
            async for chunk in self._fallback_adapter.generate_stream(
                messages=messages,
                system_instruction=system_instruction,
                temperature=temperature,
                max_tokens=max_tokens,
            ):
                yield chunk
