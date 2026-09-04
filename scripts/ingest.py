#!/usr/bin/env python3
"""
ingest.py - save a raw source into sources/<type>/<slug>.md.

Called by the /ingest skill after it has fetched content (via Notion MCP,
WebFetch, or local read) and written it to a temp file or piped it in.

Wiki/ pages are not produced here. `scripts/compile.py` owns the wiki -
it reads sources/ and daily/ and maintains concept pages over time.

Usage:
  ingest.py --type journal --slug 2026-03-15-pricing-notes \\
            --source-url https://www.notion.so/... --raw <path>
  cat page.md | ingest.py --type journal --slug my-slug --stdin

Flags:
  --type         required. One of: journal, ecom, loom, gdocs, web, inbox.
  --slug         required. Filename (no .md). Keep short and kebab-case.
  --raw <path>   path to the already-fetched raw content file.
  --stdin        read raw content from stdin instead of --raw.
  --source-url   original URL; written into the sync header.
  --force        overwrite if sources/<type>/<slug>.md already exists.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

MAX_CHARS = 100_000
# Folder names under sources/. Add your own; the only rule is that a type maps
# to exactly one subfolder, so provenance stays obvious from the path alone.
VALID_TYPES = {
    "journal", "web", "inbox", "notes", "book", "course", "call",
    "loom", "youtube", "gdocs", "notion", "substack", "fathom",
}


def log_event(repo_root: Path, msg: str) -> None:
    try:
        today = dt.date.today().isoformat()
        with (repo_root / "log.md").open("a") as f:
            f.write(f"[{today}] {msg}\n")
    except Exception:
        pass


def write_source(
    repo_root: Path,
    src_type: str,
    slug: str,
    content: str,
    source_url: str | None,
    force: bool,
) -> Path:
    target = repo_root / "sources" / src_type / f"{slug}.md"
    if target.exists() and not force:
        raise FileExistsError(f"{target.relative_to(repo_root)} already exists (use --force to overwrite)")
    target.parent.mkdir(parents=True, exist_ok=True)

    today = dt.date.today().isoformat()
    header = [f"<!-- Ingested {today} -->"]
    if source_url:
        header.append(f"<!-- Source: {source_url} -->")
    header.append("")
    target.write_text("\n".join(header) + "\n" + content.rstrip() + "\n")
    return target


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--type",
        required=True,
        help=(
            "Source type. Top-level segment must be one of: "
            + ", ".join(sorted(VALID_TYPES))
            + ". May include a nested subpath, e.g. 'notion/action-log'."
        ),
    )
    p.add_argument("--slug", required=True)
    p.add_argument("--raw", type=Path)
    p.add_argument("--stdin", action="store_true")
    p.add_argument("--source-url", default=None)
    p.add_argument("--force", action="store_true")
    args = p.parse_args()

    repo_root = Path(__file__).resolve().parent.parent

    root_type = args.type.split("/", 1)[0]
    if root_type not in VALID_TYPES:
        print(
            f"ingest.py: invalid --type root '{root_type}'. "
            f"Must be one of: {', '.join(sorted(VALID_TYPES))}",
            file=sys.stderr,
        )
        sys.exit(2)

    if args.stdin:
        content = sys.stdin.read()
    elif args.raw:
        content = args.raw.read_text(errors="replace")
    else:
        print("ingest.py: need --raw <path> or --stdin", file=sys.stderr)
        sys.exit(2)

    if len(content.strip()) < 50:
        print("ingest.py: content too short to ingest", file=sys.stderr)
        sys.exit(2)

    if len(content) > MAX_CHARS:
        content = content[:MAX_CHARS]

    try:
        source_path = write_source(
            repo_root, args.type, args.slug, content, args.source_url, args.force
        )
    except FileExistsError as exc:
        print(f"ingest.py: {exc}", file=sys.stderr)
        sys.exit(1)

    log_event(repo_root, f"INGEST OK: {args.type}/{args.slug} → {source_path.relative_to(repo_root)}")
    print(str(source_path.relative_to(repo_root)))


if __name__ == "__main__":
    main()
