import io
import re
from typing import List
from pypdf import PdfReader
from app.services.parsers.base import BaseParser, ParsedContent


class PDFParser(BaseParser):
    def parse(self, file_bytes: bytes, filename: str = "") -> List[ParsedContent]:
        results: List[ParsedContent] = []
        stream = io.BytesIO(file_bytes)
        reader = PdfReader(stream)

        for page_idx, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            text = re.sub(r"[ \t]+", " ", text)
            text = re.sub(r"\n\s*\n", "\n\n", text).strip()

            if not text:
                continue

            results.append(
                ParsedContent(
                    text=text,
                    page_number=page_idx,
                    section=f"Page {page_idx}",
                    metadata={
                        "source": filename,
                        "file_type": "pdf",
                        "total_pages": len(reader.pages),
                    },
                )
            )

        return results
