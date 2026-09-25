import re
from typing import List, Tuple
from bs4 import BeautifulSoup
import httpx
from app.services.parsers.base import ParsedContent


class WebParser:
    @staticmethod
    async def fetch_and_parse(url: str) -> Tuple[str, List[ParsedContent]]:
        """
        Fetch HTML from URL asynchronously and extract clean text sections.
        Returns (page_title, list of ParsedContent).
        """
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
        }

        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, headers=headers) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            html_text = resp.text

        soup = BeautifulSoup(html_text, "html.parser")

        # Strip non-content elements
        for element in soup(["script", "style", "nav", "footer", "aside", "noscript", "svg"]):
            element.decompose()

        page_title = soup.title.string.strip() if soup.title and soup.title.string else url

        # Find main content container if available
        main_content = soup.find("main") or soup.find("article") or soup.find("body") or soup

        results: List[ParsedContent] = []
        current_section = page_title
        current_text_blocks: List[str] = []
        section_idx = 1

        for tag in main_content.find_all(["h1", "h2", "h3", "p", "li"]):
            text = tag.get_text(separator=" ", strip=True)
            if not text:
                continue

            if tag.name in ["h1", "h2", "h3"]:
                if current_text_blocks:
                    joined = "\n\n".join(current_text_blocks)
                    if len(joined) > 40:
                        results.append(
                            ParsedContent(
                                text=joined,
                                page_number=section_idx,
                                section=current_section,
                                metadata={"url": url, "title": page_title},
                            )
                        )
                        section_idx += 1
                        current_text_blocks = []
                current_section = text
            else:
                current_text_blocks.append(text)

        # Flush final section
        if current_text_blocks:
            joined = "\n\n".join(current_text_blocks)
            if len(joined) > 30:
                results.append(
                    ParsedContent(
                        text=joined,
                        page_number=section_idx,
                        section=current_section,
                        metadata={"url": url, "title": page_title},
                    )
                )

        # Fallback if no structured tags matched
        if not results:
            clean_text = main_content.get_text(separator="\n", strip=True)
            clean_text = re.sub(r"\n\s*\n+", "\n\n", clean_text)
            if clean_text:
                results.append(
                    ParsedContent(
                        text=clean_text,
                        page_number=1,
                        section=page_title,
                        metadata={"url": url, "title": page_title},
                    )
                )

        return page_title, results
