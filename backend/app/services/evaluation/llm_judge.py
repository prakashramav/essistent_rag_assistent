import json
import logging
import re
from typing import Dict, List, Optional
import httpx
from app.core.config import settings
from app.schemas.evaluation import ClaimVerdict
from app.schemas.retrieval import SearchResultChunk

logger = logging.getLogger(__name__)

EVALUATION_JUDGE_PROMPT = """You are an impartial, highly rigorous evaluation judge for an Enterprise RAG Assistant.
Analyze the following Question, Retrieved Context Passages, and Generated Answer.

Your evaluation must compute:
1. Faithfulness (Groundedness): Break the answer into distinct factual claims. For each claim, check whether it is directly supported by the context passages. If a claim makes assertions not found in the context, mark it unsupported.
2. Answer Relevance: Does the generated answer directly and concisely address the user's question without extraneous off-topic information?

Return a strict, valid JSON object with the following schema:
{
  "faithfulness_score": <float between 0.0 and 1.0>,
  "answer_relevance_score": <float between 0.0 and 1.0>,
  "verdict": "<FAITHFUL | BORDERLINE | HALLUCINATION_DETECTED>",
  "claims": [
    {
      "claim": "<text of claim>",
      "supported": <true | false>,
      "evidence_snippet": "<matching snippet from context or null>",
      "reasoning": "<explanation>"
    }
  ]
}
"""


class LLMJudge:
    def __init__(self, api_key: str = ""):
        self.api_key = api_key or settings.GEMINI_API_KEY

    async def evaluate(
        self,
        question: str,
        retrieved_chunks: List[SearchResultChunk],
        generated_answer: str,
        ground_truth_answer: Optional[str] = None,
    ) -> Dict[str, any]:
        """
        Evaluates faithfulness and answer relevance.
        Uses Gemini LLM judge if API key is configured; otherwise uses deterministic claim audit.
        """
        if self.api_key:
            try:
                return await self._evaluate_with_gemini(question, retrieved_chunks, generated_answer)
            except Exception as e:
                logger.warning(f"Live LLM evaluation failed ({e}). Falling back to deterministic judge.")

        return self._evaluate_deterministic(question, retrieved_chunks, generated_answer)

    async def _evaluate_with_gemini(
        self,
        question: str,
        retrieved_chunks: List[SearchResultChunk],
        generated_answer: str,
    ) -> Dict[str, any]:
        context_str = "\n\n".join(
            f"Passage [{c.chunk_id}]: {c.content}" for c in retrieved_chunks
        )
        user_content = f"Question: {question}\n\nContext:\n{context_str}\n\nGenerated Answer:\n{generated_answer}"

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent?key={self.api_key}"
        payload = {
            "system_instruction": {"parts": [{"text": EVALUATION_JUDGE_PROMPT}]},
            "contents": [{"role": "user", "parts": [{"text": user_content}]}],
            "generationConfig": {"response_mime_type": "application/json", "temperature": 0.0},
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            text_response = data["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(text_response)

    def _evaluate_deterministic(
        self,
        question: str,
        retrieved_chunks: List[SearchResultChunk],
        generated_answer: str,
    ) -> Dict[str, any]:
        """
        Deterministic, offline evaluation analyzing sentence-level claims against context passages.
        """
        clean_text = generated_answer.strip()
        is_refusal = (
            "do not have enough information" in clean_text.lower()
            or "not enough information" in clean_text.lower()
        )

        all_context = " ".join(c.content.lower() for c in retrieved_chunks)
        valid_chunk_ids = {str(c.chunk_id) for c in retrieved_chunks}

        # If it's a correct refusal when context is missing, it is 100% faithful
        if is_refusal:
            return {
                "faithfulness_score": 1.0,
                "answer_relevance_score": 0.9,
                "verdict": "FAITHFUL",
                "claims": [
                    ClaimVerdict(
                        claim=clean_text[:120],
                        supported=True,
                        evidence_snippet=None,
                        reasoning="Appropriate refusal given lack of supporting documentation in knowledge base.",
                    ).model_dump()
                ],
            }

        # Break answer into sentences/claims
        sentences = [
            s.strip()
            for s in re.split(r"[.!?]\s+", clean_text)
            if len(s.strip()) > 10 and not s.strip().startswith("Based on")
        ]

        if not sentences:
            sentences = [clean_text]

        claims_result = []
        supported_count = 0

        for sentence in sentences:
            # Check citations in sentence
            cite_matches = re.findall(r"\[(?:cite:)?([0-9a-fA-F\-]{36})\]", sentence)
            has_valid_citation = any(cid in valid_chunk_ids for cid in cite_matches)

            # Check keyword overlap with context
            words = set(re.findall(r"\w+", sentence.lower())) - {
                "the", "a", "an", "is", "are", "and", "or", "in", "to", "of", "with", "that", "this", "according"
            }
            context_words = set(re.findall(r"\w+", all_context))
            overlap = len(words.intersection(context_words))
            overlap_ratio = overlap / len(words) if words else 0.0

            supported = has_valid_citation or overlap_ratio >= 0.5

            snippet_evidence = None
            if supported and retrieved_chunks:
                snippet_evidence = retrieved_chunks[0].content[:200]

            if supported:
                supported_count += 1
                reasoning = (
                    "Claim directly supported by verified citation."
                    if has_valid_citation
                    else f"Claim content matches context terms ({int(overlap_ratio * 100)}% lexical overlap)."
                )
            else:
                reasoning = "Extrapolated assertion not directly grounded in retrieved context passages."

            claims_result.append(
                ClaimVerdict(
                    claim=sentence[:150],
                    supported=supported,
                    evidence_snippet=snippet_evidence,
                    reasoning=reasoning,
                ).model_dump()
            )

        total_claims = len(sentences)
        faithfulness_score = round(supported_count / total_claims, 2) if total_claims > 0 else 1.0

        # Calculate answer relevance based on question keywords addressed in answer
        q_words = set(re.findall(r"\w+", question.lower())) - {"what", "who", "when", "where", "why", "how", "the", "is", "are", "do", "does"}
        ans_words = set(re.findall(r"\w+", clean_text.lower()))
        q_overlap = len(q_words.intersection(ans_words))
        answer_relevance_score = round(min(1.0, (q_overlap / len(q_words)) + 0.3), 2) if q_words else 0.9

        verdict = (
            "FAITHFUL"
            if faithfulness_score >= 0.8
            else "BORDERLINE"
            if faithfulness_score >= 0.5
            else "HALLUCINATION_DETECTED"
        )

        return {
            "faithfulness_score": faithfulness_score,
            "answer_relevance_score": answer_relevance_score,
            "verdict": verdict,
            "claims": claims_result,
        }
