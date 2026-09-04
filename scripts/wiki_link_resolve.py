#!/usr/bin/env python3
"""Resolve broken wikilinks semantically, using the embedding index (Phase 2).

The plan is explicit that string similarity must not do this job:
`ad-optimization` matches `ai-optimization` at 0.93 and is the wrong page.
So the query is built from the broken slug AND the sentence that referenced it,
and the match is made against section embeddings.

Two guards keep it honest:

  --min-score   absolute floor on cosine similarity
  --min-margin  the winner must beat the runner-up page by this much, so a
                genuinely ambiguous target is left alone rather than guessed

Anything that fails either guard is reported as UNRESOLVED and not touched.

    python3 scripts/wiki_link_resolve.py --dry-run
    python3 scripts/wiki_link_resolve.py --apply
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import wiki_search  # noqa: E402

WIKI = REPO / "wiki"
LINK = re.compile(r"\[\[([^\]|]+?)(\|[^\]]*)?\]\]")


def context_for(text: str, target: str, width: int = 300) -> str:
    """The sentence around the reference, so the query carries real meaning."""
    i = text.find(f"[[{target}")
    if i == -1:
        return ""
    start, end = max(0, i - width), min(len(text), i + width)
    snippet = text[start:end]
    snippet = LINK.sub(lambda m: m.group(1).replace("-", " "), snippet)
    return " ".join(snippet.split())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-score", type=float, default=0.72)
    ap.add_argument("--min-margin", type=float, default=0.04)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if not args.apply:
        args.dry_run = True

    pages = {p.stem: p for p in WIKI.rglob("*.md") if p.name != "index.md"}
    slugs = set(pages)

    # broken target -> {referring page stem: text}
    refs: dict[str, dict[str, str]] = defaultdict(dict)
    for stem, p in pages.items():
        text = p.read_text(errors="replace")
        for m in LINK.finditer(text):
            t = m.group(1).strip()
            if t not in slugs:
                refs[t][stem] = text

    targets = sorted(refs, key=lambda t: -len(refs[t]))
    if args.limit:
        targets = targets[: args.limit]
    print(f"{len(targets)} broken targets to resolve\n")

    vecs, meta = wiki_search._load()
    chunk_page = [c["slug"] for c in meta["chunks"]]

    resolved: dict[str, str] = {}
    unresolved: list[tuple[str, str, float, float]] = []

    for t in targets:
        ctx = ""
        for stem, text in list(refs[t].items())[:2]:
            ctx += " " + context_for(text, t)
        query = f"{t.replace('-', ' ')}. {ctx.strip()}"
        q = wiki_search.embed_query(query)
        scores = vecs @ q

        # Collapse sections to their best-scoring page, then compare pages.
        best: dict[str, float] = {}
        for i, s in enumerate(scores):
            pg = chunk_page[i]
            if s > best.get(pg, -1):
                best[pg] = float(s)
        ranked = sorted(best.items(), key=lambda x: -x[1])
        if not ranked:
            continue
        top, top_s = ranked[0]
        second_s = ranked[1][1] if len(ranked) > 1 else 0.0
        margin = top_s - second_s

        if top_s >= args.min_score and margin >= args.min_margin:
            resolved[t] = top
            print(f"  RESOLVE  {t}  ->  {top}   ({top_s:.3f}, margin {margin:.3f})")
        else:
            unresolved.append((t, top, top_s, margin))

    print(f"\nresolved {len(resolved)}, left alone {len(unresolved)}")
    if unresolved[:10]:
        print("closest calls left alone (score/margin below the guard):")
        for t, top, s, m in sorted(unresolved, key=lambda x: -x[2])[:10]:
            print(f"  {t}  ~  {top}  ({s:.3f}, margin {m:.3f})")

    if args.apply and resolved:
        rewrites = 0
        for p in WIKI.rglob("*.md"):
            text = p.read_text(errors="replace")

            def sub(m: re.Match) -> str:
                nonlocal rewrites
                t, alias = m.group(1).strip(), (m.group(2) or "")
                if t in resolved:
                    rewrites += 1
                    return f"[[{resolved[t]}{alias}]]"
                return m.group(0)

            new = LINK.sub(sub, text)
            if new != text:
                p.write_text(new)
        print(f"\napplied: {rewrites} links rewritten")
    elif args.dry_run:
        print("\nDRY RUN, nothing written")

    wiki_search.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
