"""Generic URL fetcher using trafilatura for readable extraction."""

from __future__ import annotations

import re

import trafilatura

from . import FetchResult


def fetch(url: str) -> FetchResult:
    downloaded = trafilatura.fetch_url(url)
    if not downloaded:
        raise RuntimeError(f"web.fetch: could not download {url}")

    markdown = trafilatura.extract(
        downloaded,
        output_format="markdown",
        include_links=True,
        include_images=False,
        with_metadata=False,
    )
    if not markdown:
        raise RuntimeError(f"web.fetch: extraction returned empty for {url}")

    meta = trafilatura.extract_metadata(downloaded)
    title = (meta.title if meta and meta.title else url).strip()
    created = meta.date if meta and getattr(meta, "date", None) else None

    links = re.findall(r"\((https?://[^\s)]+)\)", markdown)

    return FetchResult(
        title=title,
        markdown=markdown,
        source_url=url,
        default_type="web",
        created_date=created,
        links=list(dict.fromkeys(links)),
    )
