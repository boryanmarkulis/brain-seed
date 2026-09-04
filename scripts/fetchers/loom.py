"""Loom transcript fetcher.

Loom embeds the transcript in a JSON blob inside the share page HTML. We
fetch the page, find the __NEXT_DATA__ or transcript payload, and extract
the text.

Auth: private/workspace videos require a logged-in session. Drop the raw
Cookie header value (e.g. "loom_sess=...; connect.sid=...") into
~/.config/brain/loom_cookie and we'll send it on every request.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from . import FetchResult


COOKIE_FILE = Path(os.path.expanduser("~/.config/brain/loom_cookie"))


def _headers() -> dict[str, str]:
    h = {"User-Agent": "Mozilla/5.0"}
    if COOKIE_FILE.exists():
        cookie = COOKIE_FILE.read_text().strip()
        if cookie:
            h["Cookie"] = cookie
    return h


def _video_id(url: str) -> str:
    path = urlparse(url).path
    m = re.search(r"/share/([a-f0-9]{32}|[a-zA-Z0-9]{20,})", path)
    if not m:
        raise ValueError(f"loom.fetch: cannot parse video id from {url}")
    return m.group(1)


def _canonical_url(vid: str) -> str:
    return f"https://www.loom.com/share/{vid}"


def _transcript_via_api(vid: str) -> list[str] | None:
    """Try Loom's public transcript endpoint."""
    try:
        r = requests.post(
            f"https://www.loom.com/api/campaigns/sessions/{vid}/fetch-transcript",
            headers=_headers(),
            timeout=15,
        )
        if r.ok:
            data = r.json()
            segs = data.get("transcripts") or data.get("segments") or []
            texts = [s.get("text", "").strip() for s in segs if s.get("text")]
            if texts:
                return texts
    except Exception:
        pass
    return None


def _transcript_via_html(url: str) -> tuple[str, list[str]] | None:
    r = requests.get(url, timeout=30, headers=_headers())
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    title = None
    if soup.title:
        title = soup.title.get_text(strip=True)
    og = soup.find("meta", property="og:title")
    if og and og.get("content"):
        title = og["content"]

    cdn = _signed_transcript_url(r.text)
    if cdn:
        try:
            tr = requests.get(cdn, timeout=30)
            tr.raise_for_status()
            data = tr.json()
            phrases = data.get("phrases", []) if isinstance(data, dict) else []
            texts = [p.get("value", "").strip() for p in phrases if p.get("value")]
            if texts:
                return title or url, texts
        except Exception:
            pass

    next_data = soup.find("script", id="__NEXT_DATA__")
    if next_data and next_data.string:
        try:
            payload = json.loads(next_data.string)
        except Exception:
            payload = None
        if payload:
            texts = _walk_for_transcript(payload)
            if texts:
                return title or url, texts

    return (title or url, []) if title else None


def _signed_transcript_url(html: str) -> str | None:
    m = re.search(r'(https://cdn\.loom\.com/mediametadata/transcription/[^"\\]+)', html)
    return m.group(1) if m else None


def _walk_for_transcript(obj) -> list[str]:
    """Depth-first walk hunting for a 'transcript' or 'captions' list of segments."""
    out: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ("transcript", "transcripts", "captions", "segments") and isinstance(v, list):
                for seg in v:
                    if isinstance(seg, dict):
                        text = seg.get("text") or seg.get("content")
                        if text:
                            out.append(text.strip())
            else:
                out.extend(_walk_for_transcript(v))
    elif isinstance(obj, list):
        for item in obj:
            out.extend(_walk_for_transcript(item))
    return out


def fetch(url: str) -> FetchResult:
    vid = _video_id(url)

    texts = _transcript_via_api(vid)
    title = url

    if not texts:
        html_result = _transcript_via_html(url)
        if html_result is None:
            raise RuntimeError(f"loom.fetch: could not load {url}")
        title, texts = html_result

    if not texts:
        raise RuntimeError(
            f"loom.fetch: no transcript found for {url}. "
            "The video may be private or transcripts disabled."
        )

    body = "\n".join(texts)
    markdown = f"# {title}\n\n{body}\n"

    return FetchResult(
        title=title,
        markdown=markdown,
        source_url=_canonical_url(vid),
        default_type="loom",
        created_date=None,
        links=[],
    )
