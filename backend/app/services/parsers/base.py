from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ParsedContent:
    text: str
    page_number: Optional[int] = None
    section: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseParser(ABC):
    @abstractmethod
    def parse(self, file_bytes: bytes, filename: str = "") -> List[ParsedContent]:
        """Extract text and metadata from file bytes, returning a list of ParsedContent items."""
        pass
