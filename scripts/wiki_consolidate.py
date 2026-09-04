#!/usr/bin/env python3
"""
wiki_consolidate.py: Stage 2 of the local wiki compiler.

Reads the grammar-constrained extraction records Stage 1 staged into
.state/wiki-staging/ and consolidates them into wiki/ pages with a frontier
model. Local model did the volume, this does the judgment: merging, dedup,
conflict resolution, linking, frontmatter, voice.

Design notes: docs/04-the-local-model.md

  wiki_consolidate.py --status              # what is staged, no model calls
  wiki_consolidate.py --dry-run --limit 3   # show prompts and proposed writes
  wiki_consolidate.py --limit 5             # consolidate 5 concepts
  wiki_consolidate.py                       # consolidate everything staged
  wiki_consolidate.py --slug pricing-anchor # one concept

Hand edits are never clobbered. Every page written is hashed into
.state/wiki-hashes.json; if a page's current hash does not match, the owner edited
it and new material is appended under a review marker instead of overwriting.

Consumed records are marked in the staging manifest, so reruns do not
re-consolidate the same material. Staging itself stays on disk and is always
safe to delete and rebuild.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import compile as compile_mod  # noqa: E402  (reuses index, commit and state helpers)
import llm_local  # noqa: E402  (local llama-server client, shared with Stage 1)
from brain_config import cfg  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
STAGING = REPO_ROOT / ".state" / "wiki-staging"
MANIFEST = STAGING / "manifest.json"
HASHES = REPO_ROOT / ".state" / "wiki-hashes.json"
GRAMMAR = Path(__file__).resolve().parent / "wiki_page.gbnf"

MODEL = "claude-sonnet-4-6"
FIELDS = ("source", "concept", "type", "confidence", "claim", "evidence")
RECORD_RE = re.compile(r"<<<EXTRACT>>>\n(.*?)\n<<<END>>>", re.S)

# One model call per concept group. This caps how much evidence goes into a
# single call so a heavily-covered concept cannot blow the context.
MAX_RECORDS_PER_CALL = 40
MAX_PAGE_CHARS = 24_000
CALL_TIMEOUT = 300

# The full slug list is ~41k chars / ~10k tokens and was previously sent on
# every call, more than half the prompt. Locally that is pure prefill cost per
# page, so each call now gets a relevant subset of this size instead.
MAX_SLUGS_PER_CALL = 250
# Largest page seen in wiki/ is ~27k chars; 6000 tokens covers it with room.
N_PREDICT = 6000

TYPE_DIRS = {
    "concept": "concepts",
    "lesson": "lessons",
    "person": "people",
    "playbook": "playbooks",
}

REVIEW_START = "<!-- consolidate:review start -->"
REVIEW_END = "<!-- consolidate:review end -->"

SYSTEM_PROMPT = """You maintain a personal wiki for {owner}.\n\nTheir mission: {mission}\nTheir work: {work}

You are given extraction records distilled from their raw sources. Each record has a claim and a verbatim evidence quote that has already been machine-verified against its source document. You also get the current wiki page for this concept, if one exists, and the list of every other page in the wiki.

Produce ONE complete markdown wiki page.

Rules:
- Merge the new records into the existing page. Preserve everything on the existing page that still holds. You are extending a living page, not rewriting it from scratch.
- Deduplicate. Claims that restate each other in different words become one statement.
- On a contradiction between a new record and the existing page, prefer the more recent source. When both are current, state both positions with their provenance rather than silently picking one.
- Drop records that are not durable knowledge, that are trivia, or that belong to a different concept. You are the judgment layer. Discarding a weak record is correct.
- Link to related pages with [[slug]] using ONLY slugs from the provided list. Aim for two to five genuine links. Never invent a slug that is not in the list.
- Open with a level-1 heading, then a one-sentence statement of the idea, then the substance under level-2 headings.
- Frontmatter is required and comes first, in this exact shape:
---
type: concept|lesson|person|playbook
updated: YYYY-MM-DD
sources: [path, path]
confidence: high|medium|low
---
- The sources list is the union of the existing page's sources and the source paths of the records you actually used. Keep it under fifteen entries, most recent first.
- Voice: casual, warm, direct, like a smart friend. Short paragraphs. No emojis. No corporate jargon. No filler openers. Nothing that reads like AI wrote it.
- Never use an em dash, an en dash, or "--" as punctuation. Use a comma, a full stop, or a colon. This is a hard rule and a page containing one is thrown away.
- Do not include the evidence quotes verbatim as a block. Write the knowledge in your own words. Quote only when the exact wording carries the point.

Output the page and nothing else. No preamble, no code fences, no commentary."""

USER_TEMPLATE = """Concept slug: {slug}
Page type: {ptype}
Today: {today}

Existing wiki pages you may link to:
{slugs}

{existing}

New extraction records ({n}):
{records}

Write the complete page now."""


def log(msg: str) -> None:
    print(f"[{dt.datetime.now():%H:%M:%S}] {msg}", flush=True)


def sha(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8", "replace")).hexdigest()


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def load_records() -> list[dict]:
    """Every staged record, tagged with the chunk file it came from."""
    out: list[dict] = []
    if not STAGING.exists():
        return out
    for f in sorted(STAGING.glob("*.txt")):
        if f.name.endswith(".raw.txt"):
            continue
        for block in RECORD_RE.findall(f.read_text(errors="replace")):
            rec: dict[str, str] = {}
            for line in block.split("\n"):
                key, _, val = line.partition(": ")
                if key in FIELDS:
                    rec[key] = val.strip()
            if all(rec.get(k) for k in FIELDS):
                rec["chunk"] = f.stem
                out.append(rec)
    return out


LINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
WORD_RE = re.compile(r"[a-z0-9]+")

RETRY_SUFFIX = """

---
Your previous attempt was rejected by the validator: {why}

{fix}
Output the complete corrected page again. Nothing else."""

FIX_HINTS = {
    "dropped existing section": "Those level-2 sections were on the existing page and are missing from your rewrite. Put them back with their content, then merge the new records in. You are extending the page, not replacing it.",
    "invented wikilink": "Those slugs are not in the list above. Remove them or replace them with a slug that IS in the list. Plain text is better than a broken link.",
    "double hyphen": "Replace every '--' used as punctuation with a comma, a full stop, or a colon.",
    "em dash": "Replace every em dash and en dash with a comma, a full stop, or a colon.",
    "body too short": "The page has too little substance. Use more of the records.",
}


def _tokens(text: str) -> set[str]:
    return set(WORD_RE.findall(text.lower()))


def relevant_slugs(
    slug: str,
    recs: list[dict],
    current_page: str,
    known: set[str],
    batch: set[str],
    limit: int = MAX_SLUGS_PER_CALL,
) -> list[str]:
    """A short, useful slice of the wiki's slugs for one page's prompt.

    Sending all 1,688 slugs costs ~10k tokens of prefill on every call for a
    model that will link to five of them. Priority order: slugs the page already
    links to (never break an existing link), the other concepts in this batch,
    then the best lexical matches against the slug and its claims.

    validate_page still checks against the FULL known set, so a link to a real
    page that missed this cut is not punished.
    """
    out: list[str] = []
    seen: set[str] = {slug}

    def add(s: str) -> None:
        if s in seen or s not in known:
            return
        seen.add(s)
        out.append(s)

    for s in sorted(set(LINK_RE.findall(current_page))):
        add(s)
    for s in sorted(batch):
        add(s)

    target = _tokens(slug)
    for r in recs:
        target |= _tokens(r.get("claim", ""))
    if target:
        scored = []
        for cand in known:
            if cand in seen:
                continue
            t = _tokens(cand)
            if not t:
                continue
            hits = len(t & target)
            if hits:
                scored.append((hits / len(t), hits, cand))
        scored.sort(reverse=True)
        for _, _, cand in scored:
            if len(out) >= limit:
                break
            add(cand)

    return sorted(out[:limit])


def page_path_for(slug: str, ptype: str, existing: dict[str, Path]) -> Path:
    if slug in existing:
        return existing[slug]
    return REPO_ROOT / "wiki" / TYPE_DIRS.get(ptype, "concepts") / f"{slug}.md"


def existing_pages() -> dict[str, Path]:
    out: dict[str, Path] = {}
    wiki = REPO_ROOT / "wiki"
    for p in wiki.rglob("*.md"):
        if p.name == "index.md":
            continue
        out[p.stem] = p
    return out


def call_model(
    system: str,
    user: str,
    timeout: int,
    backend: str = "local",
    model: str = llm_local.DEFAULT_MODEL,
    grammar: str | None = None,
    temperature: float = 0.3,
) -> str:
    """One page-sized model call.

    backend="local" is the default and the whole point: it POSTs to the local
    llama-server, costs nothing, and can therefore afford to retry. backend=
    "claude" keeps the original frontier path for manual one-offs.
    """
    if backend == "local":
        spec = llm_local.model_spec(model)
        prompt = llm_local.chatml(system, user, think=spec["think"])
        resp = llm_local.complete(
            prompt,
            grammar=grammar,
            n_predict=N_PREDICT,
            temperature=temperature,
            timeout=timeout,
        )
        return resp.get("content", "")

    # Frontier path. Mirrors compile.py's provider routing but with a timeout
    # long enough for page generation; compile's 30s cap is tuned for one-liners
    # and would fall back to codex on every call here.
    env = os.environ.copy()
    env[compile_mod.RECURSION_ENV] = "1"
    provider = compile_mod.detect_compile_provider(env)
    full = f"{system}\n\n{user}"

    if provider == "codex":
        return compile_mod._call_codex(full, env)

    result = subprocess.run(
        ["claude", "-p", "--model", MODEL],
        input=full,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )
    if result.returncode != 0:
        stdout = result.stdout.strip()
        if any(p in stdout.lower() for p in compile_mod.QUOTA_PHRASES):
            log("quota exhausted, falling back to codex")
            return compile_mod._call_codex(full, env)
        detail = stdout or result.stderr.strip()
        raise RuntimeError(f"claude CLI failed rc={result.returncode}: {detail[:400]}")
    return result.stdout.strip()


def clean_page(raw: str) -> str:
    s = raw.strip()
    s = re.sub(r"^```(?:markdown|md)?\s*\n", "", s)
    s = re.sub(r"\n```\s*$", "", s)
    return s.strip() + "\n"


# Journal and daily files cover a whole day, so one chunk of one can hold three
# unrelated subjects at once. Stage 1 labels every record in a chunk with the
# single concept it guessed for that chunk, which is how a claim about one
# subject ends up merged into a page about another. Files under sources/ are
# single-topic by construction, so only these prefixes need the relevance bar
# below.
MULTI_TOPIC_PREFIXES = ("daily/", "journal/", "log.md", "network/log.md")

# Rarity-weighted share of a record's vocabulary that must already belong to the
# concept for it to be merged in. 0.25 was tuned against a real 3,300-record
# staging set: it caught every stray cross-subject claim and dropped about 10%
# of records sourced from a multi-topic file. Raising it to 0.50 caught nothing
# more and dropped twice as many, so the extra strictness was pure collateral.
#
# Hand-reading the drops at 0.25, the large majority are clean catches (build
# notes about a script filed under a market-research page). Roughly one in ten
# is arguable. Those are quarantined to .state/wiki-offtopic.jsonl rather than
# deleted, which is what makes this threshold safe to be wrong at. Retune it for
# your own vault by reading that file after a run.
OFFTOPIC_MIN_OVERLAP = 0.25
OFFTOPIC_MIN_ANCHOR = 40
OFFTOPIC_LOG = REPO_ROOT / ".state" / "wiki-offtopic.jsonl"


_IDF: dict[str, float] = {}


def build_idf(records: list[dict]) -> dict[str, float]:
    """Rarity weight per word, measured across every staged record.

    A plain shared-word ratio is not scale invariant: the bigger a page gets,
    the more generic vocabulary its anchor absorbs, so the same two off-topic
    records scored 0.08 and 0.23 against a 516-word page and 0.33 and 0.46
    against the 615-word rewrite of it. That makes the guard weakest on mature
    pages, which are the ones with the most to lose. Weighting by rarity fixes
    it: "cost" and "hours" are worth almost nothing, "blackout" and "roas" carry
    the judgment.
    """
    global _IDF
    df: dict[str, int] = defaultdict(int)
    for r in records:
        for t in _sig(r.get("claim", "") + " " + r.get("evidence", "")):
            df[t] += 1
    n = max(len(records), 1)
    _IDF = {t: math.log(n / (1 + c)) for t, c in df.items()}
    return _IDF


def _weight(token: str) -> float:
    # An unseen word is rarer than anything measured, not less rare.
    return _IDF.get(token, math.log(len(_IDF) or 2))


def _weighted_overlap(sig: set[str], anchor: set[str]) -> float:
    total = sum(_weight(t) for t in sig)
    if total <= 0:
        return 1.0
    return sum(_weight(t) for t in sig & anchor) / total


def concept_anchor(slug: str, recs: list[dict], current: str) -> set[str]:
    """The vocabulary that defines what this concept is actually about.

    Built only from sources that cannot be off-topic: the slug itself, the
    existing page, and records from single-topic source files.
    """
    anchor = _sig(slug.replace("-", " "))
    anchor |= _sig(current[:MAX_PAGE_CHARS])
    for r in recs:
        if not r["source"].startswith(MULTI_TOPIC_PREFIXES):
            anchor |= _sig(r.get("claim", "") + " " + r.get("evidence", ""))
    return anchor


def split_offtopic(
    slug: str, recs: list[dict], current: str
) -> tuple[list[dict], list[dict]]:
    """Partition a concept's records into on-topic and off-topic.

    Conservative by design: it only ever judges records from multi-topic files,
    and only when the concept has enough independent vocabulary to judge
    against. With no trustworthy anchor it keeps everything, because a wrong
    drop loses real knowledge while a wrong keep only adds a paragraph the
    reader can see and delete.
    """
    anchor = concept_anchor(slug, recs, current)
    if len(anchor) < OFFTOPIC_MIN_ANCHOR:
        return recs, []
    kept: list[dict] = []
    dropped: list[dict] = []
    for r in recs:
        if not r["source"].startswith(MULTI_TOPIC_PREFIXES):
            kept.append(r)
            continue
        sig = _sig(r.get("claim", "") + " " + r.get("evidence", ""))
        if not sig:
            kept.append(r)
            continue
        if _weighted_overlap(sig, anchor) >= OFFTOPIC_MIN_OVERLAP:
            kept.append(r)
        else:
            dropped.append(r)
    return kept, dropped


def build_tasks(
    todo: list[str],
    pending: dict[str, list[dict]],
    pages: dict[str, Path],
    known_slugs: set[str],
) -> list[dict]:
    """One prompt per concept, built from a consistent snapshot of wiki/.

    Split out of main() so wiki_model_bench.py benchmarks the exact prompts the
    real run will send, not an approximation of them.
    """
    tasks: list[dict] = []
    for slug in todo:
        recs = pending[slug][:MAX_RECORDS_PER_CALL]
        ptype = max(
            {r["type"] for r in recs},
            key=lambda t: sum(1 for r in recs if r["type"] == t),
        )
        target = page_path_for(slug, ptype, pages)
        rel = target.relative_to(REPO_ROOT).as_posix()
        current = target.read_text(errors="replace") if target.exists() else ""

        # Drop records that belong to a different subject before they reach the
        # prompt. The model has no way to tell that a claim it was handed does
        # not belong to the concept it was asked to write.
        recs, offtopic = split_offtopic(slug, recs, current)
        if not recs:
            # Nothing on-topic survived. main() consumes the concept so the
            # batch loop still terminates.
            continue
        existing_block = (
            f"Existing page ({rel}):\n```md\n{current[:MAX_PAGE_CHARS]}\n```"
            if current
            else "No existing page for this concept. Create it."
        )
        rec_lines = "\n\n".join(
            f"- claim: {r['claim']}\n  evidence: {r['evidence']}\n"
            f"  source: {r['source']}\n  confidence: {r['confidence']}"
            for r in recs
        )
        offered = relevant_slugs(slug, recs, current, known_slugs, set(todo))
        tasks.append({
            "slug": slug,
            "target": target,
            "rel": rel,
            "current": current,
            "n": len(recs),
            "offtopic": offtopic,
            "user": USER_TEMPLATE.format(
                slug=slug,
                ptype=ptype,
                today=dt.date.today().isoformat(),
                slugs=", ".join(offered),
                existing=existing_block,
                records=rec_lines,
                n=len(recs),
            ),
        })
    return tasks


def validate_page(
    text: str,
    slug: str,
    known_slugs: set[str],
    grandfathered: frozenset[str] | set[str] = frozenset(),
) -> tuple[bool, str]:
    """Structural gate. A page that fails is not written."""
    if not text.startswith("---\n"):
        return False, "no frontmatter"
    end = text.find("\n---\n", 4)
    if end == -1:
        return False, "unterminated frontmatter"
    fm = text[4:end]
    for key in ("type:", "updated:", "sources:", "confidence:"):
        if key not in fm:
            return False, f"frontmatter missing {key}"
    body = text[end + 5 :]
    if not re.search(r"^# .+", body, re.M):
        return False, "no h1"
    if len(body.strip()) < 200:
        return False, "body too short"
    if "-" in text or "–" in text:
        return False, "em dash present"
    # "--" is banned as prose punctuation too, but the index convention and HTML
    # comments legitimately use it, so only flag it mid-sentence.
    if re.search(r"\S\s--\s\S", body):
        return False, "double hyphen used as punctuation"
    # Links already on the page are grandfathered. Tightening known_slugs to
    # only concepts that can become pages left 435 links in wiki/ that the model
    # had been told were valid when it wrote them. Without this, preserving them
    # on a rewrite (which the system prompt demands) would fail validation every
    # time and burn the retry budget on a page that is fine. Unresolved links
    # are idiomatic in an Obsidian vault: they mark concepts worth writing.
    bad = (
        {s for s in re.findall(r"\[\[([^\]]+)\]\]", text)}
        - known_slugs
        - grandfathered
        - {slug}
    )
    if bad:
        return False, f"invented wikilink(s): {', '.join(sorted(bad))}"
    return True, ""


H2_RE = re.compile(r"^## (.+?)\s*$", re.M)

# Words too common to prove two headings or two sections are about the same
# thing. Kept deliberately small: the overlap ratios below are computed on what
# survives this filter, so an over-eager list makes every section look alike.
STOPWORDS = frozenset("""
a an and are as at be been but by can do does for from had has have how i if in
into is it its not of on once only or over so than that the their them then
there these they this to up was were what when where which who why will with
you your it's don't
""".split())


def _sig(text: str) -> set[str]:
    """Distinctive words only, the unit every overlap ratio here is measured in."""
    return {t for t in _tokens(text) if t not in STOPWORDS and len(t) > 2}


def _sections(page: str) -> dict[str, str]:
    """Level-2 heading -> the body text under it."""
    out: dict[str, str] = {}
    parts = H2_RE.split(page)
    # split() on a 1-group pattern yields [preamble, head, body, head, body, ...]
    for i in range(1, len(parts) - 1, 2):
        out[parts[i]] = parts[i + 1]
    return out


# A new heading counts as the old one renamed when it keeps this share of the
# old heading's distinctive words ("Truth as Strategy" -> "Truth as the Ultimate
# Strategy" keeps 2/2).
RENAME_MIN_OVERLAP = 0.5

# A section counts as surviving under a different heading when this share of its
# EXCLUSIVE vocabulary is still on the page. Exclusive matters: measured against
# the section's full vocabulary, deleting "Simplicity and Sincerity" outright
# scored 0.78 and passed, because words like "advertising", "message" and
# "service" live all over that page. Words no other section uses are the only
# ones that prove this particular section survived.
SURVIVED_MIN_OVERLAP = 0.6
SURVIVED_MIN_TOKENS = 8


def missing_sections(page: str, current: str) -> list[str]:
    """Level-2 headings whose CONTENT is gone from the rewrite.

    The system prompt says to extend a living page, not rewrite it, but a local
    model drifts into rewriting: measured over 8 real concepts, qwen3-30b-a3b
    kept only 87% of existing headings against qwen3-32b's 96%, once dropping 5
    of 9 sections. Silent omission is the wiki's designed-in failure mode, so it
    is worth a retry rather than a shrug.

    Exact heading matching was the first cut at this and it over-reported badly.
    On advertising-principles it flagged four sections as dropped when the model
    had only retitled them ("Simplicity Over Style" -> "Simplicity and
    Sincerity"), and the page had in fact GROWN from 491 to 534 words. Every one
    of those false alarms costs a full retry at a higher temperature, so the
    check was pushing the model away from a page that was already correct. A
    heading now survives if it is unchanged, recognisably renamed, or its
    content is still on the page under some other heading.
    """
    if not current:
        return []
    had = H2_RE.findall(current)
    now_heads = H2_RE.findall(page)
    now_lower = {h.lower() for h in now_heads}
    page_words = _sig(page)
    old_bodies = _sections(current)

    gone: list[str] = []
    for h in had:
        if h.lower() in now_lower:
            continue
        sig = _sig(h)
        if sig and any(
            len(sig & _sig(n)) / len(sig) >= RENAME_MIN_OVERLAP for n in now_heads
        ):
            continue
        others = set()
        for other_h, other_body in old_bodies.items():
            if other_h != h:
                others |= _sig(other_h + " " + other_body)
        exclusive = _sig(old_bodies.get(h, "")) - others
        if (
            len(exclusive) >= SURVIVED_MIN_TOKENS
            and len(exclusive & page_words) / len(exclusive) >= SURVIVED_MIN_OVERLAP
        ):
            continue
        gone.append(h)
    return gone


def append_for_review(path: Path, page: str) -> None:
    """Hand-edited page: never overwrite. Park the proposal at the bottom."""
    current = path.read_text(errors="replace").rstrip()
    body = page.split("\n---\n", 1)[-1].strip() if page.startswith("---\n") else page.strip()
    stamp = dt.date.today().isoformat()
    block = (
        f"\n\n{REVIEW_START}\n"
        f"## Proposed additions ({stamp})\n\n"
        f"This page was edited by hand since the last consolidation, so nothing above was "
        f"touched. Fold in what is worth keeping and delete this block.\n\n"
        f"{body}\n"
        f"{REVIEW_END}\n"
    )
    # Replace a previous unreviewed block rather than stacking them up.
    if REVIEW_START in current:
        s = current.find(REVIEW_START)
        e = current.find(REVIEW_END)
        if e != -1:
            current = (current[:s] + current[e + len(REVIEW_END):]).rstrip()
    path.write_text(current + block)


def update_index(
    written: list[dict],
    timeout: int,
    backend: str = "local",
    model: str = llm_local.DEFAULT_MODEL,
) -> None:
    """Refresh wiki/index.md one-liners for the pages just written.

    compile.update_index keys the index on repo-relative paths, but every one of
    the 146 existing entries is relative to wiki/. Writing the other form puts a
    broken link in the index, so paths are normalized here.
    """
    parts = []
    for w in written:
        target = REPO_ROOT / w["path"]
        if target.exists():
            parts.append(f"### {w['path']}\n```md\n{target.read_text(errors='replace').rstrip()}\n```\n")
    if not parts:
        return
    # No grammar here: this call returns JSON, not a wiki page.
    raw = call_model(
        compile_mod.INDEX_SUMMARY_PROMPT, "\n".join(parts), timeout,
        backend=backend, model=model, grammar=None,
    )
    s = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    s = re.sub(r"\s*```\s*$", "", s)
    start, end = s.find("["), s.rfind("]")
    if start == -1 or end == -1:
        return
    entries = json.loads(s[start : end + 1])
    index = compile_mod.read_index(REPO_ROOT)
    for entry in entries:
        path, desc = entry.get("path", ""), entry.get("description", "")
        if not path or not desc:
            continue
        rel = path[len("wiki/") :] if path.startswith("wiki/") else path
        if rel.endswith(".md"):
            index[rel] = desc
    compile_mod.write_index(REPO_ROOT, index)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="max concepts this run (0 = all)")
    ap.add_argument("--slug", help="consolidate only this concept")
    ap.add_argument("--min-records", type=int, default=2, help="skip concepts with fewer records")
    ap.add_argument("--timeout", type=int, default=CALL_TIMEOUT)
    ap.add_argument("--workers", type=int, default=1,
                    help="concurrent model calls. Against ONE local server keep this at 1: "
                         "extra threads just contend for the same GPU.")
    ap.add_argument("--backend", choices=("local", "claude"), default="local",
                    help="local llama-server (free, default) or the claude CLI")
    ap.add_argument("--model", default=llm_local.DEFAULT_MODEL,
                    help=f"local model name: {', '.join(llm_local.MODELS)}")
    ap.add_argument("--retries", type=int, default=3,
                    help="extra attempts per concept when validation fails (local calls are free)")
    ap.add_argument("--no-grammar", action="store_true",
                    help="disable the GBNF page grammar (local backend only)")
    ap.add_argument("--no-server", action="store_true",
                    help="do not start llama-server; assume one is already up (or stubbed)")
    ap.add_argument("--status", action="store_true", help="summary only, no model calls")
    ap.add_argument("--dry-run", action="store_true", help="show what would be written")
    ap.add_argument("--commit", action="store_true", help="git commit the result")
    args = ap.parse_args()

    records = load_records()
    if not records:
        log(f"nothing staged in {STAGING} (run wiki_extract.py first)")
        return 0

    build_idf(records)

    man = load_json(MANIFEST, {"chunks": {}})
    consumed = set(man.get("consumed_concepts", []))

    groups: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        groups[r["concept"]].append(r)

    pages = existing_pages()
    # Only concepts that can actually become a page. Offering every staged
    # concept here was how 435 dead wikilinks reached wiki/ in one run: 1,589
    # concepts were staged but 1,233 of them hold a single record, and
    # --min-records keeps those from ever being consolidated. The model never
    # invented a slug, it linked to exactly what it was told was valid.
    known_slugs = set(pages) | {
        s for s, g in groups.items() if len(g) >= args.min_records
    }

    pending = {
        slug: recs
        for slug, recs in groups.items()
        if len(recs) >= args.min_records
        and (args.slug is None or slug == args.slug)
        and sha("".join(sorted(r["claim"] for r in recs))) not in consumed
    }
    order = sorted(pending, key=lambda s: -len(pending[s]))

    log(f"staged: {len(records)} records across {len(groups)} concepts")
    log(f"pending: {len(order)} concepts (min {args.min_records} records each)")
    if args.status:
        for slug in order[:40]:
            mark = "update" if slug in pages else "NEW   "
            log(f"  {mark} {slug}: {len(pending[slug])} records")
        return 0
    if not order:
        log("nothing to consolidate")
        return 0

    todo = order[: args.limit] if args.limit else order
    hashes = load_json(HASHES, {})
    written: list[dict] = []
    skipped_review = 0
    failed = 0
    lossy_pages = 0

    # Build every prompt up front, on the main thread, so the page content each
    # call sees is a consistent snapshot.
    tasks = build_tasks(todo, pending, pages, known_slugs)

    # Records that belong to some other subject. Quarantined, never deleted: the
    # relevance bar is a heuristic, so the cost of it being wrong has to stay at
    # "a line in a file the owner can read" rather than "knowledge silently gone".
    quarantined = [q for t in tasks for q in t.get("offtopic", [])]
    starved = [s for s in todo if s not in {t["slug"] for t in tasks}]
    if starved:
        log(f"skipped {len(starved)} concept(s) with no on-topic records: {', '.join(starved[:5])}")
    if quarantined or starved:
        for slug in starved:
            quarantined.extend(pending[slug][:MAX_RECORDS_PER_CALL])
        if not args.dry_run:
            with open(OFFTOPIC_LOG, "a") as fh:
                for r in quarantined:
                    fh.write(json.dumps({"ts": dt.datetime.now().isoformat(), **r}) + "\n")
        log(f"quarantined {len(quarantined)} off-topic record(s) -> "
            f"{OFFTOPIC_LOG.relative_to(REPO_ROOT).as_posix()}")

    if args.dry_run:
        sizes = []
        for i, t in enumerate(tasks, 1):
            size = len(cfg.render(SYSTEM_PROMPT)) + len(t["user"])
            sizes.append(size)
            log(f"-> {i}/{len(tasks)} {t['slug']} ({t['n']} records) {t['rel']}")
            log(f"   would call model, prompt {size:,} chars")
        if sizes:
            log(f"prompt chars: min {min(sizes):,} median {sorted(sizes)[len(sizes) // 2]:,} max {max(sizes):,}")
        log(f"dry run: {len(tasks)} concepts would be consolidated")
        return 0

    grammar = None
    started_server = False
    if args.backend == "local":
        if not args.no_grammar:
            grammar = GRAMMAR.read_text()
        if not args.no_server:
            started_server = llm_local.ensure_server(args.model, log=log)
        if args.workers > 1:
            log(f"note: {args.workers} workers against one local server, they contend for the GPU")

    def generate(t: dict) -> dict:
        """Model call plus validation, with retries. Pure: touches no shared
        state and no disk.

        The old version made one call and dropped the concept on any failure,
        which is how a bad night lost 25 concepts at a time. A local call costs
        nothing, so a rejection is now fed back verbatim and retried.
        """
        user = t["user"]
        last = "no attempt made"
        # A page that is structurally valid but dropped sections. Kept as a
        # fallback: losing some sections beats losing the whole concept.
        lossy: dict | None = None

        for attempt in range(args.retries + 1):
            try:
                page = clean_page(call_model(
                    cfg.render(SYSTEM_PROMPT), user, args.timeout,
                    backend=args.backend, model=args.model, grammar=grammar,
                    # Nudge temperature up each retry so a wrong answer does not
                    # get regenerated identically.
                    temperature=0.3 + 0.15 * attempt,
                ))
            except Exception as e:
                last = str(e)[:200]
                if attempt < args.retries:  # no point pausing after the last try
                    time.sleep(2)
                continue

            ok, why = validate_page(
                page, t["slug"], known_slugs,
                grandfathered=set(LINK_RE.findall(t["current"])),
            )
            if ok:
                gone = missing_sections(page, t["current"])
                if not gone:
                    return {**t, "page": page, "attempts": attempt + 1}
                # Keep the least lossy attempt seen so far.
                if lossy is None or len(gone) < len(lossy["gone"]):
                    lossy = {"page": page, "gone": gone, "attempts": attempt + 1}
                why = "dropped existing section(s): " + ", ".join(gone)

            last = f"REJECTED: {why}"
            fix = next((h for k, h in FIX_HINTS.items() if k in why), "")
            user = t["user"] + RETRY_SUFFIX.format(why=why, fix=fix)

        if lossy is not None:
            return {**t, "page": lossy["page"], "attempts": args.retries + 1,
                    "lossy": lossy["gone"]}
        return {**t, "error": f"{last} (after {args.retries + 1} attempts)"}

    if args.workers > 1:
        log(f"generating {len(tasks)} pages with {args.workers} workers")
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            results = list(pool.map(generate, tasks))
    else:
        results = [generate(t) for t in tasks]

    # Every write and every state change happens here, single threaded and in a
    # stable order, so hand-edit detection and the manifest stay correct.
    for i, res in enumerate(results, 1):
        slug, rel, target, current = res["slug"], res["rel"], res["target"], res["current"]
        log(f"-> {i}/{len(results)} {slug} ({res['n']} records) {rel}")
        if "error" in res:
            log(f"   {res['error']}")
            failed += 1
            continue
        page = res["page"]
        target.parent.mkdir(parents=True, exist_ok=True)
        if current and hashes.get(rel) and hashes[rel] != sha(current):
            append_for_review(target, page)
            log("   hand-edited since last run, appended for review")
            skipped_review += 1
        else:
            target.write_text(page)
            hashes[rel] = sha(page)
            tries = res.get("attempts", 1)
            log(f"   wrote {len(page):,} chars" + (f" (attempt {tries})" if tries > 1 else ""))
            if res.get("lossy"):
                lossy_pages += 1
                log(f"   WARNING: still dropped section(s) after {tries} attempts: "
                    f"{', '.join(res['lossy'])}")
        written.append({"path": rel, "action": "update" if current else "create"})
        consumed.add(sha("".join(sorted(r["claim"] for r in pending[slug]))))

    # A concept whose records were all off-topic produced no page, but leaving it
    # pending would hand it straight back on the next batch forever. The records
    # are in the quarantine log, so consuming it here loses nothing.
    for slug in starved:
        consumed.add(sha("".join(sorted(r["claim"] for r in pending[slug]))))

    HASHES.write_text(json.dumps(hashes, indent=2))
    man["consumed_concepts"] = sorted(consumed)
    MANIFEST.write_text(json.dumps(man, indent=2))

    if written:
        try:
            update_index(written, args.timeout, backend=args.backend, model=args.model)
            log("index updated")
        except Exception as e:
            log(f"index update failed (pages are written): {str(e)[:160]}")
        compile_mod.log_event(
            REPO_ROOT, f"WIKI CONSOLIDATE: {len(written)} pages from {len(records)} staged records"
        )

    log(
        f"done: {len(written)} pages written, {skipped_review} appended for review, "
        f"{failed} failed" + (f", {lossy_pages} lossy" if lossy_pages else "")
    )
    if started_server:
        log(f"llama-server left running on :{llm_local.DEFAULT_PORT} for the next batch")
    if args.commit and written:
        compile_mod.auto_commit(REPO_ROOT)

    # A batch where nothing was written and everything failed is not a success.
    # Reporting it as one is exactly how this pipeline span 1,026 no-op batches.
    if not written and not skipped_review and failed:
        log("BATCH FAILED: every concept in this batch failed")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
