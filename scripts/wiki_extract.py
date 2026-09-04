#!/usr/bin/env python3
"""
wiki_extract.py: Stage 1 of the local wiki compiler.

Runs a local model (Qwen3-8B via llama-server) over the raw corpus and writes
grammar-constrained extraction records into .state/wiki-staging/. Never touches
wiki/, sources/ or journal/. Output is derived data: deletable and rebuildable.

Design notes: docs/04-the-local-model.md

Modes:
  wiki_extract.py --limit 10          # dry run over the first 10 pending chunks
  wiki_extract.py                     # process everything pending
  wiki_extract.py --status            # manifest summary, no model calls
  wiki_extract.py --roots sources daily projects

Resumption is by content hash from .state/wiki-staging/manifest.json. An
interrupted run resumes at the next pending chunk and never reprocesses one
that is already done.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import shutil
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import llm_local  # noqa: E402  (local llama-server client, shared with Stage 2)

REPO_ROOT = Path(__file__).resolve().parent.parent
STAGING = REPO_ROOT / ".state" / "wiki-staging"
MANIFEST = STAGING / "manifest.json"
GRAMMAR = Path(__file__).resolve().parent / "wiki_extract.gbnf"

# Chunks are grouped PER ROOT, never across roots. Chunk ids are content
# derived from the ordered file list, so a single global grouping means adding a
# new root reshuffles every existing chunk and re-extracts the entire corpus.
# Per-root grouping means adding daily/ and projects/ only adds new chunks and
# the 305 finished sources/ chunks keep their ids.
DEFAULT_ROOTS = [
    "sources", "daily", "projects",
    # Added 2026-08-12 (plan Phase 5). Per-root chunking means these only add
    # new chunks; the finished sources/daily/projects chunks keep their ids.
    # journal/ and areas/finances stay in EXCLUDE_DIRS and are NOT compiled.
    "network", "brainstorms", "docs", "decisions", "references",
    "me", "areas", "learnings",
]
CHUNK_CHARS = 50_000
# A single document larger than this overflows the 32k context and the server
# rejects the whole request, so oversized files are split at line boundaries.
MAX_DOC_CHARS = 40_000
# Fraction of non-empty lines that look like markdown table rows, above which a
# document is treated as a spreadsheet dump rather than prose.
TABLE_LINE_RATIO = 0.4
SERVER = "http://127.0.0.1:8080"
MIN_FREE_GB = 5

# Never feed these to the model, local or not.
EXCLUDE_DIRS = {".git", ".state", "node_modules", "journal", "wiki", "areas/finances"}
SECRET_PAT = re.compile(
    r"(sk-[A-Za-z0-9]{20,}|pit-[A-Za-z0-9-]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY)"
)

SYSTEM_PROMPT = """You extract durable knowledge from a personal knowledge base.

You read raw notes, transcripts and documents and emit atomic extraction records.
Each record is ONE claim that would still be worth knowing in a year.

Rules:
- Extract only claims that are durable knowledge: how something works, what was
  decided and why, a lesson learned, a principle, a fact about a person or market.
- Skip scheduling chatter, greetings, task lists, and anything only true today.
- The evidence field MUST be copied from the document, under 200 characters.
  Copy the words exactly as they appear. Never paraphrase. Never invent a quote.
  If you need to skip over words in the middle of a span, write "..." where you
  skipped. Each side of the "..." must still be copied exactly.
- NEVER join separate lines, bullets or table cells together with commas. Text
  from two different bullets is not one quote. Either quote ONE bullet exactly,
  or separate them with "..." so each piece stands on its own.
  Source:
    - Creepy eyes and facial expression
    - Looks better than salon extensions??
  Wrong: "Creepy eyes and facial expression, Looks better than salon extensions??"
  Right: "Creepy eyes and facial expression ... Looks better than salon extensions??"
  Best:  "Looks better than salon extensions??"
  Prefer ONE short exact bullet over a stitched-together span.
- The claim field is your own one-sentence statement of the idea. Make it
  SPECIFIC. Carry the actual detail across: the number, the name, the mechanism,
  the threshold, what was tried, what happened. A claim someone could have
  written without reading the document is a wasted record.
  Bad: "Continuous learning is essential for success in dropshipping."
  Good: "Testing 100 products without a winner is a normal run of variance, so
  the decision rule is time and budget per test, not a losing streak."
  Bad: "Adaptability is crucial for overcoming challenges."
  Good: "The system uses append-only records because overwriting would destroy
  the audit trail."
- source is the numeric id of the document the claim came from, e.g. "source: 3".
- concept is a lowercase-hyphen slug. Reuse an existing slug from the list when
  the claim belongs to it; invent a new slug when it does not.
- No emojis. No em dashes. Plain direct language.
- Emit between 3 and 12 records. Quality over volume. If the material is thin,
  emit fewer."""

USER_TEMPLATE = """Existing wiki slugs (reuse when the claim fits one):
{slugs}

Documents:
{docs}

Emit extraction records now, in the exact delimiter format."""


def log(msg: str) -> None:
    print(f"[{dt.datetime.now():%H:%M:%S}] {msg}", flush=True)


def sha(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8", "replace")).hexdigest()


def is_table_dump(content: str) -> bool:
    """True for spreadsheet exports. The model cannot quote these verbatim: it
    stitches a plausible row across columns, which the evidence check correctly
    rejects, so they burn compute for almost no kept records."""
    lines = [l for l in content.split("\n") if l.strip()]
    if not lines:
        return True
    rows = sum(1 for l in lines if l.count("|") >= 3)
    return rows / len(lines) > TABLE_LINE_RATIO


def split_doc(rel: str, content: str) -> list[tuple[str, str]]:
    """Split an oversized document into part-sized pieces at line boundaries."""
    if len(content) <= MAX_DOC_CHARS:
        return [(rel, content)]
    parts: list[tuple[str, str]] = []
    buf: list[str] = []
    used = 0
    for line in content.split("\n"):
        if buf and used + len(line) + 1 > MAX_DOC_CHARS:
            parts.append(("\n".join(buf), ""))
            buf, used = [], 0
        buf.append(line)
        used += len(line) + 1
    if buf:
        parts.append(("\n".join(buf), ""))
    n = len(parts)
    return [(f"{rel}#part{i}of{n}", body) for i, (body, _) in enumerate(parts, 1)]


def source_path(rel: str) -> str:
    """Strip any #partNofM suffix back to the real file path."""
    return rel.split("#part")[0]


def collect_files(roots: list[str], include_tables: bool = False) -> list[tuple[str, str, float]]:
    """(relpath, content, mtime) for every allowlisted markdown file."""
    out: list[tuple[str, str, float]] = []
    for root_name in roots:
        root = REPO_ROOT / root_name
        if not root.exists():
            continue
        for p in sorted(root.rglob("*.md")):
            rel = p.relative_to(REPO_ROOT).as_posix()
            if p.name.startswith("."):
                continue
            if any(part in EXCLUDE_DIRS for part in rel.split("/")):
                continue
            if rel.startswith("areas/finances"):
                continue
            try:
                content = p.read_text(errors="replace")
            except Exception:
                continue
            if not content.strip():
                continue
            if SECRET_PAT.search(content):
                log(f"skip (secret pattern): {rel}")
                continue
            if not include_tables and is_table_dump(content):
                continue
            mtime = p.stat().st_mtime
            for part_rel, part_body in split_doc(rel, content):
                out.append((part_rel, part_body, mtime))
    out.sort(key=lambda t: t[2])
    return out


def build_chunks(files: list[tuple[str, str, float]], budget: int) -> list[dict]:
    """Group files into char-budgeted chunks. Chunk id is content-derived, so a
    chunk that has not changed keeps its id across runs."""
    chunks: list[dict] = []
    cur: list[tuple[str, str]] = []
    used = 0
    for rel, content, _ in files:
        size = len(content)
        if cur and used + size > budget:
            chunks.append(_mk_chunk(cur))
            cur, used = [], 0
        cur.append((rel, content))
        used += size
    if cur:
        chunks.append(_mk_chunk(cur))
    return chunks


def _mk_chunk(items: list[tuple[str, str]]) -> dict:
    fingerprint = "|".join(f"{rel}:{sha(c)}" for rel, c in items)
    return {
        "id": sha(fingerprint)[:12],
        "files": [rel for rel, _ in items],
        "docs": items,
        "chars": sum(len(c) for _, c in items),
    }


def wiki_slugs() -> str:
    idx = REPO_ROOT / "wiki" / "index.md"
    if not idx.exists():
        return "(none)"
    slugs = re.findall(r"^- \[([a-z0-9-]+)\]", idx.read_text(errors="replace"), re.M)
    return ", ".join(sorted(set(slugs)))


def build_prompt(chunk: dict, slugs: str, think: bool = True) -> str:
    # Documents are addressed by numeric id, never by path. Paths contain spaces
    # and accented characters that a grammar cannot express, which corrupts the
    # source field and throws away otherwise valid records.
    docs = "\n\n".join(
        f"--- document {i} ---\n{content}" for i, (_, content) in enumerate(chunk["docs"], 1)
    )
    user = USER_TEMPLATE.format(slugs=slugs, docs=docs)
    # The empty think block disables Qwen3 reasoning so the grammar applies from
    # the first token. Only for hybrid-reasoning models: see MODELS[..]['think'].
    return llm_local.chatml(SYSTEM_PROMPT, user, think=think)


def call_server(prompt: str, grammar: str, server: str, n_predict: int, timeout: int) -> dict:
    body = json.dumps(
        {
            "prompt": prompt,
            "grammar": grammar,
            "n_predict": n_predict,
            "temperature": 0.2,
            "top_p": 0.9,
            "repeat_penalty": 1.05,
            "cache_prompt": True,
            "stop": ["<|im_end|>"],
        }
    ).encode()
    req = urllib.request.Request(
        f"{server}/completion", data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


RECORD_RE = re.compile(r"<<<EXTRACT>>>\n(.*?)\n<<<END>>>", re.S)
FIELDS = ("source", "concept", "type", "confidence", "claim", "evidence")


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


SMART = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"', "-": "-", "–": "-"})


def canon(text: str) -> str:
    """Canonical form for provenance matching.

    Measured over 401 rejections from the 2026-07-26 run: 38% were real quotes
    from the right document, rejected only because the model tidied the text as
    it copied. It swaps curly quotes for straight ones, drops a comma, lowercases
    a sentence start, or strips markdown emphasis. Character-exact matching threw
    all of that away as if it were hallucination.

    Case, punctuation and markdown are dropped; the word sequence is not. A
    paraphrase still cannot pass, because its words are not in the source in that
    order, which is the property the guard actually exists to enforce.
    """
    t = text.translate(SMART)
    t = re.sub(r"[*_`]", "", t)
    return re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()


ELLIPSIS_RE = re.compile(r"\s*(?:\.\.\.+|…)\s*")
MIN_FRAGMENT = 12


def evidence_is_verbatim(evidence: str, haystack: str) -> bool:
    """True only if every fragment of the quote appears in the source, in order.

    Fragments come from splitting on ellipsis, which is how the model elides a
    long span. A paraphrase fails because its words are not in the source.

    `haystack` must already be canon()-ed by the caller.
    """
    fragments = [canon(f) for f in ELLIPSIS_RE.split(evidence.strip().strip('"'))]
    fragments = [f for f in fragments if f]
    if not fragments:
        return False
    if any(len(f) < MIN_FRAGMENT for f in fragments) and len(fragments) > 1:
        # A too-short fragment is not distinctive enough to prove provenance.
        fragments = [f for f in fragments if len(f) >= MIN_FRAGMENT]
        if not fragments:
            return False
    if len(fragments) == 1 and len(fragments[0]) < MIN_FRAGMENT:
        return False
    pos = 0
    for frag in fragments:
        found = haystack.find(frag, pos)
        if found < 0:
            return False
        pos = found + len(frag)
    return True


def parse_records(raw: str, chunk: dict) -> tuple[list[dict], dict]:
    """Parse, then validate each record. Returns (kept, reject_counts)."""
    # Per document, so a quote must appear in the document it is attributed to.
    # That verifies attribution as well as provenance.
    haystacks = [canon(c) for _, c in chunk["docs"]]
    kept: list[dict] = []
    rejects = {"malformed": 0, "bad_source": 0, "hallucinated_evidence": 0, "duplicate": 0}
    seen: set[str] = set()

    for block in RECORD_RE.findall(raw):
        rec: dict[str, str] = {}
        for line in block.split("\n"):
            key, _, val = line.partition(": ")
            if key in FIELDS:
                rec[key] = val.strip()
        if not all(f in rec and rec[f] for f in FIELDS):
            rejects["malformed"] += 1
            continue
        # Resolve the numeric doc id back to a real path. Out of range is the
        # only way this can fail, and it costs one record.
        try:
            idx = int(rec["source"])
        except ValueError:
            rejects["bad_source"] += 1
            continue
        if not 1 <= idx <= len(chunk["files"]):
            rejects["bad_source"] += 1
            continue
        rec["source"] = source_path(chunk["files"][idx - 1])
        # Non-negotiable: every evidence quote must appear verbatim in the chunk.
        # Models elide with "..." across a long span, so each fragment is checked
        # separately and in order. Nothing paraphrased can pass.
        if not evidence_is_verbatim(rec["evidence"], haystacks[idx - 1]):
            rejects["hallucinated_evidence"] += 1
            continue
        key = sha(normalize(rec["claim"]).lower())
        if key in seen:
            rejects["duplicate"] += 1
            continue
        seen.add(key)
        kept.append(rec)
    return kept, rejects


def render_records(records: list[dict]) -> str:
    out = []
    for r in records:
        out.append(
            "<<<EXTRACT>>>\n"
            + "\n".join(f"{f}: {r[f]}" for f in FIELDS)
            + "\n<<<END>>>"
        )
    return "\n".join(out) + "\n"


def load_manifest() -> dict:
    if MANIFEST.exists():
        try:
            return json.loads(MANIFEST.read_text())
        except Exception:
            log("manifest unreadable, starting fresh")
    return {"chunks": {}}


def save_manifest(man: dict) -> None:
    STAGING.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(man, indent=2))


def free_gb() -> float:
    return shutil.disk_usage(REPO_ROOT).free / 1e9


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="max chunks this run (0 = all)")
    ap.add_argument("--roots", nargs="+", default=DEFAULT_ROOTS)
    ap.add_argument("--chunk-chars", type=int, default=CHUNK_CHARS)
    ap.add_argument("--server", default=SERVER)
    ap.add_argument("--model", default=None,
                    help=f"start/reuse a local model by name ({', '.join(llm_local.MODELS)}). "
                         "Omit to use whatever is already serving on --server.")
    ap.add_argument("--n-predict", type=int, default=2200)
    ap.add_argument("--timeout", type=int, default=1800)
    ap.add_argument("--min-free", type=float, default=MIN_FREE_GB, help="abort below this many GB free")
    ap.add_argument("--include-tables", action="store_true", help="also process spreadsheet dumps")
    ap.add_argument("--status", action="store_true", help="summary only, no model calls")
    ap.add_argument("--retry-failed", action="store_true")
    args = ap.parse_args()

    # Per root, so one root's chunk ids never depend on another root's files.
    files: list[tuple[str, str, float]] = []
    chunks: list[dict] = []
    for root in args.roots:
        root_files = collect_files([root], include_tables=args.include_tables)
        files.extend(root_files)
        chunks.extend(build_chunks(root_files, args.chunk_chars))
    man = load_manifest()
    done = {c: v for c, v in man["chunks"].items() if v.get("status") == "done"}

    pending = [
        c for c in chunks
        if c["id"] not in done
        and (args.retry_failed or man["chunks"].get(c["id"], {}).get("status") != "failed")
    ]

    log(f"corpus: {len(files)} files, {sum(len(c) for _, c, _ in files):,} chars")
    log(f"chunks: {len(chunks)} total, {len(done)} done, {len(pending)} pending")
    if args.status:
        return 0
    if not pending:
        log("nothing to do")
        return 0
    if free_gb() < args.min_free:
        log(f"abort: only {free_gb():.1f} GB free, need {args.min_free}")
        return 1

    think = True
    if args.model:
        llm_local.ensure_server(args.model, log=log)
        think = llm_local.model_spec(args.model)["think"]
    try:
        urllib.request.urlopen(f"{args.server}/health", timeout=10).read()
    except Exception as e:
        log(f"abort: llama-server unreachable at {args.server} ({e})")
        return 1

    grammar = GRAMMAR.read_text()
    slugs = wiki_slugs()
    STAGING.mkdir(parents=True, exist_ok=True)

    todo = pending[: args.limit] if args.limit else pending
    totals = {"records": 0, "malformed": 0, "bad_source": 0, "hallucinated_evidence": 0, "duplicate": 0}
    t_run = time.time()

    for i, chunk in enumerate(todo, 1):
        t0 = time.time()
        label = f"{i}/{len(todo)} {chunk['id']} ({len(chunk['files'])} files, {chunk['chars']:,} chars)"
        log(f"-> {label}")
        try:
            resp = call_server(
                build_prompt(chunk, slugs, think=think),
                grammar, args.server, args.n_predict, args.timeout,
            )
        except Exception as e:
            log(f"   FAILED: {e}")
            man["chunks"][chunk["id"]] = {
                "status": "failed", "error": str(e)[:200],
                "files": chunk["files"], "ts": dt.datetime.now().isoformat(),
            }
            save_manifest(man)
            continue

        raw = resp.get("content", "")
        kept, rejects = parse_records(raw, chunk)
        (STAGING / f"{chunk['id']}.txt").write_text(render_records(kept) if kept else "")
        (STAGING / f"{chunk['id']}.raw.txt").write_text(raw)

        tim = resp.get("timings", {})
        elapsed = time.time() - t0
        man["chunks"][chunk["id"]] = {
            "status": "done",
            "files": chunk["files"],
            "records": len(kept),
            "rejects": rejects,
            "seconds": round(elapsed, 1),
            "ts": dt.datetime.now().isoformat(),
        }
        save_manifest(man)
        totals["records"] += len(kept)
        for k, v in rejects.items():
            totals[k] += v
        log(
            f"   {len(kept)} kept, rejects {rejects}, {elapsed:.0f}s "
            f"(prefill {tim.get('prompt_per_second', 0):.0f} t/s, gen {tim.get('predicted_per_second', 0):.0f} t/s)"
        )

    log(
        f"run done in {(time.time() - t_run) / 60:.1f} min: {totals['records']} records kept, "
        f"malformed {totals['malformed']}, bad_source {totals['bad_source']}, "
        f"hallucinated {totals['hallucinated_evidence']}, dup {totals['duplicate']}"
    )
    log(f"staging: {STAGING}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
