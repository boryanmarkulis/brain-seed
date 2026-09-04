#!/usr/bin/env python3
"""Semantic search over the wiki. The shared retrieval helper (plan Phase 2).

Any skill can call this instead of loading wiki/index.md, which is 78 KB and
roughly 20,000 tokens for what is only a table of contents.

    from wiki_search import search
    hits = search("how do I qualify a new lead", k=6)
    for h in hits:
        print(h["score"], h["path"], h["heading"])

CLI:

    python3 scripts/wiki_search.py "how should I write a cold outreach DM"
    python3 scripts/wiki_search.py --pages "lead qualification"

Returns section-level hits, so the caller can read the relevant paragraph
instead of a whole page. `--pages` collapses to best-section-per-page.

The embedding server is started on demand and left running, because the common
case is several queries in a row. Call stop() when done, or ignore it: it costs
about 1.2 GB and `llm_local.stop_server(port=8081)` frees it.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import llm_local  # noqa: E402
import wiki_embed  # noqa: E402

WIKI = REPO / "wiki"

# Qwen3-Embedding is instruction-tuned: queries take a task prefix, documents do
# not. Skipping this costs real accuracy, it is not decoration.
import brain_config  # noqa: E402

TASK = (
    f"Given a question about {brain_config.cfg.owner}'s accumulated knowledge, "
    "retrieve the wiki section that answers it"
)

_cache: dict = {}


def _load():
    if "vecs" in _cache:
        return _cache["vecs"], _cache["meta"]
    if not (wiki_embed.VECS.exists() and wiki_embed.META.exists()):
        raise SystemExit("no embedding index. Run: python3 scripts/wiki_embed.py")
    vecs = np.load(wiki_embed.VECS)
    meta = json.loads(wiki_embed.META.read_text())
    if meta.get("fingerprint") != wiki_embed.fingerprint():
        raise SystemExit(
            f"index fingerprint {meta.get('fingerprint')} != {wiki_embed.fingerprint()}. "
            "Run: python3 scripts/wiki_embed.py --rebuild"
        )
    _cache["vecs"], _cache["meta"] = vecs, meta
    return vecs, meta


def embed_query(text: str) -> np.ndarray:
    llm_local.ensure_server(
        wiki_embed.MODEL, port=wiki_embed.PORT,
        extra_args=["--embedding", "--pooling", "last"], log=lambda *a: None,
    )
    return wiki_embed.embed_batch([f"Instruct: {TASK}\nQuery: {text}"])[0]


def _snippet(path: str, heading: str, n: int = 240) -> str:
    p = WIKI / path
    if not p.exists():
        return ""
    text = p.read_text(errors="replace")
    if heading:
        i = text.find(heading)
        if i != -1:
            text = text[i:]
    body = " ".join(text.split())
    return body[:n]


def search(query: str, k: int = 8, pages: bool = False) -> list[dict]:
    """Top-k wiki sections for a natural-language query, best first."""
    vecs, meta = _load()
    q = embed_query(query)
    scores = vecs @ q  # both sides are L2-normalised, so this is cosine
    order = np.argsort(-scores)

    out, seen = [], set()
    for i in order:
        c = meta["chunks"][int(i)]
        if pages:
            if c["path"] in seen:
                continue
            seen.add(c["path"])
        out.append({
            "score": round(float(scores[int(i)]), 4),
            "path": c["path"], "slug": c["slug"], "heading": c["heading"],
            "snippet": _snippet(c["path"], c["heading"]),
        })
        if len(out) >= k:
            break
    return out


def stop() -> None:
    llm_local.stop_server(port=wiki_embed.PORT, log=lambda *a: None)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("query", nargs="+")
    ap.add_argument("-k", type=int, default=8)
    ap.add_argument("--pages", action="store_true", help="one hit per page")
    ap.add_argument("--stop", action="store_true", help="shut the embed server down after")
    args = ap.parse_args()

    for h in search(" ".join(args.query), k=args.k, pages=args.pages):
        where = f"{h['path']}" + (f"  ## {h['heading']}" if h["heading"] else "")
        print(f"{h['score']:.3f}  {where}")
        print(f"        {h['snippet'][:200]}")
    if args.stop:
        stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
