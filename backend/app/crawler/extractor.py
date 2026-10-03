"""Content extraction and text normalization using Trafilatura and BeautifulSoup4."""

import re
import unicodedata
from dataclasses import dataclass
from typing import Optional, Tuple
from bs4 import BeautifulSoup
import trafilatura


@dataclass
class ExtractedContent:
    title: str
    text: str
    canonical_url: Optional[str] = None
    raw_size_bytes: int = 0


def normalize_text(text: str) -> str:
    """Normalize extracted text consistently.
    
    - NFKC Unicode normalization
    - Standardize line endings (\n)
    - Collapse multiple horizontal whitespace while preserving paragraph structure
    - Preserve punctuation, prices, dates, acronyms, and casing
    """
    if not text:
        return ""

    # NFKC Unicode normalization
    normalized = unicodedata.normalize("NFKC", text)

    # Standardize line endings
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")

    # Clean lines and horizontal whitespace
    cleaned_lines = []
    for line in normalized.split("\n"):
        # Replace multiple spaces/tabs with single space
        cleaned_line = re.sub(r"[^\S\n]+", " ", line).strip()
        cleaned_lines.append(cleaned_line)

    # Join lines and collapse excessive consecutive blank lines (max 2 consecutive newlines)
    result = "\n".join(cleaned_lines)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()


def extract_metadata(soup: BeautifulSoup) -> Tuple[str, Optional[str]]:
    """Extract page title and canonical URL using BeautifulSoup."""
    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    elif soup.find("h1"):
        h1 = soup.find("h1")
        if h1 and h1.get_text():
            title = h1.get_text().strip()

    canonical_url = None
    canonical_tag = soup.find("link", rel=lambda val: val and "canonical" in val.lower())
    if canonical_tag and canonical_tag.get("href"):
        canonical_url = str(canonical_tag["href"]).strip()

    return title, canonical_url


def fallback_bs4_extract(soup: BeautifulSoup) -> str:
    """Fallback text extractor when Trafilatura returns empty text."""
    # Create a copy so we don't destroy original DOM
    body = soup.find("body") or soup
    
    # Remove non-content elements
    for element in body(["script", "style", "noscript", "svg", "iframe"]):
        element.decompose()

    text = body.get_text(separator="\n")
    return text


def extract_content(html: str, url: Optional[str] = None) -> ExtractedContent:
    """Extract readable text and metadata from raw HTML.
    
    Uses Trafilatura for primary extraction with BeautifulSoup as fallback.
    """
    if not html:
        return ExtractedContent(title="", text="", canonical_url=None, raw_size_bytes=0)

    raw_bytes = len(html.encode("utf-8", errors="ignore"))
    soup = BeautifulSoup(html, "html.parser")
    title, canonical_url = extract_metadata(soup)

    # Try Trafilatura main-content extraction
    text = trafilatura.extract(
        html,
        url=url,
        include_links=False,
        include_images=False,
        include_tables=True,
        include_comments=False,
        output_format="txt",
        no_fallback=False,
    )

    # If Trafilatura fails or returns empty, use BeautifulSoup fallback
    if not text or not text.strip():
        text = fallback_bs4_extract(soup)

    normalized_text = normalize_text(text)

    return ExtractedContent(
        title=title,
        text=normalized_text,
        canonical_url=canonical_url,
        raw_size_bytes=raw_bytes,
    )
