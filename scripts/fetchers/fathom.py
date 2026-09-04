"""Fathom call recording fetcher.

Pulls a meeting's summary + transcript via Fathom's Public API
(developers.fathom.ai). The API has no share_url filter, so we page
through /meetings (newest first) until we find the matching share_url,
then fetch its summary and transcript by recording_id.

Auth: FATHOM_API_KEY in the Brain root .env (or env var directly).
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import requests

from . import FetchResult

BASE_URL = "https://api.fathom.ai/external/v1"
MAX_PAGES = 20

# Fathom falls back to a placeholder title (e.g. "Impromptu Google Meet
# Meeting") whenever the calendar event has no real name. Treat anything
# matching this as generic and derive a real title from the summary instead.
_GENERIC_TITLE_RE = re.compile(r"^(impromptu\s+)?(google meet|zoom|teams)?\s*meeting$", re.IGNORECASE)


def _derive_title(raw_title: str, summary_md: str, recording_id: int) -> str:
    """Turn a generic Fathom title into something that reflects the content."""
    if raw_title and not _GENERIC_TITLE_RE.match(raw_title.strip()):
        return raw_title

    match = re.search(r"##\s*Meeting Purpose\s*\n+(.+)", summary_md)
    if match:
        purpose_line = match.group(1).strip()
        # Strip markdown link syntax: [text](url) -> text
        purpose_line = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", purpose_line)
        purpose_line = purpose_line.strip().rstrip(".")
        if purpose_line:
            return purpose_line[:100]

    return raw_title or f"Fathom call {recording_id}"

_ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"
if _ENV_PATH.exists():
    for _line in _ENV_PATH.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip())


def _api_key() -> str:
    key = os.environ.get("FATHOM_API_KEY")
    if not key:
        raise RuntimeError(
            "Fathom API key not found. Set FATHOM_API_KEY in the Brain root .env "
            "(or as an env var). Create one at fathom.video (Settings > API)."
        )
    return key


def _headers() -> dict[str, str]:
    return {"X-Api-Key": _api_key()}


def _find_meeting(share_url: str) -> dict:
    cursor = None
    for _ in range(MAX_PAGES):
        params = {"include_summary": "false", "include_transcript": "false"}
        if cursor:
            params["cursor"] = cursor
        r = requests.get(f"{BASE_URL}/meetings", headers=_headers(), params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        for item in data.get("items", []):
            if item.get("share_url") == share_url or item.get("url") == share_url:
                return item
        cursor = data.get("next_cursor")
        if not cursor:
            break
    raise RuntimeError(f"fathom.fetch: no meeting found matching {share_url}")


def _summary_markdown(recording_id: int) -> str:
    r = requests.get(f"{BASE_URL}/recordings/{recording_id}/summary", headers=_headers(), timeout=30)
    r.raise_for_status()
    summary = r.json().get("summary") or {}
    return summary.get("markdown_formatted", "")


def _transcript_lines(recording_id: int) -> list[str]:
    r = requests.get(f"{BASE_URL}/recordings/{recording_id}/transcript", headers=_headers(), timeout=30)
    r.raise_for_status()
    segments = r.json().get("transcript", [])
    lines = []
    for seg in segments:
        speaker = (seg.get("speaker") or {}).get("display_name") or "Unknown"
        text = seg.get("text", "").strip()
        ts = seg.get("timestamp", "")
        if text:
            lines.append(f"**[{ts}] {speaker}:** {text}")
    return lines


def fetch(url: str) -> FetchResult:
    meeting = _find_meeting(url)
    recording_id = meeting["recording_id"]
    raw_title = meeting.get("meeting_title") or meeting.get("title") or f"Fathom call {recording_id}"
    created_at = meeting.get("created_at")
    created_date = created_at[:10] if created_at else None

    summary_md = _summary_markdown(recording_id)
    transcript_lines = _transcript_lines(recording_id)

    title = _derive_title(raw_title, summary_md, recording_id)

    parts = [f"# {title}\n"]
    if created_at:
        parts.append(f"_Recorded: {created_at}_\n")
    if summary_md:
        parts.append(summary_md.strip() + "\n")
    if transcript_lines:
        parts.append("## Transcript\n")
        parts.append("\n\n".join(transcript_lines) + "\n")

    markdown = "\n".join(parts)

    return FetchResult(
        title=title,
        markdown=markdown,
        source_url=meeting.get("share_url") or url,
        default_type="fathom",
        created_date=created_date,
        links=[],
    )
