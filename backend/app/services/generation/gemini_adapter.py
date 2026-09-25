import asyncio
import json
import logging
import re
from typing import AsyncGenerator, Dict, List
import httpx
from app.core.config import settings
from app.services.generation.base import BaseGenerationAdapter

logger = logging.getLogger(__name__)


class GeminiGenerationAdapter(BaseGenerationAdapter):
    """
    Adapter for Google Gemini generation models (gemini-1.5-pro, gemini-2.0-flash, gemini-1.5-flash).
    Supports SSE streaming directly from the Gemini REST endpoint, with deterministic offline
    grounded synthesis fallback for testing environments without an active API key.
    """

    def __init__(self, api_key: str = "", model_name: str = ""):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model_name = model_name or settings.DEFAULT_CHAT_MODEL or "gemini-1.5-pro"

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
        # If API key is present, attempt live streaming from Gemini
        if self.api_key:
            try:
                async for chunk in self._stream_gemini_api(
                    messages=messages,
                    system_instruction=system_instruction,
                    temperature=temperature,
                    max_tokens=max_tokens,
                ):
                    yield chunk
                return
            except Exception as e:
                logger.warning(f"Live Gemini stream failed ({e}). Falling back to deterministic grounded synthesis.")

        # Offline / deterministic synthesis fallback
        async for chunk in self._fallback_deterministic_stream(messages, system_instruction):
            yield chunk

    async def _stream_gemini_api(
        self,
        messages: List[Dict[str, str]],
        system_instruction: str,
        temperature: float,
        max_tokens: int,
    ) -> AsyncGenerator[str, None]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:streamGenerateContent?alt=sse&key={self.api_key}"

        # Map standard roles ('user', 'assistant') to Gemini format ('user', 'model')
        contents = []
        for m in messages:
            role = "model" if m.get("role") in ("assistant", "model") else "user"
            contents.append({
                "role": role,
                "parts": [{"text": m.get("content", "")}]
            })

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }

        if system_instruction:
            payload["system_instruction"] = {
                "parts": [{"text": system_instruction}]
            }

        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", url, json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    if line.startswith("data: "):
                        json_str = line[6:].strip()
                        if json_str == "[DONE]":
                            break
                        try:
                            data = json.loads(json_str)
                            candidates = data.get("candidates", [])
                            if candidates:
                                parts = candidates[0].get("content", {}).get("parts", [])
                                for p in parts:
                                    text = p.get("text", "")
                                    if text:
                                        yield text
                        except json.JSONDecodeError:
                            continue

    async def _fallback_deterministic_stream(
        self,
        messages: List[Dict[str, str]],
        system_instruction: str,
    ) -> AsyncGenerator[str, None]:
        """
        Deterministic, offline synthesis that parses passages embedded in the system prompt / query,
        synthesizes grounded sentences, and appends citations [cite:<chunk_id>].
        """
        last_user_msg = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                last_user_msg = m.get("content", "")
                break

        full_prompt_text = system_instruction + "\n" + last_user_msg
        
        # Regex to detect Passage [ID: <uuid>] (Doc: "<title>", Page: <num>)
        passage_regex = re.compile(
            r"--- Passage \[ID: ([0-9a-fA-F\-]{36})\] \(Doc: \"(.*?)\"(?:, Page: (.*?))?\) ---\s*\n(.*?)(?=(?:--- Passage|\Z))",
            re.DOTALL
        )
        passages = passage_regex.findall(full_prompt_text)

        if not passages:
            refusal = "I do not have enough information in the provided documents to answer this question."
            for word in refusal.split(" "):
                yield word + " "
                await asyncio.sleep(0.01)
            return

        # Score passages against user query keywords
        query_words = set(re.findall(r"\w+", last_user_msg.lower())) - {"what", "who", "when", "where", "why", "how", "the", "a", "an", "is", "are"}
        scored_passages = []
        for chunk_id, title, page, body in passages:
            body_words = set(re.findall(r"\w+", body.lower()))
            overlap = len(query_words.intersection(body_words))
            scored_passages.append((overlap, chunk_id, title, page, body.strip()))

        scored_passages.sort(key=lambda x: x[0], reverse=True)

        if scored_passages[0][0] == 0 and len(query_words) > 0:
            refusal = "I do not have enough information in the provided documents to answer this question."
            for word in refusal.split(" "):
                yield word + " "
                await asyncio.sleep(0.01)
            return

        # Take the top relevant passages (up to 3)
        relevant = [p for p in scored_passages if p[0] > 0][:3]
        if not relevant:
            relevant = scored_passages[:2]

        response_sentences = ["Based on the provided documents:"]
        for _, chunk_id, title, page, body in relevant:
            sentences = [s.strip() for s in re.split(r"[.!?]\s+", body) if len(s.strip()) > 15]
            summary_snippet = sentences[0] if sentences else body[:140]
            page_info = f" (p. {page})" if page and page.strip() not in ("None", "N/A") else ""
            response_sentences.append(
                f"- According to {title}{page_info}, {summary_snippet.rstrip('.')} [cite:{chunk_id}]."
            )

        full_response = "\n\n".join(response_sentences)
        # Stream response token by token
        words = full_response.split(" ")
        for i, word in enumerate(words):
            yield word + (" " if i < len(words) - 1 else "")
            await asyncio.sleep(0.008)
