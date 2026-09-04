#!/usr/bin/env python3
"""
brain_doctor.py -- how far along is this Brain, and what is broken?

Answers one question: what do I do next to make this thing actually work?

Runs entirely locally. No model call, no network. Prints a completeness score
out of 100 across five stages, then the single highest-value next action.

    python3 scripts/brain_doctor.py
    python3 scripts/brain_doctor.py --json
    python3 scripts/brain_doctor.py --verbose   # show every passing check too

The five stages are ordered by dependency: there is no point compiling a wiki
before there are sources, and no point ingesting sources before the Brain knows
whose sources they are. So the next action is always drawn from the earliest
stage that is not yet complete.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from brain_config import cfg, memory_dir  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

PLACEHOLDER = re.compile(r"not set yet|<!--|\{\{[A-Z_]+\}\}|^\s*$", re.M)


@dataclass
class Check:
    name: str
    ok: bool
    weight: int
    fix: str = ""
    detail: str = ""


@dataclass
class Stage:
    name: str
    blurb: str
    checks: list[Check] = field(default_factory=list)

    @property
    def score(self) -> int:
        total = sum(c.weight for c in self.checks) or 1
        got = sum(c.weight for c in self.checks if c.ok)
        return round(100 * got / total)

    @property
    def failures(self) -> list[Check]:
        return [c for c in self.checks if not c.ok]


def _text(rel: str) -> str:
    p = ROOT / rel
    return p.read_text(errors="replace") if p.exists() else ""


def _has_real_content(rel: str, min_words: int = 25) -> bool:
    """True when a file has been filled in, not just left as its template.

    Comment blocks and {{PLACEHOLDER}} slots are stripped before counting, so a
    file that still holds only its prompts scores as empty, which is correct.
    """
    body = PLACEHOLDER.sub(" ", _text(rel))
    body = re.sub(r"^#.*$", " ", body, flags=re.M)      # headings are template too
    body = re.sub(r"^>.*$", " ", body, flags=re.M)      # blockquote instructions
    return len(body.split()) >= min_words


def _count(glob: str, exclude_names: tuple[str, ...] = (".gitkeep", "README.md", "index.md")) -> int:
    return len([p for p in ROOT.glob(glob) if p.is_file() and p.name not in exclude_names])


def _git(*args: str) -> str:
    try:
        r = subprocess.run(["git", "-C", str(ROOT), *args],
                           capture_output=True, text=True, timeout=10)
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def stage_identity() -> Stage:
    s = Stage("1. Identity",
              "Does the Brain know whose it is? Nothing downstream works until it does.")
    s.checks += [
        Check("brain.config.json is filled in", cfg.is_configured, 5,
              "Run /onboard. It interviews you and writes this file."),
        Check("mission is set", "not set yet" not in str(cfg.mission), 5,
              "Run /onboard section 2. A Brain with no mission cannot filter anything."),
        Check("CLAUDE.md has no unfilled slots", "{{" not in _text("CLAUDE.md"), 4,
              "Replace the {{MISSION}} and {{OWNER_PARAGRAPH}} slots in CLAUDE.md."),
        Check("AGENTS.md mirrors CLAUDE.md",
              _text("CLAUDE.md") == _text("AGENTS.md"), 2,
              "cp CLAUDE.md AGENTS.md -- they must stay byte-identical."),
        Check("me/me.md written", _has_real_content("me/me.md"), 4,
              "Run /onboard section 1."),
        Check("me/work.md written", _has_real_content("me/work.md"), 3,
              "Run /onboard section 3. The Brain is useless if it does not know how you get paid."),
        Check("me/priorities.md written", _has_real_content("me/priorities.md"), 4,
              "Run /onboard section 4."),
        Check("favorite problems listed",
              _has_real_content("areas/favorite-problems.md", min_words=40), 3,
              "Run /onboard section 5. This is the filter for what the Brain notices."),
        Check("voice rule is yours, not the default",
              "placeholder with sensible defaults" not in _text(".claude/rules/communication-style.md"), 2,
              "Run /onboard section 6. Paste three things you actually wrote."),
    ]
    return s


def stage_capture() -> Stage:
    s = Stage("2. Capture",
              "Is real material coming in? A Brain with no sources has nothing to think with.")
    src = _count("sources/**/*.md")
    daily = _count("daily/*.md")
    recent = 0
    cutoff = dt.date.today() - dt.timedelta(days=14)
    for p in (ROOT / "daily").glob("*.md"):
        m = re.match(r"(\d{4}-\d{2}-\d{2})", p.name)
        if m:
            try:
                if dt.date.fromisoformat(m.group(1)) >= cutoff:
                    recent += 1
            except ValueError:
                pass
    s.checks += [
        Check("at least one source ingested", src >= 1, 4,
              "Run /pull <url> on something you wrote. Your own writing first.",
              f"{src} source files"),
        Check("10+ sources", src >= 10, 3,
              "Keep pulling. See docs/03-getting-your-stuff-in.md for bulk backfills.",
              f"{src} source files"),
        Check("50+ sources", src >= 50, 2,
              "Backfill an archive: your notes app, your published writing, your call transcripts.",
              f"{src} source files"),
        Check("daily capture has started", daily >= 1, 4,
              "Run /reflect at the end of a working day.",
              f"{daily} daily files"),
        Check("daily capture is live (last 14 days)", recent >= 3, 4,
              "Run /action in the morning and /reflect at night. The loop needs daily files to compile.",
              f"{recent} daily files in the last 14 days"),
    ]
    return s


def stage_connections() -> Stage:
    s = Stage("3. Connections",
              "Can the Brain reach the systems where your real work already lives?")
    conn = _text("connections.md")
    rows = [ln for ln in conn.splitlines()
            if ln.startswith("|") and "---" not in ln
            and not ln.startswith("| Domain") and "_example_" not in ln]
    env_ok = (ROOT / ".env").exists()
    s.checks += [
        Check("at least one system wired", len(rows) >= 1, 5,
              "Run /connect <tool>. Start with wherever your own writing lives.",
              f"{len(rows)} connection rows"),
        Check("three or more systems wired", len(rows) >= 3, 3,
              "Run /connect again. Notes, calendar, and whatever holds the money.",
              f"{len(rows)} connection rows"),
        Check(".env exists for credentials", env_ok, 2,
              "cp .env.example .env and fill in what you use."),
        Check(".env is gitignored", ".env" in _text(".gitignore"), 3,
              "CRITICAL: add .env to .gitignore before you commit anything."),
        Check("no secrets pasted into connections.md",
              not re.search(r"(sk-|ghp_|xox[baprs]-|AIza|Bearer\s+\w{20,})", conn), 5,
              "CRITICAL: remove the credential from connections.md and rotate it. "
              "That file names env vars, never values."),
    ]
    return s


def stage_synthesis() -> Stage:
    s = Stage("4. Synthesis",
              "Is raw capture turning into knowledge you can query?")
    pages = _count("wiki/**/*.md")
    last_compile = _text(".state/last-compile.txt").strip()
    fresh = False
    if last_compile:
        try:
            age = (dt.datetime.now() - dt.datetime.fromisoformat(last_compile)).days
            fresh = age <= 7
        except ValueError:
            pass
    embeds = (ROOT / ".state" / "wiki-embeddings.npy").exists()
    s.checks += [
        Check("compile has run", bool(last_compile), 4,
              "Run python3 scripts/compile.py once there are sources and daily files.",
              f"last compile: {last_compile or 'never'}"),
        Check("compile ran in the last 7 days", fresh, 3,
              "The SessionStart hook runs this automatically. If it has not, check .state/compile.err."),
        Check("wiki has pages", pages >= 1, 4, "Run python3 scripts/compile.py.",
              f"{pages} wiki pages"),
        Check("wiki has 20+ pages", pages >= 20, 2,
              "Keep feeding sources. Pages accumulate as material does.",
              f"{pages} wiki pages"),
        Check("semantic search index built", embeds, 3,
              "Run python3 scripts/wiki_embed.py. Without it, wiki_search.py cannot run "
              "and skills fall back to loading whole files."),
    ]
    return s


def stage_loop() -> Stage:
    s = Stage("5. The self-improving loop",
              "Is the Brain learning from corrections without you maintaining it?")
    mem = memory_dir()
    feedback = len(list(mem.glob("feedback_*.md"))) if mem.exists() else 0
    rules_body = ""
    claude = _text("CLAUDE.md")
    m = re.search(r"<!-- compile:rules start -->(.*?)<!-- compile:rules end -->", claude, re.S)
    if m:
        rules_body = m.group(1)
    hooks_ok = "SessionEnd" in _text(".claude/settings.json")
    decisions = len(re.findall(r"^## \d{4}-\d{2}-\d{2}", _text("decisions/log.md"), re.M))
    s.checks += [
        Check("hooks are wired", hooks_ok, 4,
              "Check .claude/settings.json. Without hooks nothing runs on its own."),
        Check("feedback memories exist", feedback >= 1, 4,
              "Correct the agent when it is wrong and tell it to save the rule. "
              "See .claude/rules/learn-from-corrections.md.",
              f"{feedback} feedback memories in {mem}"),
        Check("5+ feedback memories", feedback >= 5, 2, "Keep correcting. This is how it gets sharp.",
              f"{feedback} feedback memories"),
        Check("Learned Rules section is populating",
              "It starts empty" not in rules_body and len(rules_body.split()) > 30, 3,
              "compile.py writes this from your feedback memories. Needs memories first."),
        Check("decisions are being logged", decisions >= 1, 3,
              "Append a dated entry to decisions/log.md the next time you decide something real.",
              f"{decisions} decisions logged"),
    ]
    return s


def env_warnings() -> list[str]:
    out = []
    if not shutil.which("git"):
        out.append("git is not installed. sync.py cannot run.")
    elif not _git("rev-parse", "--git-dir"):
        out.append("not a git repo. Run: git init && git remote add origin <url>")
    elif not _git("remote"):
        out.append("no git remote. Device sync and backup are off. Add one with: git remote add origin <url>")
    if sys.version_info < (3, 10):
        out.append(f"Python {sys.version_info.major}.{sys.version_info.minor} is too old. Scripts need 3.10+.")
    if not (shutil.which("claude") or shutil.which("codex")):
        out.append("neither the `claude` nor `codex` CLI is on PATH. compile.py needs one of them.")
    try:
        import numpy  # noqa: F401
    except ImportError:
        out.append("numpy is not installed. wiki_search.py needs it: pip3 install numpy")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()

    stages = [stage_identity(), stage_capture(), stage_connections(),
              stage_synthesis(), stage_loop()]
    overall = round(sum(s.score for s in stages) / len(stages))
    warnings = env_warnings()

    if args.json:
        print(json.dumps({
            "score": overall,
            "stages": [{"name": s.name, "score": s.score,
                        "failures": [{"check": c.name, "fix": c.fix, "detail": c.detail}
                                     for c in s.failures]} for s in stages],
            "environment_warnings": warnings,
        }, indent=2))
        return 0

    bar = lambda n: "#" * (n // 10) + "." * (10 - n // 10)  # noqa: E731
    print()
    print(f"  BRAIN COMPLETENESS   {overall}/100   [{bar(overall)}]")
    print()
    for s in stages:
        print(f"  {s.name:<32} {s.score:>3}/100  [{bar(s.score)}]")
        print(f"     {s.blurb}")
        for c in s.checks:
            if c.ok and not args.verbose:
                continue
            mark = "ok  " if c.ok else "MISS"
            extra = f"  ({c.detail})" if c.detail else ""
            print(f"     [{mark}] {c.name}{extra}")
            if not c.ok and c.fix:
                print(f"            -> {c.fix}")
        print()

    if warnings:
        print("  ENVIRONMENT")
        for w in warnings:
            print(f"     [WARN] {w}")
        print()

    # The next action always comes from the earliest incomplete stage, because
    # the stages are dependency-ordered. Fixing stage 4 while stage 1 is empty
    # produces a wiki about nobody.
    for s in stages:
        if s.failures:
            top = max(s.failures, key=lambda c: c.weight)
            print(f"  NEXT: {top.fix}")
            print(f"        (unblocks {s.name})")
            print()
            break
    else:
        print("  NEXT: nothing. The Brain is fully set up. Go use it.")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
