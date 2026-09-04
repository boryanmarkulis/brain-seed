"""Substack fetcher.

Handles:
  - single post URL → one FetchResult
  - publication root URL (e.g. https://example.substack.com) → FetchBatch of all posts
"""

from __future__ import annotations

import os
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import requests
from markdownify import markdownify

from . import FetchBatch, FetchResult


_HEADERS = {"User-Agent": "Mozilla/5.0 (BrainPull)"}

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SUBSTACKRC = Path.home() / ".substackrc"


def _load_substackrc() -> None:
    """Load SUBSTACK_* env vars from ~/.substackrc if present."""
    if not _SUBSTACKRC.exists():
        return
    for line in _SUBSTACKRC.read_text().splitlines():
        line = line.strip()
        if line.startswith("export "):
            line = line[7:]
        if "=" in line and not line.startswith("#"):
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"'))


def _get_authed_client():
    """Return an authenticated SubstackClient, or None if unauthed."""
    _load_substackrc()
    if not os.environ.get("SUBSTACK_SID") or not os.environ.get("SUBSTACK_PUBLICATION"):
        return None
    mcp_path = _REPO_ROOT / "mcp" / "substack"
    if str(mcp_path) not in sys.path:
        sys.path.insert(0, str(mcp_path))
    try:
        from client import SubstackClient  # type: ignore
        return SubstackClient()
    except Exception as exc:
        print(f"substack: auth unavailable ({exc}); continuing without", file=sys.stderr)
        return None


def _stats_map(client=None) -> dict[int, dict]:
    """Return {post_id: {sent, opens, open_rate}} for every post. Substack caps each call at 10 rows, so paginate."""
    client = client or _get_authed_client()
    if client is None:
        return {}
    out: dict[int, dict] = {}
    offset = 0
    try:
        while True:
            resp = client.session.get(
                f"{client.base_url}/publication/stats/email_stats",
                params={"offset": offset},
            )
            resp.raise_for_status()
            body = resp.json()
            rows = body.get("rows", [])
            if not rows:
                break
            for r in rows:
                pid = r.get("post_id")
                if pid is None or pid in out:
                    continue
                open_rate = r.get("open_rate") or 0
                out[pid] = {
                    "sent": r.get("sent") or 0,
                    "opens": r.get("opened") or 0,
                    "open_rate": round(open_rate * 100, 1),
                }
            total = body.get("total")
            offset += len(rows)
            if total is not None and offset >= total:
                break
            if len(rows) < 10:
                break
    except Exception as exc:
        print(f"substack: stats pagination stopped ({exc})", file=sys.stderr)
    return out


def _publication(url: str) -> str:
    """Return the https://<sub>.substack.com base for any substack URL."""
    u = urlparse(url)
    return f"https://{u.hostname}"


def _is_post_url(url: str) -> bool:
    return "/p/" in urlparse(url).path


def _post_to_result(post: dict, pub_base: str, stats: dict | None = None) -> FetchResult:
    title = post.get("title") or "Untitled"
    slug = post.get("slug") or ""
    post_url = post.get("canonical_url") or f"{pub_base}/p/{slug}"
    body_html = post.get("body_html") or ""
    subtitle = post.get("subtitle") or ""

    body_md = markdownify(body_html, heading_style="ATX").strip()
    parts = [f"# {title}"]
    if subtitle:
        parts.append(f"*{subtitle}*")
    if stats:
        parts.append(
            "## Stats\n"
            f"- subs_at_send: {stats.get('sent', 0)}\n"
            f"- opens: {stats.get('opens', 0)}\n"
            f"- open_rate: {stats.get('open_rate', 0)}%"
        )
    parts.append(body_md)
    markdown = "\n\n".join(parts) + "\n"

    post_date = post.get("post_date") or ""
    created = post_date[:10] if post_date else None

    return FetchResult(
        title=title,
        markdown=markdown,
        source_url=post_url,
        default_type="substack",
        created_date=created,
        links=re.findall(r"\((https?://[^\s)]+)\)", markdown),
    )


def _fetch_post(url: str) -> FetchResult:
    pub_base = _publication(url)
    slug = urlparse(url).path.rstrip("/").split("/")[-1]
    api = f"{pub_base}/api/v1/posts/{slug}"
    r = requests.get(api, headers=_HEADERS, timeout=30)
    r.raise_for_status()
    post = r.json()
    stats = _stats_map().get(post.get("id"))
    return _post_to_result(post, pub_base, stats)


def _fetch_archive(pub_url: str) -> FetchBatch:
    pub_base = _publication(pub_url)
    client = _get_authed_client()

    def _list(offset: int, limit: int) -> list[dict]:
        if client is not None:
            r = client.session.get(
                f"{client.base_url}/archive",
                params={"sort": "new", "limit": limit, "offset": offset},
            )
        else:
            r = requests.get(
                f"{pub_base}/api/v1/archive",
                params={"sort": "new", "limit": limit, "offset": offset},
                headers=_HEADERS,
                timeout=30,
            )
        r.raise_for_status()
        return r.json()

    authed_base = client.base_url if client is not None else None
    authed_cookies = {"connect.sid": os.environ["SUBSTACK_SID"]} if client is not None else None

    def _fetch_full(slug: str) -> dict:
        import time
        last_exc: Exception | None = None
        if authed_base is not None:
            url = f"{authed_base}/posts/{slug}"
            cookies = authed_cookies
        else:
            url = f"{pub_base}/api/v1/posts/{slug}"
            cookies = None
        for attempt in range(6):
            try:
                r = requests.get(url, headers=_HEADERS, cookies=cookies, timeout=60)
                if r.status_code == 429 or r.status_code >= 500:
                    last_exc = RuntimeError(f"HTTP {r.status_code}: {r.text[:120]}")
                    time.sleep((2 ** attempt) + 0.5)
                    continue
                r.raise_for_status()
                return r.json()
            except requests.exceptions.RequestException as exc:
                last_exc = exc
                time.sleep((2 ** attempt) + 0.5)
        raise last_exc or RuntimeError(f"failed to fetch {slug}")

    posts: list[dict] = []
    seen_ids: set[int] = set()
    offset = 0
    limit = 50
    while True:
        batch = _list(offset, limit)
        if not batch:
            break
        new = [p for p in batch if p.get("id") not in seen_ids]
        for p in new:
            seen_ids.add(p.get("id"))
        posts.extend(new)
        # Advance by the batch size actually returned. Stop only when Substack returns nothing new.
        offset += max(len(batch), 1)
        if not new and len(batch) < limit:
            break

    stats_by_id = _stats_map(client)

    from concurrent.futures import ThreadPoolExecutor, as_completed

    slugs = [s.get("slug") for s in posts if s.get("slug")]
    results: list[FetchResult] = []
    failed: list[str] = []

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(_fetch_full, slug): slug for slug in slugs}
        for fut in as_completed(futures):
            slug = futures[fut]
            try:
                full = fut.result()
                results.append(_post_to_result(full, pub_base, stats_by_id.get(full.get("id"))))
            except Exception as exc:
                failed.append(slug)
                print(f"substack: failed to fetch {slug}: {exc}", file=sys.stderr)

    print(
        f"substack: archive has {len(posts)} posts, fetched {len(results)}, "
        f"failed {len(failed)}",
        file=sys.stderr,
    )
    return FetchBatch(results=results, source_url=pub_base)


def fetch(url: str):
    if _is_post_url(url):
        return _fetch_post(url)
    return _fetch_archive(url)
