"""Google Sheets fetcher - renders each tab as a markdown table."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from . import FetchResult
from ._google_auth import sheets_service


def _sheet_id(url: str) -> str:
    m = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", urlparse(url).path)
    if not m:
        raise ValueError(f"gsheet.fetch: cannot parse sheet id from {url}")
    return m.group(1)


def _trim(rows: list[list[str]]) -> list[list[str]]:
    rows = [[(c if c is not None else "") for c in r] for r in rows]
    while rows and all((c == "" for c in rows[-1])):
        rows.pop()
    if not rows:
        return rows
    width = max(len(r) for r in rows)
    while width > 0 and all((len(r) < width or r[width - 1] == "") for r in rows):
        width -= 1
    return [r[:width] + [""] * (width - len(r)) for r in rows]


def _render_table(rows: list[list[str]]) -> str:
    rows = _trim(rows)
    if not rows:
        return "_(empty)_"
    width = len(rows[0])
    if width == 0:
        return "_(empty)_"
    header = rows[0]
    body = rows[1:] if len(rows) > 1 else []

    def esc(c: str) -> str:
        return str(c).replace("|", "\\|").replace("\n", " ").strip()

    lines = ["| " + " | ".join(esc(c) for c in header) + " |"]
    lines.append("| " + " | ".join(["---"] * width) + " |")
    for r in body:
        lines.append("| " + " | ".join(esc(c) for c in r) + " |")
    return "\n".join(lines)


def fetch(url: str) -> FetchResult:
    sid = _sheet_id(url)
    svc = sheets_service()
    meta = svc.spreadsheets().get(spreadsheetId=sid, includeGridData=False).execute()

    title = meta.get("properties", {}).get("title", "Untitled")
    sheets = meta.get("sheets", [])
    tab_titles = [s.get("properties", {}).get("title", "Sheet") for s in sheets]

    blocks: list[str] = [f"# {title}"]
    for tab in tab_titles:
        try:
            resp = svc.spreadsheets().values().get(
                spreadsheetId=sid,
                range=f"'{tab}'",
                valueRenderOption="FORMATTED_VALUE",
            ).execute()
            rows = resp.get("values", []) or []
        except Exception as exc:
            blocks.append(f"## {tab}\n\n_(error reading tab: {exc})_")
            continue
        blocks.append(f"## {tab}\n\n{_render_table(rows)}")

    markdown = "\n\n".join(blocks) + "\n"

    return FetchResult(
        title=title,
        markdown=markdown,
        source_url=url,
        default_type="gdocs",
        created_date=None,
        links=[],
    )
