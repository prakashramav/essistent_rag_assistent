import os
from typing import Optional
from app.services.parsers.base import BaseParser
from app.services.parsers.docx_parser import DocxParser
from app.services.parsers.pdf_parser import PDFParser
from app.services.parsers.txt_parser import TxtParser


def get_parser_for_filename(filename: str) -> Optional[BaseParser]:
    ext = os.path.splitext(filename)[1].lower()
    if ext == ".pdf":
        return PDFParser()
    elif ext in [".docx", ".doc"]:
        return DocxParser()
    elif ext in [".txt", ".md", ".csv", ".json", ".log"]:
        return TxtParser()
    return None
