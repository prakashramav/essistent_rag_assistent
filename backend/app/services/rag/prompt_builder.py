import uuid
from typing import Dict, List, Optional
from app.models.message import Message
from app.schemas.retrieval import SearchResultChunk

SYSTEM_PROMPT_TEMPLATE = """You are an Enterprise AI Assistant answering questions accurately and truthfully for employees and organizations based SOLELY on the internal company documents provided in the Context Passages below.

CRITICAL INSTRUCTIONS:
1. Strict Grounding: Every factual statement or claim you make MUST be directly supported by the context passages below. Never extrapolate, speculate, or introduce external knowledge not present in the passages.
2. Refusal Requirement: If the provided context passages do not contain enough facts to answer the question with certainty, state clearly and honestly:
   "I do not have enough information in the provided documents to answer this question."
   Do NOT attempt to guess or partially hallucinate an answer.
3. Citation Discipline: You MUST insert an inline citation token immediately following each statement or claim derived from a passage.
   Use the exact format: [cite:<chunk_id>]
   Where <chunk_id> is the passage ID.
   Example: "The annual recurring revenue reached $12M in Q4 2024 [cite:a7e8b9c0-1234-5678-9abc-def012345678]."
   You may cite multiple sources if a statement synthesizes multiple passages: "[cite:UUID-1] [cite:UUID-2]".
4. Professional Formatting: Format your answers in clean, readable markdown with bullet points, numbered lists, or short paragraphs where appropriate.
"""


def build_system_prompt(chunks: List[SearchResultChunk]) -> str:
    """Builds the grounding system prompt populated with retrieved document chunks."""
    passages_text = []
    for chunk in chunks:
        page_str = f", Page: {chunk.page_number}" if chunk.page_number is not None else ""
        passages_text.append(
            f'--- Passage [ID: {chunk.chunk_id}] (Doc: "{chunk.document_title}"{page_str}) ---\n{chunk.content.strip()}'
        )

    context_block = "\n\n".join(passages_text) if passages_text else "No relevant document passages were found."

    return f"{SYSTEM_PROMPT_TEMPLATE}\n\n=== CONTEXT PASSAGES ===\n{context_block}\n=== END CONTEXT PASSAGES ==="


def build_conversation_history(
    messages: List[Message],
    max_history_turns: int = 10,
) -> List[Dict[str, str]]:
    """
    Constructs a sliding window of recent conversation history formatted for LLM messages.
    Limits context to the last `max_history_turns` messages to respect context limits.
    """
    formatted = []
    # Take the last N messages
    recent_messages = messages[-max_history_turns:] if len(messages) > max_history_turns else messages

    for msg in recent_messages:
        role = "assistant" if msg.sender_type.value == "assistant" else "user"
        formatted.append({
            "role": role,
            "content": msg.content,
        })

    return formatted
