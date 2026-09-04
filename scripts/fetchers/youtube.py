"""YouTube transcript fetcher."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

import requests
from youtube_transcript_api import YouTubeTranscriptApi

from . import FetchResult


def _video_id(url: str) -> str:
    u = urlparse(url)
    if u.hostname in ("youtu.be",):
        return u.path.lstrip("/")
    if u.hostname and "youtube.com" in u.hostname:
        qs = parse_qs(u.query)
        if "v" in qs:
            return qs["v"][0]
        m = re.search(r"/(?:embed|shorts|v)/([^/?&]+)", u.path)
        if m:
            return m.group(1)
    raise ValueError(f"youtube.fetch: cannot parse video id from {url}")


def _title(video_id: str) -> str:
    try:
        r = requests.get(
            "https://www.youtube.com/oembed",
            params={"url": f"https://www.youtube.com/watch?v={video_id}", "format": "json"},
            timeout=15,
        )
        r.raise_for_status()
        return r.json().get("title") or video_id
    except Exception:
        return video_id


def fetch(url: str) -> FetchResult:
    vid = _video_id(url)
    try:
        if hasattr(YouTubeTranscriptApi, "get_transcript"):
            transcript = YouTubeTranscriptApi.get_transcript(vid)
        else:
            # youtube-transcript-api >= 1.0 instance API
            fetched = YouTubeTranscriptApi().fetch(vid)
            transcript = [{"text": snippet.text} for snippet in fetched]
    except Exception as exc:
        raise RuntimeError(f"youtube.fetch: no transcript for {vid}: {exc}") from exc

    title = _title(vid)
    lines = [seg["text"].strip() for seg in transcript if seg.get("text")]
    body = "\n".join(lines)
    markdown = f"# {title}\n\n{body}\n"

    return FetchResult(
        title=title,
        markdown=markdown,
        source_url=url,
        default_type="youtube",
        created_date=None,
        links=[],
    )
