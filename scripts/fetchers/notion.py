"""Notion fetcher - single pages or whole databases.

Auth: NOTION_TOKEN env var or ~/.config/brain/notion_token.
Create an internal integration at https://www.notion.so/my-integrations
and share the target pages/DBs with it.

Handles nested structures: if a page contains a `child_database` or
`child_page` block, the fetcher recurses into it and yields those pages
as siblings in the same output batch. Media blocks (image, audio,
video, file, pdf) are rendered as `[media: <type> - <label>]`
placeholders; binaries are not downloaded.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from urllib.parse import urlparse

from notion_client import Client

from . import FetchBatch, FetchResult, slugify


TOKEN_PATH = Path.home() / ".config" / "brain" / "notion_token"

MEDIA_BLOCK_TYPES = {"image", "audio", "video", "file", "pdf"}


def _client() -> Client:
    token = os.environ.get("NOTION_TOKEN")
    if not token and TOKEN_PATH.exists():
        token = TOKEN_PATH.read_text().strip()
    if not token:
        raise RuntimeError(
            f"Notion token not found. Set NOTION_TOKEN env var or write the token "
            f"to {TOKEN_PATH}. Create an integration at notion.so/my-integrations "
            "and share target pages/DBs with it."
        )
    return Client(auth=token)


def _uuid_from_url(url: str) -> str:
    """Extract the 32-char UUID from a Notion URL (with or without dashes)."""
    path = urlparse(url).path
    m = re.search(r"([a-f0-9]{32})", path.replace("-", ""))
    if not m:
        raise ValueError(f"notion.fetch: cannot find page/db id in {url}")
    raw = m.group(1)
    return f"{raw[0:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:32]}"


def _rich_text(rt: list) -> str:
    parts = []
    for seg in rt or []:
        txt = seg.get("plain_text", "")
        ann = seg.get("annotations", {}) or {}
        href = seg.get("href")
        if ann.get("code"):
            txt = f"`{txt}`"
        if ann.get("bold"):
            txt = f"**{txt}**"
        if ann.get("italic"):
            txt = f"*{txt}*"
        if href:
            txt = f"[{txt}]({href})"
        parts.append(txt)
    return "".join(parts)


def _media_placeholder(block: dict, btype: str) -> str:
    data = block.get(btype, {}) or {}
    file_info = data.get("file") or data.get("external") or {}
    url = file_info.get("url", "") or ""
    filename = url.rsplit("/", 1)[-1].split("?")[0] if url else ""
    caption = _rich_text(data.get("caption", []))
    label = caption or filename or "untitled"
    return f"[media:{btype} - {label}]"


def _block_md(block: dict, depth: int = 0) -> str:
    btype = block.get("type")
    data = block.get(btype, {}) or {}
    indent = "  " * depth

    if btype in MEDIA_BLOCK_TYPES:
        return indent + _media_placeholder(block, btype)
    if btype == "paragraph":
        return indent + _rich_text(data.get("rich_text", []))
    if btype in ("heading_1", "heading_2", "heading_3"):
        level = int(btype.split("_")[1])
        return f"{'#' * level} {_rich_text(data.get('rich_text', []))}"
    if btype == "bulleted_list_item":
        return f"{indent}- {_rich_text(data.get('rich_text', []))}"
    if btype == "numbered_list_item":
        return f"{indent}1. {_rich_text(data.get('rich_text', []))}"
    if btype == "to_do":
        checked = "x" if data.get("checked") else " "
        return f"{indent}- [{checked}] {_rich_text(data.get('rich_text', []))}"
    if btype == "quote":
        return f"> {_rich_text(data.get('rich_text', []))}"
    if btype == "code":
        lang = data.get("language", "")
        return f"```{lang}\n{_rich_text(data.get('rich_text', []))}\n```"
    if btype == "divider":
        return "---"
    if btype == "callout":
        return f"> {_rich_text(data.get('rich_text', []))}"
    if btype == "toggle":
        return f"{indent}- {_rich_text(data.get('rich_text', []))}"
    if btype in ("bookmark", "embed", "link_preview"):
        url = data.get("url") or ""
        return f"[{url}]({url})"
    if btype == "child_page":
        return f"{indent}- (child page: {data.get('title', 'untitled')})"
    if btype == "child_database":
        return f"{indent}- (child database: {data.get('title', 'untitled')})"

    txt = _rich_text(data.get("rich_text", [])) if "rich_text" in data else ""
    return indent + txt if txt else ""


def _walk_children(
    client: Client,
    block_id: str,
    depth: int,
    out_lines: list[str],
    sub_pages: list[str],
    sub_dbs: list[str],
) -> None:
    cursor = None
    while True:
        resp = client.blocks.children.list(block_id=block_id, start_cursor=cursor)
        for b in resp.get("results", []):
            btype = b.get("type")
            md = _block_md(b, depth)
            if md.strip():
                out_lines.append(md)

            if btype == "child_page":
                sub_pages.append(b["id"])
            elif btype == "child_database":
                sub_dbs.append(b["id"])
            elif b.get("has_children") and btype not in ("child_page", "child_database"):
                _walk_children(client, b["id"], depth + 1, out_lines, sub_pages, sub_dbs)
        if not resp.get("has_more"):
            break
        cursor = resp.get("next_cursor")


def _page_title(page: dict) -> str:
    props = page.get("properties", {}) or {}
    for v in props.values():
        if v.get("type") == "title":
            return _rich_text(v.get("title", [])) or "Untitled"
    return "Untitled"


def _render_page(
    page: dict, client: Client, default_type: str
) -> tuple[FetchResult, list[str], list[str]]:
    """Render a single page. Returns (result, sub_page_ids, sub_db_ids)."""
    title = _page_title(page)
    url = page.get("url", "")
    created = (page.get("created_time") or "")[:10] or None

    body_parts: list[str] = []
    sub_pages: list[str] = []
    sub_dbs: list[str] = []
    _walk_children(client, page["id"], 0, body_parts, sub_pages, sub_dbs)

    markdown = f"# {title}\n\n" + "\n\n".join(body_parts) + "\n"
    links = re.findall(r"\((https?://[^\s)]+)\)", markdown)

    result = FetchResult(
        title=title,
        markdown=markdown,
        source_url=url,
        default_type=default_type,
        created_date=created,
        links=list(dict.fromkeys(links)),
    )
    return result, sub_pages, sub_dbs


def _database_title(client: Client, db_id: str) -> str:
    try:
        db = client.databases.retrieve(database_id=db_id)
        title_parts = db.get("title", []) or []
        text = "".join(t.get("plain_text", "") for t in title_parts)
        return text.strip() or "untitled-db"
    except Exception:
        return "untitled-db"


def _database_data_source_ids(client: Client, db_id: str) -> list[str] | None:
    """Return the data_source IDs for a database, or None if obj isn't a database."""
    try:
        db = client.databases.retrieve(database_id=db_id)
    except Exception:
        return None
    sources = db.get("data_sources") or []
    return [s["id"] for s in sources if s.get("id")]


def _query_data_source(client: Client, ds_id: str) -> list[dict]:
    pages: list[dict] = []
    cursor = None
    while True:
        resp = client.data_sources.query(data_source_id=ds_id, start_cursor=cursor)
        pages.extend(resp.get("results", []))
        if not resp.get("has_more"):
            break
        cursor = resp.get("next_cursor")
    return pages


def _drain_queue(
    client: Client,
    initial_pages: list[dict],
    initial_db_ids: list[str],
    default_type: str,
) -> list[FetchResult]:
    """BFS over pages + nested databases. Returns a flat list of results."""
    results: list[FetchResult] = []
    seen_pages: set[str] = set()
    seen_dbs: set[str] = set()

    page_queue: list[dict] = list(initial_pages)
    db_queue: list[str] = list(initial_db_ids)

    while page_queue or db_queue:
        while db_queue:
            db_id = db_queue.pop(0)
            if db_id in seen_dbs:
                continue
            seen_dbs.add(db_id)
            ds_ids = _database_data_source_ids(client, db_id) or []
            for ds_id in ds_ids:
                page_queue.extend(_query_data_source(client, ds_id))

        if not page_queue:
            break
        page = page_queue.pop(0)
        pid = page.get("id")
        if not pid or pid in seen_pages:
            continue
        seen_pages.add(pid)
        try:
            result, sub_pages, sub_dbs = _render_page(page, client, default_type)
        except Exception as exc:
            print(f"notion: failed to render page {pid}: {exc}")
            continue
        results.append(result)
        for sp_id in sub_pages:
            if sp_id not in seen_pages:
                try:
                    sub_page = client.pages.retrieve(page_id=sp_id)
                    page_queue.append(sub_page)
                except Exception as exc:
                    print(f"notion: failed to retrieve sub-page {sp_id}: {exc}")
        for sdb_id in sub_dbs:
            if sdb_id not in seen_dbs:
                db_queue.append(sdb_id)

    return results


def fetch(url: str):
    client = _client()
    obj_id = _uuid_from_url(url)

    ds_ids = _database_data_source_ids(client, obj_id)
    if ds_ids is not None:
        db_title = _database_title(client, obj_id)
        default_type = f"notion/{slugify(db_title)}"
        initial_pages: list[dict] = []
        for ds_id in ds_ids:
            initial_pages.extend(_query_data_source(client, ds_id))
        results = _drain_queue(client, initial_pages, [], default_type)
        return FetchBatch(results=results, source_url=url)

    page = client.pages.retrieve(page_id=obj_id)
    results = _drain_queue(client, [page], [], "notion/pages")
    if len(results) == 1:
        return results[0]
    return FetchBatch(results=results, source_url=url)
