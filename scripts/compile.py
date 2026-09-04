#!/usr/bin/env python3
"""
compile.py: update wiki/concepts/ and wiki/lessons/ from new sources/ and daily/
material since the last compile. Also runs a two-pass update of CLAUDE.md and
AGENTS.md from feedback memories and me/ context.

Reads state from .state/last-compile.txt (ISO timestamp). Processes everything
modified after that, asks Haiku to route material to concept pages (proposing
new ones freely), and rewrites affected pages in place.

Modes:
  compile.py                 # normal: process gap since last run
  compile.py --since 2026-04-01
  compile.py --dry-run       # show what would change without writing

Called by session hooks (SessionStart, heartbeat, /reflect). Uses a state file
so missed sessions get caught up automatically.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from brain_config import cfg, memory_dir  # noqa: E402

RECURSION_ENV = "BRAIN_FLUSH_RUNNING"
MODEL = cfg.compile_model
CODEX_MODEL_ENV = "BRAIN_CODEX_COMPILE_MODEL"
PROVIDER_ENV = "BRAIN_COMPILE_PROVIDER"
STATE_FILE = ".state/last-compile.txt"
COMMIT_STATE_FILE = ".state/last-commit.txt"
MAX_INPUT_CHARS = 300_000  # hard cap on the prompt payload
DEFAULT_CHUNK_CHARS = 50_000  # per-run budget for new material (leaves room for wiki context)
MAX_CONCEPTS_PER_RUN = 20

# CLAUDE.md / AGENTS.md update
MEMORY_DIR = memory_dir()
BODY_STATE_FILE = ".state/last-body-pass.txt"
MAX_FILE_LINES = 70
MAX_RULES_LINES = 18
MAX_EFFICIENCY_LINES = 10
BODY_PASS_HOURS = 24

LOCKED_START = "<!-- compile:locked start -->"
LOCKED_END = "<!-- compile:locked end -->"
EFFICIENCY_START = "<!-- compile:efficiency start -->"
EFFICIENCY_END = "<!-- compile:efficiency end -->"
RULES_START = "<!-- compile:rules start -->"
RULES_END = "<!-- compile:rules end -->"
ALL_MARKERS = [
    LOCKED_START, LOCKED_END,
    EFFICIENCY_START, EFFICIENCY_END,
    RULES_START, RULES_END,
    "## Token Efficiency",
]

ROUTE_PROMPT = """\
You are maintaining {owner}'s second-brain concept wiki.

About the owner:
- Mission: {mission}
- Work: {work}
- Subjects that matter to them: {domains}

You will receive:
1. WIKI INDEX: every existing wiki page's slug and a one-line description of
   what it covers. This is the vocabulary of `[[slug]]` links you can point to.
2. CURRENT WIKI: a list of existing concept pages with their full content.
3. NEW MATERIAL: raw sources and daily session captures added since the last
   compile.
4. BRAIN OPERATING CONTEXT: project README summaries, schema, PARA map, and
   Favorite Problems used to route material toward action.

Your job: decide which concept/lesson pages need to be created or updated based
on the new material, then output the FULL NEW CONTENT of each affected page.

Rules for the wiki:
- Every page MUST start with a YAML frontmatter block, before the H1 title:
    ---
    type: concept | lesson | person | playbook
    updated: YYYY-MM-DD
    sources: [sources/path/one.md, sources/path/two.md]
    confidence: high | medium | low
    ---
  `type` matches the page's target directory. `updated` is today's date.
  `sources` is a YAML list of the repo-relative source paths that informed the
  page (derived from the page's own Evidence/Sources section). `confidence`
  reflects how well-supported the page's claims are.
- A concept page is a long-lived, evolving synthesis. When updating, preserve
  what is still true and add/revise with the new material. Don't wipe history.
- After the frontmatter: an H1 concept title, then 2-6 short H2 sections.
- Weave `[[slug]]` links inline into the prose wherever a related wiki page is
  genuinely referenced (check the WIKI INDEX for what exists). Target 2-5
  links per page. Prefer linking to a slug that already exists in the WIKI
  INDEX; a link to a slug that doesn't exist yet is allowed but should be rare,
  since it just becomes a backlog signal. Never link a page to its own slug.
  Links go inline in sentences where the idea comes up, never dumped in a
  bottom "Related" list.
- Include an "Evidence" or "Sources" section listing the source files that
  informed the page. Use markdown links like [2026-04-17-one-thing](../../sources/journal/2026-04-17-one-thing.md).
- Propose NEW concept pages freely when material introduces a new idea, person,
  or playbook. Don't force-fit into existing pages.
- Slug is kebab-case, short, nouny. E.g. "one-thing", "pricing-anchor",
  "jane-doe-acme".
- Target directories:
    wiki/concepts/   recurring ideas, principles, topics
    wiki/lessons/    distilled lessons, time-bound insights
    wiki/people/     people the owner works with or learns from
    wiki/playbooks/  repeatable operating patterns
- Preserve the owner's voice: {voice}. If the source has their voice in it,
  keep it in the page.
- HARD BANS: no emojis. NO em dashes (-) ANYWHERE, in any form, spaced or
  unspaced. Use a hyphen, comma, or new sentence instead. This is non-negotiable.

STRICT OUTPUT RULES:
- Output a single JSON array. No preamble, no code fences, no commentary.
- Each item: {"path": "wiki/<dir>/<slug>.md", "action": "create"|"update", "content": "<full markdown>"}.
- If nothing needs changing, output: []
- Cap total output at 20 pages. Prioritize the most important changes if more.
"""

# A "focus" run narrows the compiler to one subject so a single lane of your
# knowledge gets deep, well-linked pages instead of being averaged into general
# notes. Define one by dropping a markdown file in references/focus/<name>.md
# with two headed lists, "## Include" and "## Skip". Then:
#     python3 scripts/compile.py --focus <name>
FOCUS_ROUTE_PROMPT = """\
You are maintaining {owner}'s second-brain concept wiki.

About the owner:
- Mission: {mission}
- Work: {work}

This is a FOCUSED run. You are only extracting knowledge about one subject.

FOCUS DEFINITION:
__FOCUS_DEFINITION__

You will receive:
1. WIKI INDEX: every existing wiki page's slug and a one-line description of
   what it covers. This is the vocabulary of `[[slug]]` links you can point to.
2. CURRENT WIKI: existing concept pages with their full content.
3. NEW MATERIAL: raw sources and daily session captures since the last compile.
4. BRAIN OPERATING CONTEXT: project README summaries, schema, PARA map, and
   Favorite Problems used to route material toward action.

Extract ONLY knowledge that fits the focus definition above. Skip everything
else, however interesting. A later general run will pick that up.

All standard wiki rules apply:
- Every page MUST start with a YAML frontmatter block, before the H1 title:
    ---
    type: concept | lesson | person | playbook
    updated: YYYY-MM-DD
    sources: [sources/path/one.md, sources/path/two.md]
    confidence: high | medium | low
    ---
  `type` matches the page's target directory, `updated` is today's date,
  `sources` lists the repo-relative paths that informed the page, and
  `confidence` reflects how well-supported it is.
- Long-lived synthesis, preserve history on updates, H1 + 2-6 H2 sections
- Weave `[[slug]]` links inline into the prose wherever a related wiki page is
  genuinely referenced (check the WIKI INDEX for what exists). Target 2-5
  links per page, prefer existing slugs, never link a page to itself.
- Include a Sources section with markdown links to source files
- Propose new pages freely for distinct topics inside the focus
- Slug is kebab-case, short, nouny
- Target directories: wiki/concepts/, wiki/lessons/, wiki/playbooks/
- The owner's voice: {voice}
- HARD BANS: no emojis. NO em dashes anywhere. Non-negotiable.

STRICT OUTPUT RULES:
- Output a single JSON array. No preamble, no code fences, no commentary.
- Each item: {"path": "wiki/<dir>/<slug>.md", "action": "create"|"update", "content": "<full markdown>"}.
- If nothing in this chunk fits the focus, output: []
- Cap total output at 20 pages. Prioritize the most important changes if more.
"""


def load_focus(repo_root: Path, name: str) -> str:
    """Read references/focus/<name>.md, the user-authored focus definition."""
    path = repo_root / "references" / "focus" / f"{name}.md"
    if not path.exists():
        available = sorted(
            f.stem for f in (repo_root / "references" / "focus").glob("*.md")
        )
        raise SystemExit(
            f"no focus definition at {path.relative_to(repo_root)}. "
            + (f"Available: {', '.join(available)}" if available else
               "Create one with an '## Include' and a '## Skip' list.")
        )
    return path.read_text().strip()


INDEX_SUMMARY_PROMPT = """\
You are building a one-line index of wiki pages for a second brain.

You will receive a list of wiki pages with their full content. For each page,
output a single JSON object with the page path and a one-line description that
captures what knowledge the page contains -- written to help decide whether to
load it for a specific task.

Rules:
- Description should be 8-15 words, specific, topic-focused
- Describe the KNOWLEDGE in the page, not the title
- No fluff, no emojis, no em dashes
- Output a JSON array only. No preamble, no fences.
- Each item: {"path": "wiki/dir/slug.md", "description": "one-liner"}
"""

RULES_PROMPT = """\
You are updating two sections of CLAUDE.md, a session-loaded context file for
an AI agent working in a personal second brain.

You will receive:
1. FEEDBACK MEMORIES -- corrections and validated approaches (highest signal).
2. LEARNINGS -- captured errors and successful patterns from recent sessions.
3. CURRENT RULES SECTION -- the existing Learned Rules content (between fences).
4. CURRENT TOKEN EFFICIENCY SECTION -- the existing Token Efficiency content.

Your job: produce updated content for both sections.

## Learned Rules rules:
- Hard cap: 18 lines total. At the cap you MUST evict before adding -- this
  section is meant to stay tight, not grow.
- Only durable, CROSS-CUTTING rules belong here (apply across many sessions and
  skills). Skill-specific detail (e.g. SET quoting, a single skill's quirks)
  belongs IN that skill, referenced by one pointer line, not enumerated here.
- Format: `- {one-line rule} -> {pointer}` (pointer = file/section or memory filename).
- Preserve high-value existing rules. Evict stale, narrow, or low-value ones.
- Collapse near-duplicates into a single line. Both corrections AND validated
  approaches belong here, but only if broadly applicable.

## Token Efficiency rules:
- Soft cap: 10 lines.
- Only update if you see a recurring token-inefficiency pattern (redundant tool
  calls, repeated re-reads, missed doc consultations).
- If no pattern detected, output the current section unchanged.

HARD BANS: no emojis. NO em dashes (--) ANYWHERE. Non-negotiable.

STRICT OUTPUT RULES:
- Output a single JSON object. No preamble, no code fences, no commentary.
- Format: {"rules": "<rules body>", "efficiency": "<efficiency body>"}
- Section bodies: content only, no fence markers, no section headings.
- If nothing needs changing in a section, repeat its current content unchanged.
"""

BODY_PROMPT = """\
You are maintaining the editable body of CLAUDE.md, a session-loaded context
file for an AI agent working in {owner}'s personal second brain.

You will receive:
1. LOCKED BLOCK -- read-only. Never modify this.
2. CURRENT BODY -- the content between the locked end and Token Efficiency.
3. ME FILES -- the owner's canonical self-context.
4. RECENT DECISIONS -- last 30 days of decisions/log.md.
5. RECENT DAILY -- last 14 days of daily/ captures.
6. BRAIN OPERATING CONTEXT -- active project READMEs, schema, PARA map, and
   Favorite Problems.

Your job: update the body to reflect current truth.

Rules:
- This file loads EVERY session. It is a light index, not a knowledge base.
  Default to a pointer over prose. Never inline tool inventories, long thread
  lists, connection how-tos, or anything the agent can read on demand.
- Keep the structure to three sections: "Who" (one line: name, role, location,
  timezone), "Priorities" (comp + deadline, primary bet, and a pointer to
  me/priorities.md + me/work.md for the full ranked list and active threads),
  and "How the Brain works" (pointers only: connections.md, references/, memory
  locations, decision-log format, skills). Do not add new top-level sections.
- Update Priorities to match me/priorities.md and me/work.md. Drop stale items.
- Target: keep the whole file <=70 lines total -- compress aggressively, and
  when a section grows past a few lines, move the detail out to a pointer.
- The owner's voice: {voice}.
- HARD BANS: no emojis. NO em dashes ANYWHERE. Non-negotiable.

STRICT OUTPUT RULES:
- Output a single JSON object. No preamble, no code fences, no commentary.
- Format: {"body": "<body content>"}
- Body: content only, from after locked end to before Token Efficiency.
  Start with \\n and preserve natural section spacing.
- If current body is already accurate, repeat it unchanged.
"""


def log_event(repo_root: Path, msg: str) -> None:
    try:
        today = dt.date.today().isoformat()
        with (repo_root / "log.md").open("a") as f:
            f.write(f"[{today}] {msg}\n")
    except Exception:
        pass


def read_state(repo_root: Path) -> dt.datetime | None:
    state = repo_root / STATE_FILE
    if not state.exists():
        return None
    try:
        return dt.datetime.fromisoformat(state.read_text().strip())
    except Exception:
        return None


def write_state(repo_root: Path, ts: dt.datetime) -> None:
    state = repo_root / STATE_FILE
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(ts.isoformat())


def collect_new_material(repo_root: Path, since: dt.datetime) -> list[tuple[Path, str, dt.datetime]]:
    """Return list of (relative_path, content, mtime) for files newer than `since`,
    sorted by mtime ascending so chunked runs drain the backlog in time order."""
    out: list[tuple[Path, str, dt.datetime]] = []
    roots = [repo_root / "sources", repo_root / "daily"]
    for root in roots:
        if not root.exists():
            continue
        for p in root.rglob("*.md"):
            # Folder documentation is scaffolding, not material. Without this a
            # fresh clone compiles its own README into a wiki page.
            if p.name in ("README.md", "index.md"):
                continue
            if p.name.startswith("."):
                continue
            mtime = dt.datetime.fromtimestamp(p.stat().st_mtime)
            if mtime <= since:
                continue
            try:
                out.append((p.relative_to(repo_root), p.read_text(errors="replace"), mtime))
            except Exception:
                continue
    out.sort(key=lambda t: t[2])
    return out


def chunk_by_chars(
    material: list[tuple[Path, str, dt.datetime]],
    budget: int,
) -> tuple[list[tuple[Path, str, dt.datetime]], list[tuple[Path, str, dt.datetime]]]:
    """Split material into (chunk, remaining) by char budget. Always takes at
    least one file even if oversized, so a single huge file can't deadlock the
    backlog."""
    chunk: list[tuple[Path, str, dt.datetime]] = []
    used = 0
    for i, item in enumerate(material):
        size = len(item[1])
        if chunk and used + size > budget:
            return chunk, material[i:]
        chunk.append(item)
        used += size
    return chunk, []


def collect_wiki(repo_root: Path) -> list[tuple[Path, str]]:
    out: list[tuple[Path, str]] = []
    wiki = repo_root / "wiki"
    if not wiki.exists():
        return out
    for p in wiki.rglob("*.md"):
        if p.name.startswith("."):
            continue
        try:
            out.append((p.relative_to(repo_root), p.read_text(errors="replace")))
        except Exception:
            continue
    return out


def build_payload(
    wiki_pages: list[tuple[Path, str]],
    new_material: list[tuple[Path, str, dt.datetime]],
    operating_context: list[tuple[str, str]] | None = None,
    wiki_index: dict[str, str] | None = None,
) -> str:
    parts = ["## WIKI INDEX (existing slugs available for [[wikilinks]])\n"]
    if wiki_index:
        for path in sorted(wiki_index):
            slug = Path(path).stem
            parts.append(f"- [[{slug}]] -- {wiki_index[path]}")
        parts.append("")
    else:
        parts.append("(empty, no pages yet)\n")
    parts.append("\n## CURRENT WIKI\n")
    if not wiki_pages:
        parts.append("(empty, no pages yet)\n")
    for path, content in wiki_pages:
        parts.append(f"### {path}\n```md\n{content.rstrip()}\n```\n")
    if operating_context:
        parts.append("\n## BRAIN OPERATING CONTEXT\n")
        for name, content in operating_context:
            parts.append(f"### {name}\n```md\n{content.rstrip()}\n```\n")
    parts.append("\n## NEW MATERIAL\n")
    for item in new_material:
        path, content = item[0], item[1]
        parts.append(f"### {path}\n```md\n{content.rstrip()}\n```\n")
    return "\n".join(parts)


def detect_compile_provider(env: dict[str, str] | None = None) -> str:
    """Pick the LLM provider from the launcher, unless explicitly overridden."""
    env = env or os.environ
    override = env.get(PROVIDER_ENV)
    if override:
        return override.lower()

    if any(k.startswith("CLAUDE") for k in env):
        return "claude"
    if any(k.startswith("CODEX") for k in env):
        return "codex"

    try:
        pid = os.getppid()
        for _ in range(8):
            result = subprocess.run(
                ["ps", "-o", "ppid=", "-o", "comm=", "-p", str(pid)],
                capture_output=True,
                text=True,
                timeout=2,
            )
            line = result.stdout.strip()
            if not line:
                break
            parent_pid, command = line.split(None, 1)
            command = command.lower()
            if "claude" in command:
                return "claude"
            if "codex" in command:
                return "codex"
            pid = int(parent_pid)
            if pid <= 1:
                break
    except Exception:
        pass

    return "codex"


QUOTA_PHRASES = ("out of extra usage", "usage limit", "rate limit")


def _call_codex(full: str, env: dict[str, str]) -> str:
    repo_root = Path.cwd()
    with tempfile.NamedTemporaryFile("w+", delete=False) as f:
        out_path = Path(f.name)
    cmd = [
        "codex",
        "exec",
        "--ephemeral",
        "--skip-git-repo-check",
        "--sandbox",
        "read-only",
        "-C",
        str(repo_root),
        "-o",
        str(out_path),
        "-",
    ]
    codex_model = env.get(CODEX_MODEL_ENV)
    if codex_model:
        cmd[2:2] = ["-m", codex_model]
    try:
        result = subprocess.run(
            cmd,
            input=full,
            capture_output=True,
            text=True,
            timeout=600,
            cwd=repo_root,
            env=env,
        )
        if result.returncode != 0:
            err = result.stderr.strip()[:1000]
            out = result.stdout.strip()[:1000]
            cli = subprocess.run(["which", "codex"], capture_output=True, text=True).stdout.strip()
            raise RuntimeError(
                f"codex CLI failed rc={result.returncode} cli={cli!r} stderr={err!r} stdout={out!r}"
            )
        return out_path.read_text(errors="replace").strip()
    finally:
        try:
            out_path.unlink()
        except OSError:
            pass


def call_haiku(prompt: str, payload: str) -> str:
    # Every prompt in this file is written against {owner} / {mission} / {work}
    # / {voice} placeholders. Rendering here means no caller can forget to.
    full = f"{cfg.render(prompt)}\n\n{payload}"
    env = os.environ.copy()
    env[RECURSION_ENV] = "1"
    provider = detect_compile_provider(env)

    if provider == "codex":
        return _call_codex(full, env)

    if provider != "claude":
        raise RuntimeError(f"unknown compile provider: {provider}")

    try:
        result = subprocess.run(
            ["claude", "-p", "--model", MODEL],
            input=full,
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )
    except subprocess.TimeoutExpired:
        log_event(Path.cwd(), "COMPILE FALLBACK: claude CLI timed out → codex")
        return _call_codex(full, env)
    if result.returncode != 0:
        stdout = result.stdout.strip()
        # Quota exhausted: fall back to codex transparently
        if any(p in stdout.lower() for p in QUOTA_PHRASES):
            log_event(Path.cwd(), "COMPILE FALLBACK: claude quota exhausted → codex")
            return _call_codex(full, env)
        err = result.stderr.strip()[:1000]
        out = stdout[:1000]
        cli = subprocess.run(["which", "claude"], capture_output=True, text=True).stdout.strip()
        raise RuntimeError(
            f"claude CLI failed rc={result.returncode} cli={cli!r} stderr={err!r} stdout={out!r}"
        )
    return result.stdout.strip()


def parse_actions(raw: str) -> list[dict]:
    """Parse Haiku's JSON output, forgiving common wrappers."""
    s = raw.strip()
    # Strip ```json ... ``` fences if Haiku leaked them
    s = re.sub(r"^```(?:json)?\s*", "", s)
    s = re.sub(r"\s*```\s*$", "", s)
    # Find the first `[` and last `]` as a fallback
    start = s.find("[")
    end = s.rfind("]")
    if start == -1 or end == -1:
        return []
    try:
        return json.loads(s[start : end + 1])
    except json.JSONDecodeError:
        return []


def validate_action(action: dict) -> bool:
    if not isinstance(action, dict):
        return False
    path = action.get("path", "")
    if not path.startswith("wiki/") or not path.endswith(".md"):
        return False
    if action.get("action") not in ("create", "update"):
        return False
    if not isinstance(action.get("content"), str) or len(action["content"].strip()) < 30:
        return False
    # Prevent path traversal
    if ".." in path or path.startswith("/"):
        return False
    return True


def stamp_timezone(repo_root: Path) -> None:
    """Record this computer's current IANA timezone into a tracked file so the
    nightly cloud dreamer (which runs on a fresh checkout and cannot see this
    machine) computes "today/yesterday" in whatever timezone the owner is actually
    in. The Brain follows the computer: when the owner travels, the next compile run
    stamps the new zone and the dream picks it up on its next push.

    NOTE: this file MUST stay outside .state/ (which is gitignored): the dream
    reads it from a clean clone, so it has to be committed."""
    tz_file = repo_root / ".claude" / "dream" / "timezone"
    try:
        # Resolve the IANA name from /etc/localtime (works on macOS + Linux).
        link = os.readlink("/etc/localtime")  # .../zoneinfo/Europe/Sofia
        if "zoneinfo/" not in link:
            return
        tz = link.split("zoneinfo/", 1)[1].strip()
        if not tz:
            return
        current = tz_file.read_text().strip() if tz_file.exists() else None
        if current != tz:
            tz_file.parent.mkdir(parents=True, exist_ok=True)
            tz_file.write_text(tz + "\n")
            log_event(repo_root, f"TIMEZONE STAMP: {current or 'unset'} -> {tz}")
    except (OSError, ValueError) as exc:
        log_event(repo_root, f"TIMEZONE STAMP ERROR: {exc}")


def auto_commit(repo_root: Path) -> None:
    """Commit any dirty files once per day. Gated by .state/last-commit.txt so
    multiple triggers (SessionStart, launchd RunAtLoad, StartInterval) don't
    produce duplicate commits. The post-commit hook handles pushing."""
    today = dt.date.today().isoformat()
    state = repo_root / COMMIT_STATE_FILE
    if state.exists() and state.read_text().strip() == today:
        return
    try:
        # Clear a stale index.lock (>10 min old) that would block git add.
        lock = repo_root / ".git" / "index.lock"
        if lock.exists():
            import time as _time
            age = _time.time() - lock.stat().st_mtime
            if age > 600:
                lock.unlink()
            else:
                log_event(repo_root, "AUTO-COMMIT SKIP: index.lock held by another process")
                return

        state.parent.mkdir(parents=True, exist_ok=True)
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, cwd=repo_root, timeout=60,
        )
        if status.returncode != 0:
            log_event(repo_root, f"AUTO-COMMIT ERROR: git status failed: {status.stderr.strip()[:200]}")
            return
        if not status.stdout.strip():
            state.write_text(today)
            return

        # Retry git add up to 2 times; Obsidian may briefly hold file locks.
        for attempt in range(2):
            result = subprocess.run(
                ["git", "add", "-A"], cwd=repo_root, timeout=120,
                capture_output=True, text=True,
            )
            if result.returncode == 0:
                break
            if attempt == 0:
                import time as _time
                _time.sleep(5)
        else:
            log_event(repo_root, f"AUTO-COMMIT ERROR: git add failed after retries: {result.stderr.strip()[:200]}")
            return

        commit = subprocess.run(
            ["git", "commit", "-m", f"auto: daily brain snapshot {today}"],
            capture_output=True, text=True, cwd=repo_root, timeout=120,
        )
        if commit.returncode == 0:
            state.write_text(today)
            log_event(repo_root, f"AUTO-COMMIT OK: {today}")
        else:
            log_event(repo_root, f"AUTO-COMMIT ERROR: {commit.stderr.strip()[:300]}")
    except Exception as exc:
        log_event(repo_root, f"AUTO-COMMIT ERROR: {exc}")


def read_index(repo_root: Path) -> dict[str, str]:
    index_file = repo_root / "wiki" / "index.md"
    if not index_file.exists():
        return {}
    out: dict[str, str] = {}
    for line in index_file.read_text().splitlines():
        m = re.match(r"^- \[.+?\]\((.+?)\) -- (.+)$", line.strip())
        if m:
            out[m.group(1)] = m.group(2)
    return out


def write_index(repo_root: Path, index: dict[str, str]) -> None:
    index_file = repo_root / "wiki" / "index.md"
    lines = []
    for path in sorted(index):
        slug = Path(path).stem
        desc = index[path]
        lines.append(f"- [{slug}]({path}) -- {desc}")
    index_file.write_text("\n".join(lines) + "\n")


def update_index(repo_root: Path, touched_actions: list[dict]) -> None:
    if not touched_actions:
        return
    parts = []
    for a in touched_actions:
        target = repo_root / a["path"]
        if target.exists():
            content = target.read_text(errors="replace")
            parts.append(f"### {a['path']}\n```md\n{content.rstrip()}\n```\n")
    if not parts:
        return
    payload = "\n".join(parts)
    try:
        raw = call_haiku(INDEX_SUMMARY_PROMPT, payload)
    except Exception:
        return
    s = raw.strip()
    s = re.sub(r"^```(?:json)?\s*", "", s)
    s = re.sub(r"\s*```\s*$", "", s)
    start, end = s.find("["), s.rfind("]")
    if start == -1 or end == -1:
        return
    try:
        entries = json.loads(s[start:end + 1])
    except json.JSONDecodeError:
        return
    index = read_index(repo_root)
    for entry in entries:
        path = entry.get("path", "")
        desc = entry.get("description", "")
        if path and desc and path.startswith("wiki/") and path.endswith(".md"):
            # Index links are resolved relative to wiki/index.md, so the wiki/
            # prefix has to come off or the link lands nowhere.
            index[path[len("wiki/"):]] = desc
    write_index(repo_root, index)


# ---------------------------------------------------------------------------
# CLAUDE.md / AGENTS.md update helpers
# ---------------------------------------------------------------------------

def extract_between(content: str, start_marker: str, end_marker: str) -> str | None:
    """Extract text strictly between start_marker and end_marker."""
    s = content.find(start_marker)
    if s == -1:
        return None
    s += len(start_marker)
    e = content.find(end_marker, s)
    if e == -1:
        return None
    return content[s:e]


def substitute_between(content: str, start_marker: str, end_marker: str, new_body: str) -> str:
    """Replace text between start_marker and end_marker with new_body."""
    s = content.find(start_marker)
    if s == -1:
        return content
    s += len(start_marker)
    e = content.find(end_marker, s)
    if e == -1:
        return content
    # Normalize: new_body surrounded by single newlines
    normalized = "\n" + new_body.strip() + "\n"
    return content[:s] + normalized + content[e:]


def extract_body(content: str) -> str | None:
    """Extract the compile-managed body: between LOCKED_END and \\n## Token Efficiency."""
    s = content.find(LOCKED_END)
    if s == -1:
        return None
    s += len(LOCKED_END)
    e = content.find("\n## Token Efficiency", s)
    if e == -1:
        return None
    return content[s:e]


def substitute_body(content: str, new_body: str) -> str:
    """Replace the compile-managed body region."""
    s = content.find(LOCKED_END)
    if s == -1:
        return content
    s += len(LOCKED_END)
    e = content.find("\n## Token Efficiency", s)
    if e == -1:
        return content
    # Ensure new_body starts with \n
    body = new_body if new_body.startswith("\n") else "\n" + new_body
    # Ensure new_body ends without trailing newline (the \n before ## Token Efficiency is preserved)
    body = body.rstrip("\n")
    return content[:s] + body + content[e:]


def collect_feedback_memories(since: dt.datetime) -> list[tuple[str, str]]:
    """Collect feedback_*.md files from the memory directory modified since `since`."""
    out: list[tuple[str, str]] = []
    if not MEMORY_DIR.exists():
        return out
    for p in MEMORY_DIR.glob("feedback_*.md"):
        try:
            mtime = dt.datetime.fromtimestamp(p.stat().st_mtime)
            if mtime > since:
                out.append((p.name, p.read_text(errors="replace")))
        except Exception:
            continue
    return out


def collect_learnings_since(repo_root: Path, since: dt.datetime) -> list[tuple[str, str]]:
    """Collect learnings files modified since `since`."""
    out: list[tuple[str, str]] = []
    for name in ["LEARNINGS.md", "ERRORS.md", "SKILL-CANDIDATES.md"]:
        p = repo_root / "learnings" / name
        if not p.exists():
            continue
        try:
            mtime = dt.datetime.fromtimestamp(p.stat().st_mtime)
            if mtime > since:
                out.append((name, p.read_text(errors="replace")))
        except Exception:
            continue
    return out


def read_body_state(repo_root: Path) -> dt.datetime | None:
    state = repo_root / BODY_STATE_FILE
    if not state.exists():
        return None
    try:
        return dt.datetime.fromisoformat(state.read_text().strip())
    except Exception:
        return None


def write_body_state(repo_root: Path, ts: dt.datetime) -> None:
    state = repo_root / BODY_STATE_FILE
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(ts.isoformat())


def check_no_markers(text: str) -> bool:
    """Return True if text contains none of the compile markers (injection guard)."""
    return not any(m in text for m in ALL_MARKERS)


def enforce_rules_cap(body: str, max_lines: int) -> str:
    """Truncate the rules body to at most max_lines non-empty lines."""
    lines = [l for l in body.splitlines() if l.strip()]
    if len(lines) <= max_lines:
        return body
    return "\n".join(lines[:max_lines]) + "\n"


def validate_claude_content(content: str, original_locked: str) -> tuple[bool, str]:
    """
    Validate the post-substitution CLAUDE.md content.
    Returns (ok, error_message).
    """
    # LOCKED block must be byte-identical
    current_locked = extract_between(content, LOCKED_START, LOCKED_END)
    if current_locked is None:
        return False, "LOCKED block markers missing"
    if current_locked != original_locked:
        return False, "LOCKED block was modified by Haiku output"

    # Fenced sections must be present
    for marker in [EFFICIENCY_START, EFFICIENCY_END, RULES_START, RULES_END]:
        if marker not in content:
            return False, f"fence marker missing: {marker!r}"

    return True, ""


def parse_json_obj(raw: str) -> dict:
    """Parse a JSON object from Haiku output, stripping common wrappers."""
    s = raw.strip()
    s = re.sub(r"^```(?:json)?\s*", "", s)
    s = re.sub(r"\s*```\s*$", "", s)
    start = s.find("{")
    end = s.rfind("}")
    if start == -1 or end == -1:
        return {}
    try:
        return json.loads(s[start:end + 1])
    except json.JSONDecodeError:
        return {}


def collect_me_files(repo_root: Path) -> list[tuple[str, str]]:
    out = []
    for name in ["me.md", "work.md", "team.md", "priorities.md", "goals.md"]:
        p = repo_root / "me" / name
        if p.exists():
            try:
                out.append((f"me/{name}", p.read_text(errors="replace")))
            except Exception:
                pass
    return out


def collect_recent_decisions(repo_root: Path, days: int = 30) -> str:
    p = repo_root / "decisions" / "log.md"
    if not p.exists():
        return ""
    cutoff = dt.date.today() - dt.timedelta(days=days)
    lines = []
    for line in p.read_text(errors="replace").splitlines():
        m = re.match(r"^\[(\d{4}-\d{2}-\d{2})\]", line)
        if m:
            try:
                d = dt.date.fromisoformat(m.group(1))
                if d >= cutoff:
                    lines.append(line)
            except ValueError:
                pass
    return "\n".join(lines)


def collect_recent_daily(repo_root: Path, days: int = 14) -> list[tuple[str, str]]:
    out = []
    daily_dir = repo_root / "daily"
    if not daily_dir.exists():
        return out
    cutoff = dt.date.today() - dt.timedelta(days=days)
    # Human plan/reflection files plus the machine session-capture files that
    # live in daily/sessions/ (split out so automated writes never
    # collide with hand edits).
    candidates = sorted(daily_dir.glob("*.md"), reverse=True) + sorted(
        daily_dir.glob("sessions/*.md"), reverse=True
    )
    for p in candidates:
        m = re.match(r"(\d{4}-\d{2}-\d{2})(-sessions)?\.md$", p.name)
        if not m:
            continue
        try:
            d = dt.date.fromisoformat(m.group(1))
        except ValueError:
            continue
        if d < cutoff:
            continue
        try:
            out.append((p.name, p.read_text(errors="replace")))
        except Exception:
            continue
    return out


def collect_project_readmes(repo_root: Path) -> list[tuple[str, str]]:
    """Collect project README files as lightweight active-work context."""
    out = []
    projects_dir = repo_root / "projects"
    if not projects_dir.exists():
        return out
    for p in sorted(projects_dir.glob("*/README.md")):
        try:
            out.append((str(p.relative_to(repo_root)), p.read_text(errors="replace")))
        except Exception:
            continue
    return out


def collect_operating_context(repo_root: Path) -> list[tuple[str, str]]:
    """Collect small operating docs that help route material toward action."""
    out: list[tuple[str, str]] = []
    for rel in [
        "references/brain-schema.md",
        "references/para-map.md",
        "areas/favorite-problems.md",
    ]:
        p = repo_root / rel
        if p.exists():
            try:
                out.append((rel, p.read_text(errors="replace")))
            except Exception:
                continue
    out.extend(collect_project_readmes(repo_root))
    return out


def update_claude_agents_md(repo_root: Path, since: dt.datetime, dry_run: bool) -> None:
    """Two-pass update of CLAUDE.md and AGENTS.md from feedback memories and me/ context."""
    claude_path = repo_root / "CLAUDE.md"
    agents_path = repo_root / "AGENTS.md"

    if not claude_path.exists():
        return

    original_content = claude_path.read_text()
    original_locked = extract_between(original_content, LOCKED_START, LOCKED_END)
    if original_locked is None:
        log_event(repo_root, "CLAUDE.MD SKIP: LOCKED block not found")
        return

    working_content = original_content
    pass1_ran = False
    pass2_ran = False
    changes: list[str] = []

    # --- Pass 1: Rules and efficiency ---
    feedback = collect_feedback_memories(since)
    learnings = collect_learnings_since(repo_root, since)

    if feedback or learnings:
        efficiency_body = extract_between(working_content, EFFICIENCY_START, EFFICIENCY_END) or ""
        rules_body = extract_between(working_content, RULES_START, RULES_END) or ""

        parts = []
        if feedback:
            parts.append("## FEEDBACK MEMORIES\n")
            for name, content in feedback:
                parts.append(f"### {name}\n{content.strip()}\n")
        if learnings:
            parts.append("## LEARNINGS\n")
            for name, content in learnings:
                parts.append(f"### {name}\n{content.strip()}\n")
        parts.append(f"## CURRENT RULES SECTION\n{rules_body.strip()}\n")
        parts.append(f"## CURRENT TOKEN EFFICIENCY SECTION\n{efficiency_body.strip()}\n")

        payload = "\n".join(parts)

        if dry_run:
            print(f"[dry-run] CLAUDE.md Pass 1: {len(feedback)} feedback files, {len(learnings)} learnings files")
        else:
            try:
                raw = call_haiku(RULES_PROMPT, payload)
                result = parse_json_obj(raw)

                new_rules = result.get("rules", "")
                new_efficiency = result.get("efficiency", "")

                if new_rules and check_no_markers(new_rules):
                    new_rules = enforce_rules_cap(new_rules, MAX_RULES_LINES)
                    working_content = substitute_between(
                        working_content, RULES_START, RULES_END, new_rules
                    )
                    changes.append("rules")

                if new_efficiency and check_no_markers(new_efficiency):
                    eff_lines = [l for l in new_efficiency.splitlines() if l.strip()]
                    if len(eff_lines) > MAX_EFFICIENCY_LINES:
                        log_event(repo_root, f"CLAUDE.MD WARN: efficiency section over {MAX_EFFICIENCY_LINES} lines")
                    working_content = substitute_between(
                        working_content, EFFICIENCY_START, EFFICIENCY_END, new_efficiency
                    )
                    changes.append("efficiency")

                pass1_ran = True
            except Exception as exc:
                log_event(repo_root, f"CLAUDE.MD ERROR (pass1): {exc}")
                # Continue to Pass 2 even if Pass 1 fails
    else:
        if dry_run:
            print("[dry-run] CLAUDE.md Pass 1: no new feedback or learnings, skipping")

    # --- Pass 2: Body sections ---
    last_body = read_body_state(repo_root)
    body_age_h = (
        (dt.datetime.now() - last_body).total_seconds() / 3600
        if last_body else float("inf")
    )

    if body_age_h > BODY_PASS_HOURS:
        me_files = collect_me_files(repo_root)
        decisions = collect_recent_decisions(repo_root)
        daily = collect_recent_daily(repo_root)
        operating_context = collect_operating_context(repo_root)
        current_body = extract_body(working_content) or ""

        parts = []
        parts.append(f"## LOCKED BLOCK (read-only)\n{LOCKED_START}{original_locked}{LOCKED_END}\n")
        parts.append(f"## CURRENT BODY\n{current_body.strip()}\n")
        if me_files:
            parts.append("## ME FILES\n")
            for name, content in me_files:
                parts.append(f"### {name}\n{content.strip()}\n")
        if decisions:
            parts.append(f"## RECENT DECISIONS (last 30 days)\n{decisions}\n")
        if daily:
            parts.append("## RECENT DAILY (last 14 days)\n")
            for name, content in daily:
                parts.append(f"### {name}\n{content.strip()}\n")
        if operating_context:
            parts.append("## BRAIN OPERATING CONTEXT\n")
            for name, content in operating_context:
                parts.append(f"### {name}\n{content.strip()}\n")

        payload = "\n".join(parts)

        if dry_run:
            print(f"[dry-run] CLAUDE.md Pass 2: body pass (last ran {body_age_h:.0f}h ago)")
        else:
            try:
                raw = call_haiku(BODY_PROMPT, payload)
                result = parse_json_obj(raw)
                new_body = result.get("body", "")

                if new_body and check_no_markers(new_body):
                    working_content = substitute_body(working_content, new_body)
                    changes.append("body")
                    pass2_ran = True
            except Exception as exc:
                log_event(repo_root, f"CLAUDE.MD ERROR (pass2): {exc}")
    else:
        if dry_run:
            print(f"[dry-run] CLAUDE.md Pass 2: skipped (last ran {body_age_h:.0f}h ago)")

    if dry_run or not changes:
        return

    # --- Validate before writing ---
    ok, err = validate_claude_content(working_content, original_locked)
    if not ok:
        log_event(repo_root, f"CLAUDE.MD ABORT: validation failed: {err}")
        return

    line_count = working_content.count("\n")
    if line_count > MAX_FILE_LINES:
        log_event(repo_root, f"CLAUDE.MD WARN: file is {line_count} lines (>{MAX_FILE_LINES})")

    # --- Write both files atomically ---
    claude_path.write_text(working_content)
    agents_path.write_text(working_content)

    if pass2_ran:
        write_body_state(repo_root, dt.datetime.now())

    log_event(
        repo_root,
        f"CLAUDE.MD UPDATED: sections changed={','.join(changes)} lines={line_count}",
    )


def main() -> None:
    if os.environ.get(RECURSION_ENV) == "1":
        sys.exit(0)

    p = argparse.ArgumentParser()
    p.add_argument("--since", type=str, help="ISO date to compile from (overrides state file)")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--no-commit", action="store_true", help="skip the daily auto-commit step")
    p.add_argument("--chunk-chars", type=int, default=DEFAULT_CHUNK_CHARS,
                   help=f"max chars of new material per run (default {DEFAULT_CHUNK_CHARS})")
    p.add_argument("--drain", action="store_true",
                   help="loop until the backlog is empty (each iteration is one chunked Haiku call)")
    p.add_argument("--focus", type=str, choices=["copywriting"],
                   help="restrict wiki output to a specific knowledge domain")
    args = p.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    try:
        _run_compile(repo_root, args)
    finally:
        if not args.dry_run and not args.no_commit:
            stamp_timezone(repo_root)
            auto_commit(repo_root)


def _run_compile(repo_root: Path, args: argparse.Namespace) -> None:

    if args.since:
        since = dt.datetime.fromisoformat(args.since)
    else:
        since = read_state(repo_root) or (dt.datetime.now() - dt.timedelta(days=30))

    # Capture pre-loop timestamp for CLAUDE.md update (feedback gating)
    original_since = since

    while True:
        new_material = collect_new_material(repo_root, since)

        if not new_material:
            if args.dry_run:
                print(f"[dry-run] COMPILE SKIP: no new material since {since.isoformat()}")
            else:
                log_event(repo_root, f"COMPILE SKIP: no new material since {since.isoformat()}")
                write_state(repo_root, dt.datetime.now())
            break

        chunk, remaining = chunk_by_chars(new_material, args.chunk_chars)
        chunk_last_mtime = chunk[-1][2]
        chunk_chars = sum(len(c) for _, c, _ in chunk)
        remaining_chars = sum(len(c) for _, c, _ in remaining)

        wiki_pages = collect_wiki(repo_root)
        operating_context = collect_operating_context(repo_root)
        wiki_index = read_index(repo_root)
        payload = build_payload(wiki_pages, chunk, operating_context, wiki_index)
        if len(payload) > MAX_INPUT_CHARS:
            payload = payload[:MAX_INPUT_CHARS]

        focus = getattr(args, "focus", None)
        if focus:
            prompt = FOCUS_ROUTE_PROMPT.replace(
                "__FOCUS_DEFINITION__", load_focus(repo_root, focus)
            )
        else:
            prompt = ROUTE_PROMPT
        prompt = cfg.render(prompt)
        try:
            raw = call_haiku(prompt, payload)
        except Exception as exc:
            log_event(repo_root, f"COMPILE ERROR: LLM call failed: {exc}")
            break

        actions = parse_actions(raw)
        valid = [a for a in actions if validate_action(a)][:MAX_CONCEPTS_PER_RUN]

        if args.dry_run:
            print(f"chunk: {len(chunk)} files, {chunk_chars} chars; remaining: {len(remaining)} files, {remaining_chars} chars")
            for a in valid:
                print(f"  [{a['action']}] {a['path']} ({len(a['content'])} chars)")
            if not args.drain or not remaining:
                break
            since = chunk_last_mtime
            continue

        touched: list[str] = []
        touched_actions: list[dict] = []
        for a in valid:
            target = repo_root / a["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            content = a["content"].replace(": ", ", ").replace("-", "-")
            target.write_text(content.rstrip() + "\n")
            touched.append(f"{a['action']}:{a['path']}")
            touched_actions.append(a)

        if touched_actions:
            update_index(repo_root, touched_actions)

        write_state(repo_root, chunk_last_mtime)
        if touched:
            log_event(
                repo_root,
                f"COMPILE OK: {len(chunk)} files ({chunk_chars} chars) → {len(touched)} wiki edits, {len(remaining)} files remaining "
                f"({', '.join(touched[:5])}{'...' if len(touched) > 5 else ''})",
            )
        else:
            log_event(
                repo_root,
                f"COMPILE OK: no actions proposed for {len(chunk)} files ({chunk_chars} chars), {len(remaining)} files remaining",
            )

        if not args.drain or not remaining:
            break
        since = chunk_last_mtime

    # Clear needs-compile marker -- compile ran regardless of what changed
    if not args.dry_run:
        needs_marker = repo_root / ".state" / "needs-compile"
        try:
            needs_marker.unlink(missing_ok=True)
        except Exception:
            pass

    # Always run the CLAUDE.md / AGENTS.md update, regardless of wiki outcome
    update_claude_agents_md(repo_root, original_since, args.dry_run)

    # Priority/comp shifts are NOT staged here anymore. They adapt live, in the
    # session where the owner states the change, via .claude/rules/priorities-auto-update.md
    # (one-tap confirm, me/ written same-session). The old propose_priorities.py
    # backstop staged a draft that surfaced at /reflect Phase H; /reflect was
    # simplified to dump + reflection + plan only, so that approval queue is gone.
    # Re-enable the block below if the live path proves to miss too much.


if __name__ == "__main__":
    main()
