import re
from typing import List
from app.services.parsers.base import BaseParser, ParsedContent


class TxtParser(BaseParser):
    def parse(self, file_bytes: bytes, filename: str = "") -> List[ParsedContent]:
        try:
            content = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            content = file_bytes.decode("latin-1", errors="replace")

        content = content.replace("\r\n", "\n").strip()
        if not content:
            return []

        # Split into sections if Markdown headers (# Header) exist
        sections = re.split(r"\n(?=#{1,3}\s+)", content)
        if len(sections) > 1:
            results = []
            for idx, sec in enumerate(sections, start=1):
                sec = sec.strip()
                if not sec:
                    continue
                lines = sec.split("\n", 1)
                heading = lines[0].lstrip("#").strip() if len(lines) > 0 else f"Section {idx}"
                results.append(
                    ParsedContent(
                        text=sec,
                        page_number=idx,
                        section=heading,
                        metadata={"source": filename, "file_type": "txt"},
                    )
                )
            return results

        return [
            ParsedContent(
                text=content,
                page_number=1,
                section="Document Body",
                metadata={"source": filename, "file_type": "txt"},
            )
        ]
