#!/usr/bin/env python3
"""
capture_learning.py - foundation script for all learning capture.

Called by hooks (error_detector.py, activator.py) and by the agent directly.

Usage:
  python3 scripts/capture_learning.py --type LRN --note "description"
  python3 scripts/capture_learning.py --type ERR --note "description" [--skill "skill-name"]
  python3 scripts/capture_learning.py --type ERR --auto          # reads error from stdin
  python3 scripts/capture_learning.py --type FEAT --note "desc" --steps "Read,Edit,Bash" --context "user was doing X"
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

BRAIN_DIR = Path(__file__).parent.parent
STATE_FILE = BRAIN_DIR / ".state" / "learnings-state.json"
LOG_FILE = BRAIN_DIR / "log.md"

LEARNINGS_FILE = BRAIN_DIR / "learnings" / "LEARNINGS.md"
ERRORS_FILE = BRAIN_DIR / "learnings" / "ERRORS.md"
CANDIDATES_FILE = BRAIN_DIR / "learnings" / "SKILL-CANDIDATES.md"

TYPE_TO_FILE = {
    "LRN": LEARNINGS_FILE,
    "ERR": ERRORS_FILE,
    "FEAT": CANDIDATES_FILE,
}


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"counter": {"LRN": 0, "ERR": 0, "FEAT": 0}, "patterns": {}}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2) + "\n")


def next_id(state: dict, entry_type: str) -> str:
    state["counter"][entry_type] += 1
    n = state["counter"][entry_type]
    date_str = dt.date.today().strftime("%Y%m%d")
    return f"{entry_type}-{date_str}-{n:03d}"


def pattern_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:8]


def update_recurrence(state: dict, phash: str, entry_id: str, session_id: str | None) -> int:
    if phash not in state["patterns"]:
        state["patterns"][phash] = {
            "count": 0,
            "sessions": [],
            "ids": [],
            "first_seen": dt.date.today().isoformat(),
            "last_seen": dt.date.today().isoformat(),
        }
    p = state["patterns"][phash]
    p["count"] += 1
    p["last_seen"] = dt.date.today().isoformat()
    p["ids"].append(entry_id)
    if session_id and session_id not in p["sessions"]:
        p["sessions"].append(session_id)
    return p["count"]


def append_to_log(entry_id: str) -> None:
    today = dt.date.today().isoformat()
    line = f"[{today}] LEARNING CAPTURED: {entry_id}\n"
    with open(LOG_FILE, "a") as f:
        f.write(line)


def write_lrn_entry(entry_id: str, note: str, phash: str, recurrence: int) -> None:
    today = dt.date.today().isoformat()
    section = f"""
### {entry_id} · {today}
{note}

**Pattern hash:** {phash}
**Recurrence:** {recurrence}
**Promoted:** false

---
"""
    with open(LEARNINGS_FILE, "a") as f:
        f.write(section)


def write_err_entry(entry_id: str, note: str, phash: str, recurrence: int,
                    skill: str | None, error_excerpt: str | None) -> None:
    today = dt.date.today().isoformat()
    lines = [f"\n### {entry_id} · {today}", note, ""]
    if error_excerpt:
        excerpt = error_excerpt[:500].strip()
        lines += [f"**Error excerpt:** `{excerpt}`", ""]
    if skill:
        lines += [f"**Skill active:** {skill}", ""]
    lines += [
        f"**Pattern hash:** {phash}",
        f"**Recurrence:** {recurrence}",
        "**Promoted:** false",
        "",
        "---",
        "",
    ]
    with open(ERRORS_FILE, "a") as f:
        f.write("\n".join(lines))


def write_feat_entry(entry_id: str, note: str, phash: str, recurrence: int,
                     steps: str | None, context: str | None) -> None:
    today = dt.date.today().isoformat()
    seq = steps.replace(",", " → ") if steps else ""
    lines = [f"\n### {entry_id} · {today}", note, ""]
    if seq:
        lines += [f"**Tool sequence:** {seq}", ""]
    if context:
        lines += [f"**Context:** {context}", ""]
    lines += [
        f"**Pattern hash:** {phash}",
        f"**Recurrence:** {recurrence}",
        "**Promoted:** false",
        "",
        "---",
        "",
    ]
    with open(CANDIDATES_FILE, "a") as f:
        f.write("\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--type", required=True, choices=["LRN", "ERR", "FEAT"])
    parser.add_argument("--note", default="")
    parser.add_argument("--auto", action="store_true",
                        help="Read error text from stdin (ERR type only)")
    parser.add_argument("--skill", default=None)
    parser.add_argument("--steps", default=None,
                        help="Comma-separated tool names for FEAT entries")
    parser.add_argument("--context", default=None,
                        help="Surrounding user message context for FEAT entries")
    parser.add_argument("--session", default=None)
    args = parser.parse_args()

    note = args.note
    error_excerpt = None

    if args.auto and args.type == "ERR":
        error_excerpt = sys.stdin.read().strip()
        if not note:
            note = f"Auto-captured bash error: {error_excerpt[:120]}"

    if not note and not error_excerpt:
        print("capture_learning: nothing to capture (no --note and no stdin)", file=sys.stderr)
        sys.exit(1)

    # Build hash content from what's stable (type + note/steps, not date)
    hash_content = f"{args.type}:{note or ''}{args.steps or ''}"
    phash = pattern_hash(hash_content)

    state = load_state()
    entry_id = next_id(state, args.type)
    recurrence = update_recurrence(state, phash, entry_id, args.session)
    save_state(state)

    if args.type == "LRN":
        write_lrn_entry(entry_id, note, phash, recurrence)
    elif args.type == "ERR":
        write_err_entry(entry_id, note, phash, recurrence, args.skill, error_excerpt)
    elif args.type == "FEAT":
        write_feat_entry(entry_id, note, phash, recurrence, args.steps, args.context)

    append_to_log(entry_id)
    print(f"captured: {entry_id} (recurrence: {recurrence})")


if __name__ == "__main__":
    main()
