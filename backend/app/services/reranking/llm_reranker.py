import json
import logging
import re
from typing import List
import httpx
from app.core.config import settings
from app.services.reranking.base import BaseReranker, CandidateChunk

logger = logging.getLogger(__name__)


class LLMReranker(BaseReranker):
    """
    Reranks candidates using an LLM (Gemini 1.5 Pro / Flash) relevance scoring call.
    Falls back gracefully to combined hybrid score if LLM call is unavailable.
    """
    def __init__(self, api_key: str = "", model_name: str = "gemini-1.5-flash"):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model_name = model_name

    async def rerank(
        self, query: str, candidates: List[CandidateChunk], top_k: int
    ) -> List[CandidateChunk]:
        if not candidates:
            return []

        if not self.api_key:
            return self._heuristic_rerank(query, candidates, top_k)

        # Build prompt for LLM scoring
        passages_text = ""
        for idx, c in enumerate(candidates):
            snippet = c.content[:300].replace("\n", " ")
            passages_text += f"[{idx}] {snippet}\n\n"

        prompt = f"""You are a RAG retrieval reranker.
Score the relevance of each candidate passage to the user query on a scale of 0 to 10.
Query: "{query}"

Candidate Passages:
{passages_text}

Output ONLY a JSON array of objects with "index" and "score" (float 0.0 to 10.0), e.g.:
[
  {{"index": 0, "score": 9.5}},
  {{"index": 1, "score": 4.0}}
]
"""

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.0, "responseMimeType": "application/json"},
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
                text_out = data["candidates"][0]["content"]["parts"][0]["text"]
                scored_items = json.loads(text_out)

                score_map = {item["index"]: float(item["score"]) / 10.0 for item in scored_items if "index" in item}
                for idx, c in enumerate(candidates):
                    c.rerank_score = score_map.get(idx, c.combined_score)

                candidates.sort(key=lambda c: (c.rerank_score or 0.0), reverse=True)
                return candidates[:top_k]

            except Exception as e:
                logger.warning(f"LLM reranking request failed: {e}. Falling back to heuristic reranking.")
                return self._heuristic_rerank(query, candidates, top_k)

    def _heuristic_rerank(
        self, query: str, candidates: List[CandidateChunk], top_k: int
    ) -> List[CandidateChunk]:
        """Fast lexical + exact match heuristic scorer."""
        query_words = set(re.findall(r"\w+", query.lower()))
        for c in candidates:
            content_lower = c.content.lower()
            # Exact phrase bonus
            exact_bonus = 0.3 if query.lower() in content_lower else 0.0
            # Word coverage
            matches = sum(1 for w in query_words if w in content_lower)
            coverage = (matches / len(query_words)) if query_words else 0.0
            
            # Blend with existing hybrid score
            c.rerank_score = round(min(1.0, (c.combined_score * 0.5) + (coverage * 0.3) + exact_bonus), 4)

        candidates.sort(key=lambda c: (c.rerank_score or 0.0), reverse=True)
        return candidates[:top_k]
