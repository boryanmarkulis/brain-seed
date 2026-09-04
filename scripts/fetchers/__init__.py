"""
fetchers - source-specific fetchers for pull.py.

Each fetcher module exposes a single `fetch(url: str) -> FetchResult` function.
Fetchers run as direct Python (no MCP, no LLM in the path) so bulk ingests
don't burn tokens.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable
from urllib.parse import urlparse


@dataclass
class FetchResult:
    title: str
    markdown: str
    source_url: str
    default_type: str
    created_date: str | None = None
    links: list[str] = field(default_factory=list)


@dataclass
class FetchBatch:
    """Returned by fetchers that yield multiple results (e.g. Notion DB, Drive folder, Substack archive)."""
    results: list[FetchResult]
    source_url: str


def slugify(text: str, max_len: int = 60) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text[:max_len] or "untitled"


def route(url: str) -> str:
    """Return the fetcher name for a URL."""
    host = (urlparse(url).hostname or "").lower()
    if "notion.so" in host or "notion.site" in host:
        return "notion"
    if host == "docs.google.com" and "/document" in url:
        return "gdoc"
    if host == "docs.google.com" and "/spreadsheets" in url:
        return "gsheet"
    if host == "drive.google.com" and "/folders" in url:
        return "gdrive"
    if "loom.com" in host and "/looms/videos" in url:
        return "loom_library"
    if "loom.com" in host:
        return "loom"
    if "youtube.com" in host or "youtu.be" in host:
        return "youtube"
    if host.endswith("substack.com"):
        return "substack"
    if host.endswith("fathom.video"):
        return "fathom"
    return "web"
