import re
import uuid
from typing import Dict, List, Set
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.citation import Citation
from app.schemas.chat import CitationOut
from app.schemas.retrieval import SearchResultChunk


CITATION_PATTERN = re.compile(r"\[cite:([0-9a-fA-F\-]{36})\]|\[([0-9a-fA-F\-]{36})\]")


class CitationService:
    @staticmethod
    def extract_cited_chunk_ids(text: str) -> Set[uuid.UUID]:
        """Extracts unique cited chunk UUIDs from generated text."""
        cited = set()
        for match in CITATION_PATTERN.finditer(text):
            chunk_id_str = match.group(1) or match.group(2)
            if chunk_id_str:
                try:
                    cited.add(uuid.UUID(chunk_id_str))
                except ValueError:
                    continue
        return cited

    @classmethod
    async def create_citations_for_message(
        cls,
        db: AsyncSession,
        message_id: uuid.UUID,
        organization_id: uuid.UUID,
        generated_text: str,
        retrieved_chunks: List[SearchResultChunk],
    ) -> List[CitationOut]:
        """
        Parses citations in the generated response, matches them to retrieved chunks,
        persists them to the PostgreSQL database, and returns CitationOut models.
        """
        chunk_map: Dict[uuid.UUID, SearchResultChunk] = {
            chunk.chunk_id: chunk for chunk in retrieved_chunks
        }

        cited_ids = cls.extract_cited_chunk_ids(generated_text)

        # If LLM didn't emit strict [cite:...] tags but used information from top chunks,
        # and did not refuse, link the top 1-2 chunks with highest relevance score as sources
        is_refusal = "do not have enough information" in generated_text.lower() or "not enough information" in generated_text.lower()
        if not cited_ids and not is_refusal and retrieved_chunks:
            # Associate top chunk(s)
            for top_chunk in retrieved_chunks[:2]:
                cited_ids.add(top_chunk.chunk_id)

        citations_to_create: List[Citation] = []
        citation_out_list: List[CitationOut] = []

        for cid in cited_ids:
            chunk = chunk_map.get(cid)
            if not chunk:
                continue

            citation_id = uuid.uuid4()
            snippet = chunk.content[:400].strip()

            citation_record = Citation(
                id=citation_id,
                message_id=message_id,
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                organization_id=organization_id,
                snippet=snippet,
                page_number=chunk.page_number,
            )
            citations_to_create.append(citation_record)

            citation_out_list.append(
                CitationOut(
                    id=citation_id,
                    message_id=message_id,
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    document_title=chunk.document_title,
                    file_type=chunk.file_type,
                    snippet=snippet,
                    page_number=chunk.page_number,
                    score=chunk.combined_score,
                )
            )

        if citations_to_create:
            db.add_all(citations_to_create)
            await db.flush()

        return citation_out_list
