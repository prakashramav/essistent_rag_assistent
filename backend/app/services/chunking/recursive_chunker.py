from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from app.services.parsers.base import ParsedContent


@dataclass
class ChunkItem:
    chunk_index: int
    content: str
    page_number: Optional[int] = None
    section: Optional[str] = None
    token_count: int = 0
    metadata_json: Dict[str, Any] = field(default_factory=dict)


class RecursiveTokenChunker:
    """
    Splits text recursively using natural boundaries (\n\n, \n, sentence ends, words),
    preserving page numbers, sections, and metadata across all chunks.
    """
    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        separators: Optional[List[str]] = None,
    ):
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be strictly less than chunk_size")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or ["\n\n", "\n", ". ", "? ", "! ", "; ", " ", ""]

    def _split_text(self, text: str, separators: List[str]) -> List[str]:
        """Recursively split text using the given separators."""
        final_splits: List[str] = []
        separator = separators[-1]
        new_separators: List[str] = []

        for i, sep in enumerate(separators):
            if sep == "":
                separator = ""
                break
            if sep in text:
                separator = sep
                new_separators = separators[i + 1:]
                break

        splits = text.split(separator) if separator else list(text)

        good_splits: List[str] = []
        for s in splits:
            if not s:
                continue
            if len(s) < self.chunk_size:
                good_splits.append(s)
            else:
                if new_separators:
                    other_splits = self._split_text(s, new_separators)
                    good_splits.extend(other_splits)
                else:
                    # Hard truncate if no smaller separator left
                    for chunk_start in range(0, len(s), self.chunk_size - self.chunk_overlap):
                        good_splits.append(s[chunk_start:chunk_start + self.chunk_size])

        return good_splits

    def _merge_splits(self, splits: List[str], separator: str = " ") -> List[str]:
        """Merge smaller splits into chunks with sliding overlap window."""
        chunks: List[str] = []
        current_chunk: List[str] = []
        current_len = 0

        for split in splits:
            split_len = len(split)
            if current_len + split_len + (1 if current_chunk else 0) > self.chunk_size:
                if current_chunk:
                    chunk_text = separator.join(current_chunk).strip()
                    if chunk_text:
                        chunks.append(chunk_text)

                    # Backtrack to satisfy chunk_overlap
                    while current_chunk and current_len > self.chunk_overlap:
                        removed = current_chunk.pop(0)
                        current_len -= len(removed) + (1 if current_chunk else 0)

            current_chunk.append(split)
            current_len += split_len + (1 if len(current_chunk) > 1 else 0)

        if current_chunk:
            chunk_text = separator.join(current_chunk).strip()
            if chunk_text:
                chunks.append(chunk_text)

        return chunks

    def chunk_document(self, parsed_contents: List[ParsedContent]) -> List[ChunkItem]:
        """Chunks a document's parsed contents into sequential ChunkItems with preserved metadata."""
        all_chunks: List[ChunkItem] = []
        global_chunk_index = 0

        for item in parsed_contents:
            if not item.text or not item.text.strip():
                continue

            raw_splits = self._split_text(item.text, self.separators)
            merged_chunks = self._merge_splits(raw_splits)

            for chunk_str in merged_chunks:
                clean_chunk = chunk_str.strip()
                if not clean_chunk:
                    continue

                # Estimate tokens (average 4 chars per token)
                token_count = max(1, len(clean_chunk) // 4)

                metadata = dict(item.metadata)
                metadata.update({
                    "char_length": len(clean_chunk),
                    "page_number": item.page_number,
                    "section": item.section,
                })

                all_chunks.append(
                    ChunkItem(
                        chunk_index=global_chunk_index,
                        content=clean_chunk,
                        page_number=item.page_number,
                        section=item.section,
                        token_count=token_count,
                        metadata_json=metadata,
                    )
                )
                global_chunk_index += 1

        return all_chunks
