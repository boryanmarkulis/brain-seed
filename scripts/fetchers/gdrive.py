"""Google Drive folder fetcher - recursively enumerates Docs and Sheets.

Walks the folder tree depth-first, dispatches each Doc to gdoc.fetch and
each Sheet to gsheet.fetch. Skips Slides, videos, images, and other
binary mimetypes.

Each child FetchResult has its title prefixed with the relative folder
path (e.g. "ACME / OFFERS / Positioning Doc") so slugify produces
collision-resistant slugs across deeply nested trees.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from . import FetchBatch
from ._google_auth import drive_service
from . import gdoc as gdoc_fetcher
from . import gsheet as gsheet_fetcher


DOC_MT = "application/vnd.google-apps.document"
SHEET_MT = "application/vnd.google-apps.spreadsheet"
FOLDER_MT = "application/vnd.google-apps.folder"
TEXT_MTS = {DOC_MT, SHEET_MT}


def _folder_id(url: str) -> str:
    m = re.search(r"/folders/([a-zA-Z0-9_-]+)", urlparse(url).path)
    if not m:
        raise ValueError(f"gdrive.fetch: cannot parse folder id from {url}")
    return m.group(1)


def _walk(svc, folder_id: str, path: list[str]) -> list[tuple[list[str], dict]]:
    """Return [(folder_path_segments, file_metadata), ...] for all text files in the tree."""
    out: list[tuple[list[str], dict]] = []
    page_token = None
    while True:
        resp = svc.files().list(
            q=f"'{folder_id}' in parents and trashed=false",
            fields="nextPageToken, files(id, name, mimeType, webViewLink)",
            pageSize=200,
            pageToken=page_token,
        ).execute(num_retries=3)
        for f in resp.get("files", []):
            mt = f.get("mimeType", "")
            if mt == FOLDER_MT:
                out.extend(_walk(svc, f["id"], path + [f["name"]]))
            elif mt in TEXT_MTS:
                out.append((path, f))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return out


def enumerate_titles(url: str) -> list[dict]:
    """Lightweight enumeration for dry-run - no content fetch."""
    folder_id = _folder_id(url)
    svc = drive_service()
    entries = _walk(svc, folder_id, [])
    out = []
    for path_segments, f in entries:
        prefix = " / ".join(path_segments) if path_segments else ""
        title = f"{prefix} / {f['name']}" if prefix else f["name"]
        out.append({"title": title, "type": "doc" if f["mimeType"] == DOC_MT else "sheet"})
    return out


def _doc_link(f: dict) -> str:
    return f.get("webViewLink") or f"https://docs.google.com/document/d/{f['id']}"


def _sheet_link(f: dict) -> str:
    return f.get("webViewLink") or f"https://docs.google.com/spreadsheets/d/{f['id']}"


def fetch(url: str) -> FetchBatch:
    folder_id = _folder_id(url)
    svc = drive_service()
    entries = _walk(svc, folder_id, [])
    print(f"gdrive: walking {len(entries)} files")

    results = []
    for i, (path_segments, f) in enumerate(entries, 1):
        mt = f["mimeType"]
        name = f.get("name", "?")
        try:
            if mt == DOC_MT:
                r = gdoc_fetcher.fetch(_doc_link(f))
            elif mt == SHEET_MT:
                r = gsheet_fetcher.fetch(_sheet_link(f))
            else:
                continue
        except Exception as exc:
            print(f"gdrive [{i}/{len(entries)}]: failed {name} ({f.get('id')}): {exc}")
            continue

        if path_segments:
            prefix = " / ".join(path_segments)
            r.title = f"{prefix} / {r.title}"
            r.markdown = re.sub(r"^# .*\n", f"# {r.title}\n", r.markdown, count=1)
        results.append(r)
        if i % 25 == 0:
            print(f"gdrive: fetched {i}/{len(entries)}")

    return FetchBatch(results=results, source_url=url)
