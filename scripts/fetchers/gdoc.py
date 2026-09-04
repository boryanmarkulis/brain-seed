"""Google Doc fetcher - converts Docs API JSON to markdown, extracts hyperlinks."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from . import FetchResult
from ._google_auth import docs_service


def _doc_id(url: str) -> str:
    m = re.search(r"/document/d/([a-zA-Z0-9_-]+)", urlparse(url).path)
    if not m:
        raise ValueError(f"gdoc.fetch: cannot parse doc id from {url}")
    return m.group(1)


def _render_elements(elements: list) -> tuple[str, list[str]]:
    out: list[str] = []
    links: list[str] = []
    for el in elements:
        tr = el.get("textRun")
        if not tr:
            continue
        text = tr.get("content", "")
        style = tr.get("textStyle", {}) or {}
        link = (style.get("link") or {}).get("url")
        bold = style.get("bold")
        italic = style.get("italic")

        rendered = text
        if bold and text.strip():
            rendered = f"**{text.rstrip()}**" + text[len(text.rstrip()):]
        if italic and text.strip():
            rendered = f"*{rendered.rstrip()}*" + rendered[len(rendered.rstrip()):]
        if link:
            rendered = f"[{text.rstrip()}]({link})" + text[len(text.rstrip()):]
            links.append(link)
        out.append(rendered)
    return "".join(out), links


def _render_paragraph(para: dict) -> tuple[str, list[str]]:
    style = para.get("paragraphStyle", {}) or {}
    named = style.get("namedStyleType", "")
    text, links = _render_elements(para.get("elements", []))
    text = text.rstrip("\n")

    if named.startswith("HEADING_"):
        level = int(named.split("_")[1]) if named.split("_")[1].isdigit() else 2
        level = max(1, min(level, 6))
        return "#" * level + " " + text, links

    bullet = para.get("bullet")
    if bullet:
        return "- " + text, links

    return text, links


def _render_table(table: dict) -> tuple[str, list[str]]:
    all_links: list[str] = []
    rows_md: list[str] = []
    for row in table.get("tableRows", []):
        cells_md = []
        for cell in row.get("tableCells", []):
            parts = []
            for el in cell.get("content", []):
                para = el.get("paragraph")
                if para:
                    t, l = _render_paragraph(para)
                    parts.append(t)
                    all_links.extend(l)
            cells_md.append(" ".join(p for p in parts if p).replace("|", "\\|"))
        rows_md.append("| " + " | ".join(cells_md) + " |")
    if rows_md:
        sep = "| " + " | ".join(["---"] * len(rows_md[0].split("|")[1:-1])) + " |"
        rows_md.insert(1, sep)
    return "\n".join(rows_md), all_links


def fetch(url: str) -> FetchResult:
    doc_id = _doc_id(url)
    doc = docs_service().documents().get(documentId=doc_id).execute()

    title = doc.get("title", "Untitled")
    body = doc.get("body", {}).get("content", []) or []

    blocks: list[str] = []
    all_links: list[str] = []
    for el in body:
        if "paragraph" in el:
            t, links = _render_paragraph(el["paragraph"])
            if t.strip():
                blocks.append(t)
            all_links.extend(links)
        elif "table" in el:
            t, links = _render_table(el["table"])
            if t.strip():
                blocks.append(t)
            all_links.extend(links)

    markdown = f"# {title}\n\n" + "\n\n".join(blocks) + "\n"

    return FetchResult(
        title=title,
        markdown=markdown,
        source_url=url,
        default_type="gdocs",
        created_date=None,
        links=list(dict.fromkeys(all_links)),
    )
