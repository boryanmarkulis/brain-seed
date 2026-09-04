#!/usr/bin/env python3
"""
pull.py - universal ingestion dispatcher.

Detects the source type from a URL (or accepts --source explicitly),
invokes the right fetcher, and shells out to ingest.py to save each
result into sources/<type>/<slug>.md.

For gdoc / notion sources, follows discovered Loom/YouTube/gdoc links
by default (disable with --no-follow).

Usage:
  pull.py <url> [--type <type>] [--slug <slug>] [--no-follow]
                [--limit N] [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from fetchers import FetchBatch, FetchResult, route, slugify

REPO_ROOT = Path(__file__).resolve().parent.parent
INGEST_SCRIPT = Path(__file__).resolve().parent / "ingest.py"
FOLLOWABLE = {"loom", "youtube", "gdoc"}


def _load_fetcher(name: str):
    from importlib import import_module
    mod = import_module(f"fetchers.{name}")
    return mod.fetch


def _make_slug(result: FetchResult, override: str | None = None) -> str:
    if override:
        return override
    base = slugify(result.title)
    if result.created_date:
        return f"{result.created_date}-{base}"
    return base


MAX_SLUG_VARIANTS = 50


def _existing_path_for_url(src_type: str, source_url: str) -> Path | None:
    """Return the existing source file for this URL, if any.

    Ingested files carry a `<!-- Source: <url> -->` header. We grep the target
    dir for that exact marker so re-runs skip already-pulled entries instead
    of creating `-2`, `-3`, ... duplicates.
    """
    if not source_url:
        return None
    target_dir = REPO_ROOT / "sources" / src_type
    if not target_dir.exists():
        return None
    marker = f"<!-- Source: {source_url} -->"
    for path in target_dir.glob("*.md"):
        try:
            with path.open() as f:
                head = "".join(next(f, "") for _ in range(5))
        except OSError:
            continue
        if marker in head:
            return path
    return None


def _ingest(result: FetchResult, forced_type: str | None, parent_slug: str | None) -> dict:
    base_slug = _make_slug(result)
    src_type = forced_type or result.default_type
    source_url = result.source_url

    existing = _existing_path_for_url(src_type, source_url)
    if existing is not None:
        return {
            "status": "skipped",
            "slug": existing.stem,
            "type": src_type,
            "path": str(existing.relative_to(REPO_ROOT)),
            "reason": "source_url already ingested",
        }

    content = result.markdown
    if parent_slug:
        content = f"<!-- Linked from: {parent_slug} -->\n\n" + content

    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as tf:
        tf.write(content)
        tmp_path = tf.name

    try:
        for attempt in range(1, MAX_SLUG_VARIANTS + 1):
            slug = base_slug if attempt == 1 else f"{base_slug}-{attempt}"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(INGEST_SCRIPT),
                    "--type", src_type,
                    "--slug", slug,
                    "--raw", tmp_path,
                    "--source-url", source_url,
                ],
                capture_output=True,
                text=True,
            )
            if proc.returncode == 0:
                return {
                    "status": "ingested",
                    "slug": slug,
                    "type": src_type,
                    "path": proc.stdout.strip(),
                    "renamed_from": base_slug if attempt > 1 else None,
                }
            if "already exists" not in proc.stderr:
                return {"status": "error", "slug": slug, "type": src_type, "error": proc.stderr.strip()}
        return {
            "status": "error",
            "slug": base_slug,
            "type": src_type,
            "error": f"exhausted {MAX_SLUG_VARIANTS} slug variants; all collided",
        }
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def _follow_links(parent: FetchResult, parent_slug: str, summary: dict, seen: set[str], allowed: set[str] | None = None) -> None:
    followable = allowed if allowed is not None else FOLLOWABLE
    for link in parent.links:
        if link in seen:
            continue
        seen.add(link)
        kind = route(link)
        if kind not in followable:
            continue
        try:
            fetcher = _load_fetcher(kind)
            child = fetcher(link)
        except Exception as exc:
            summary["error"].append({"url": link, "error": str(exc)})
            continue
        if isinstance(child, FetchBatch):
            for r in child.results:
                res = _ingest(r, None, parent_slug)
                summary["ingested" if res["status"] == "ingested" else res["status"]].append(res)
        else:
            res = _ingest(child, None, parent_slug)
            summary["ingested" if res["status"] == "ingested" else res["status"]].append(res)


def _append_children_section(parent_path: Path, children: list[dict]) -> None:
    if not children:
        return
    abs_path = REPO_ROOT / parent_path
    if not abs_path.exists():
        return
    lines = ["", "## Linked sources", ""]
    for c in children:
        lines.append(f"- {c['type']}/{c['slug']}")
    with abs_path.open("a") as f:
        f.write("\n".join(lines) + "\n")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("url")
    p.add_argument("--type", dest="forced_type", default=None)
    p.add_argument("--slug", default=None)
    p.add_argument("--no-follow", action="store_true")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    kind = route(args.url)

    if args.dry_run and kind == "gdrive":
        from fetchers.gdrive import enumerate_titles
        try:
            titles = enumerate_titles(args.url)
        except Exception as exc:
            print(f"pull: enumerate failed: {exc}", file=sys.stderr)
            return 2
        print(json.dumps({
            "batch": True,
            "count": len(titles),
            "docs": sum(1 for t in titles if t["type"] == "doc"),
            "sheets": sum(1 for t in titles if t["type"] == "sheet"),
            "titles": [t["title"] for t in titles],
        }, indent=2))
        return 0

    try:
        fetcher = _load_fetcher(kind)
    except Exception as exc:
        print(f"pull: no fetcher for {args.url}: {exc}", file=sys.stderr)
        return 2

    try:
        result = fetcher(args.url)
    except Exception as exc:
        print(f"pull: fetch failed: {exc}", file=sys.stderr)
        return 2

    summary = {"ingested": [], "skipped": [], "error": []}
    seen: set[str] = {args.url}

    if isinstance(result, FetchBatch):
        batch = result.results
        if args.limit:
            batch = batch[: args.limit]
        if args.dry_run:
            print(json.dumps({
                "batch": True,
                "count": len(batch),
                "titles": [r.title for r in batch],
            }, indent=2))
            return 0
        for r in batch:
            res = _ingest(r, args.forced_type, None)
            summary["ingested" if res["status"] == "ingested" else res["status"]].append(res)
            if (
                not args.no_follow
                and res["status"] == "ingested"
                and r.links
                and kind in {"gdrive", "notion"}
            ):
                children_before = len(summary["ingested"])
                _follow_links(r, res["slug"], summary, seen, allowed={"loom", "youtube"})
                children = summary["ingested"][children_before:]
                if children and "path" in res:
                    _append_children_section(Path(res["path"]), children)
    else:
        if args.dry_run:
            print(json.dumps({
                "batch": False,
                "title": result.title,
                "type": args.forced_type or result.default_type,
                "slug_preview": _make_slug(result, args.slug),
                "links": result.links,
            }, indent=2))
            return 0

        if args.slug:
            saved_slug = args.slug
        else:
            saved_slug = _make_slug(result)

        # ingest parent
        parent_result = _ingest(
            FetchResult(
                title=result.title,
                markdown=result.markdown,
                source_url=result.source_url,
                default_type=args.forced_type or result.default_type,
                created_date=result.created_date,
                links=result.links,
            ),
            args.forced_type,
            None,
        )
        summary["ingested" if parent_result["status"] == "ingested" else parent_result["status"]].append(parent_result)

        if (
            not args.no_follow
            and parent_result["status"] == "ingested"
            and kind in {"gdoc", "notion"}
        ):
            children_before = len(summary["ingested"])
            _follow_links(result, parent_result["slug"], summary, seen)
            children = [c for c in summary["ingested"][children_before:]]
            if children and "path" in parent_result:
                _append_children_section(Path(parent_result["path"]), children)

    print(json.dumps({
        "ingested": len(summary["ingested"]),
        "skipped": len(summary["skipped"]),
        "errors": len(summary["error"]),
        "paths": [i["path"] for i in summary["ingested"] if "path" in i],
        "error_details": summary["error"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
