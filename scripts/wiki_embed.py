#!/usr/bin/env python3
"""Section-level embedding index for the wiki (plan Phase 2).

Embeds each wiki page at SECTION granularity, not page granularity, so
retrieval returns the relevant paragraph instead of a whole page. Page-level
vectors reward long pages that mention everything, which is the exact failure
the lexical A/B test already showed.

Storage is two files next to the other pipeline state:

    .state/wiki-embeddings.npy    float32 [n_chunks, dims], L2-normalised
    .state/wiki-embeddings.json   aligned metadata + model fingerprint

Incremental by content hash: a chunk whose text is unchanged keeps its vector,
so a nightly refresh only pays for what actually moved. Changing the model or
the chunker invalidates everything, which the fingerprint detects.

    python3 scripts/wiki_embed.py --status
    python3 scripts/wiki_embed.py            # incremental
    python3 scripts/wiki_embed.py --rebuild  # from scratch
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.request
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import llm_local  # noqa: E402

WIKI = REPO / "wiki"
VECS = REPO / ".state" / "wiki-embeddings.npy"
META = REPO / ".state" / "wiki-embeddings.json"
# Hash -> vector cache, checkpointed during the run. The final matrix is
# assembled from it. Without this a crash at chunk 4,800 of 4,885 throws away
# the whole run, which is exactly what happened the first time.
CACHE = REPO / ".state" / "wiki-embed-cache.npz"

MODEL = "qwen3-embed-0.6b"

# llama-server forces n_batch down to n_ubatch when embeddings are on, and its
# default n_ubatch is 512. An embedding input is never split across ubatches,
# so ANY chunk longer than that kills the server mid-request and the client
# sees "Remote end closed connection without response". The wiki has 26 such
# sections (longest ~1,640 tokens), which is why the index silently stalled at
# 4,885 of 5,298 vectors. Raising both to 4096 covers the longest section with
# headroom; on a 0.6B model the extra memory is negligible.
EMBED_ARGS = ["--embedding", "--pooling", "last", "-ub", "4096", "-b", "4096"]
PORT = 8081  # not 8080: the chat model may be serving there
# Bump when the chunker changes so old vectors are not silently reused.
CHUNKER_VERSION = 1

HEADING = re.compile(r"^(#{2,6})\s+(.*)$", re.M)
# Pages that are registries or indexes, not knowledge.
SKIP = {"index.md", "canonical-names.md"}


def split_front(text: str) -> tuple[str, str]:
    if not text.startswith("---"):
        return "", text
    end = text.find("\n---", 3)
    if end == -1:
        return "", text
    return text[3:end], text[end + 4 :].lstrip("\n")


def chunk_page(path: Path) -> list[dict]:
    """One chunk per ## section, each carrying the page title for context.

    A section stripped of its page title embeds as an orphan paragraph and
    retrieves badly, so the H1 is prepended to every chunk.
    """
    raw = path.read_text(errors="replace")
    _, body = split_front(raw)
    rel = path.relative_to(WIKI).as_posix()

    m = re.search(r"^#\s+(.*)$", body, re.M)
    title = m.group(1).strip() if m else path.stem.replace("-", " ")

    marks = list(HEADING.finditer(body))
    out: list[dict] = []
    if not marks:
        text = body.strip()
        if text:
            out.append({"path": rel, "slug": path.stem, "heading": "", "text": f"{title}\n\n{text}"})
        return out

    # Prose above the first ## heading is the page's own lede and is worth its
    # own chunk; it usually holds the one-sentence definition.
    lede = body[: marks[0].start()]
    lede = re.sub(r"^#\s+.*$", "", lede, count=1, flags=re.M).strip()
    if lede:
        out.append({"path": rel, "slug": path.stem, "heading": "", "text": f"{title}\n\n{lede}"})

    for i, mk in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(body)
        sec = body[mk.start() : end].strip()
        head = mk.group(2).strip()
        if len(sec) < 40:  # a bare heading carries no meaning
            continue
        out.append({"path": rel, "slug": path.stem, "heading": head,
                    "text": f"{title}\n\n{sec}"})
    return out


def all_chunks() -> list[dict]:
    out = []
    for p in sorted(WIKI.rglob("*.md")):
        if p.name in SKIP:
            continue
        for c in chunk_page(p):
            c["hash"] = hashlib.sha1(c["text"].encode()).hexdigest()[:16]
            c["id"] = f"{c['path']}#{c['heading'][:60]}"
            out.append(c)
    return out


def embed_batch(texts: list[str], port: int = PORT, timeout: int = 300) -> np.ndarray:
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/v1/embeddings",
        data=json.dumps({"input": texts, "model": MODEL}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        payload = json.loads(r.read())
    rows = [d["embedding"] for d in sorted(payload["data"], key=lambda d: d["index"])]
    arr = np.asarray(rows, dtype=np.float32)
    # Normalise once here so every downstream similarity is a plain dot product.
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return arr / norms


def fingerprint() -> str:
    return f"{MODEL}/v{CHUNKER_VERSION}"


def load_existing() -> tuple[np.ndarray | None, dict]:
    if not (VECS.exists() and META.exists()):
        return None, {}
    meta = json.loads(META.read_text())
    if meta.get("fingerprint") != fingerprint():
        print(f"fingerprint changed ({meta.get('fingerprint')} -> {fingerprint()}), rebuilding")
        return None, {}
    return np.load(VECS), meta


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--batch", type=int, default=16)
    args = ap.parse_args()

    chunks = all_chunks()
    if args.status:
        pages = len({c["path"] for c in chunks})
        print(f"{len(chunks)} chunks across {pages} pages")
        if META.exists():
            meta = json.loads(META.read_text())
            print(f"index: {len(meta.get('chunks', []))} vectors, "
                  f"fingerprint {meta.get('fingerprint')}, dims {meta.get('dims')}")
            have = {c["hash"] for c in meta.get("chunks", [])}
            print(f"stale/new chunks: {sum(1 for c in chunks if c['hash'] not in have)}")
        else:
            print("index: none")
        return 0

    reuse: dict[str, np.ndarray] = {}
    if not args.rebuild:
        old_vecs, old_meta = load_existing()
        if old_vecs is not None:
            for i, c in enumerate(old_meta.get("chunks", [])):
                if i < len(old_vecs):
                    reuse[c["hash"]] = old_vecs[i]
        # Resume a run that died before it could write the final matrix.
        if CACHE.exists():
            z = np.load(CACHE, allow_pickle=False)
            if str(z["fingerprint"]) == fingerprint():
                for h, v in zip(z["hashes"].tolist(), z["vectors"]):
                    reuse.setdefault(h, v)
                print(f"resumed {len(z['hashes'])} vectors from checkpoint")

    todo = [c for c in chunks if c["hash"] not in reuse]
    print(f"{len(chunks)} chunks total, {len(chunks) - len(todo)} reused, {len(todo)} to embed")

    def checkpoint(done_map: dict[str, np.ndarray]) -> None:
        if not done_map:
            return
        np.savez(CACHE, fingerprint=np.array(fingerprint()),
                 hashes=np.array(list(done_map)),
                 vectors=np.vstack(list(done_map.values())).astype(np.float32))

    fresh: dict[str, np.ndarray] = dict(reuse)
    started = False
    if todo:
        started = llm_local.ensure_server(
            MODEL, port=PORT, extra_args=EMBED_ARGS
        )
    try:
        for i in range(0, len(todo), args.batch):
            batch = todo[i : i + args.batch]
            for attempt in range(3):
                try:
                    vecs = embed_batch([c["text"] for c in batch])
                    break
                except Exception as e:
                    # The server can die mid-run. Checkpoint, bring it back,
                    # and retry the batch rather than losing everything.
                    print(f"  batch failed ({str(e)[:80]}), attempt {attempt + 1}/3")
                    checkpoint(fresh)
                    llm_local.stop_server(port=PORT, log=lambda *a: None)
                    llm_local.ensure_server(
                        MODEL, port=PORT,
                        extra_args=EMBED_ARGS,
                        log=lambda *a: None,
                    )
            else:
                raise SystemExit("three consecutive batch failures, stopping")
            for c, v in zip(batch, vecs):
                fresh[c["hash"]] = v
            done = min(i + args.batch, len(todo))
            if done % 400 < args.batch or done == len(todo):
                checkpoint(fresh)
                print(f"  embedded {done}/{len(todo)} (checkpointed)")
    finally:
        if started:
            llm_local.stop_server(port=PORT)

    missing = [c["id"] for c in chunks if c["hash"] not in fresh]
    if missing:
        raise SystemExit(f"{len(missing)} chunks have no vector, refusing to write a partial index")
    matrix = np.vstack([fresh[c["hash"]] for c in chunks]) \
        if chunks else np.zeros((0, 1024), dtype=np.float32)
    np.save(VECS, matrix.astype(np.float32))
    META.write_text(json.dumps({
        "fingerprint": fingerprint(),
        "dims": int(matrix.shape[1]) if len(matrix) else 0,
        "chunks": [{k: c[k] for k in ("id", "path", "slug", "heading", "hash")} for c in chunks],
    }, indent=1))
    print(f"wrote {matrix.shape[0]} vectors x {matrix.shape[1] if len(matrix) else 0} dims -> {VECS.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
