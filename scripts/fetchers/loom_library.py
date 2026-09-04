"""Loom library fetcher - paginates the authenticated user's full video list.

Uses the internal `recentUserVideos` GraphQL query (auth via cookie file
at ~/.config/brain/loom_cookie). Each video is then handed off to
loom.fetch to pull the transcript.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from . import FetchBatch
from . import loom as loom_fetcher


GRAPHQL_URL = "https://www.loom.com/graphql"
COOKIE_FILE = Path(os.path.expanduser("~/.config/brain/loom_cookie"))
PAGE_SIZE = 50

QUERY = """
query GetMostRecentVideoV2($startDate: String!, $endDate: String!, $offset: Int!, $limit: Int!) {
  recentUserVideos(startDate: $startDate, endDate: $endDate, offset: $offset, limit: $limit) {
    id
    name
    __typename
  }
}
"""


def _headers() -> dict[str, str]:
    if not COOKIE_FILE.exists():
        raise RuntimeError(
            f"Loom cookie not found at {COOKIE_FILE}. "
            "Sign into loom.com, copy your Cookie header value, save it there."
        )
    cookie = COOKIE_FILE.read_text().strip()
    return {
        "Content-Type": "application/json",
        "Accept": "*/*",
        "User-Agent": "Mozilla/5.0",
        "Cookie": cookie,
        "apollographql-client-name": "web",
        "apollographql-client-version": "545bde9",
        "x-loom-request-source": "loom_web_#73269",
        "Origin": "https://www.loom.com",
        "Referer": "https://www.loom.com/looms/videos",
    }


def _list_videos() -> list[dict]:
    end = datetime.now(timezone.utc) + timedelta(days=1)
    start = end - timedelta(days=365 * 5)
    end_iso = end.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    start_iso = start.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    h = _headers()

    out: list[dict] = []
    offset = 0
    while True:
        body = {
            "operationName": "GetMostRecentVideoV2",
            "variables": {
                "startDate": start_iso,
                "endDate": end_iso,
                "offset": offset,
                "limit": PAGE_SIZE,
            },
            "query": QUERY,
        }
        r = requests.post(GRAPHQL_URL, headers=h, json=body, timeout=30)
        r.raise_for_status()
        data = r.json()
        if "errors" in data:
            raise RuntimeError(f"loom_library: graphql errors: {data['errors']}")
        page = data.get("data", {}).get("recentUserVideos", []) or []
        if not page:
            break
        out.extend(page)
        print(f"loom_library: fetched {len(out)} videos so far")
        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return out


def _existing_video_ids() -> set[str]:
    """Scan sources/loom/ for canonical URL markers and return the set of video IDs already on disk."""
    import re
    repo_root = Path(__file__).resolve().parents[2]
    loom_dir = repo_root / "sources" / "loom"
    if not loom_dir.exists():
        return set()
    out: set[str] = set()
    for p in loom_dir.glob("*.md"):
        try:
            with p.open() as f:
                head = "".join(next(f, "") for _ in range(5))
        except OSError:
            continue
        m = re.search(r"loom\.com/share/([a-f0-9]{32})", head)
        if m:
            out.add(m.group(1))
    return out


def fetch(url: str) -> FetchBatch:
    videos = _list_videos()
    existing = _existing_video_ids()
    print(f"loom_library: total {len(videos)} videos, {len(existing)} already on disk")
    results = []
    skipped = 0
    for i, v in enumerate(videos, 1):
        vid = v.get("id")
        name = v.get("name") or vid
        if not vid:
            continue
        if vid in existing:
            skipped += 1
            continue
        share_url = f"https://www.loom.com/share/{vid}"
        try:
            r = loom_fetcher.fetch(share_url)
            results.append(r)
        except Exception as exc:
            print(f"loom_library [{i}/{len(videos)}]: failed {name} ({vid}): {exc}")
            continue
        if (i - skipped) % 25 == 0:
            print(f"loom_library: ingested {len(results)} new (skipped {skipped} dupes) at video {i}/{len(videos)}")
    print(f"loom_library: done. {len(results)} new, {skipped} pre-existing skipped")
    return FetchBatch(results=results, source_url=url)
