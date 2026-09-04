#!/usr/bin/env python3
"""
evolve.py - session-end skill evolution engine.

Fires via SessionEnd hook. Reviews learnings/ for patterns and proposes new
or updated skills via a Haiku call when thresholds are crossed.

Three triggers:
  A. 5+ sequential tool calls in this session → log FEAT entry
  B. Same tool-name pattern in 2+ sessions, 3+ total occurrences → skill candidate
  C. Same error pattern in 2+ occurrences → skill-update candidate

Only calls Haiku when at least one trigger fires.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

BRAIN_DIR = Path(__file__).parent.parent
RECURSION_ENV = "BRAIN_FLUSH_RUNNING"
MODEL = "claude-haiku-4-5-20251001"
STATE_FILE = BRAIN_DIR / ".state" / "learnings-state.json"
LAST_EVOLVE_FILE = BRAIN_DIR / ".state" / "last-evolve.txt"
LOG_FILE = BRAIN_DIR / "log.md"
CANDIDATES_FILE = BRAIN_DIR / "learnings" / "SKILL-CANDIDATES.md"
ERRORS_FILE = BRAIN_DIR / "learnings" / "ERRORS.md"
SKILLS_DIR = BRAIN_DIR / ".claude" / "skills"

TRANSCRIPT_WAIT_TRIES = 30
TRANSCRIPT_WAIT_SECONDS = 1.0

# Thresholds
FEAT_MIN_TOOL_CALLS = 5
SKILL_CANDIDATE_MIN_COUNT = 3
SKILL_CANDIDATE_MIN_SESSIONS = 2
ERROR_CANDIDATE_MIN_COUNT = 2
RECURRENCE_WINDOW_DAYS = 30


def log_event(msg: str) -> None:
    try:
        today = dt.date.today().isoformat()
        with LOG_FILE.open("a") as f:
            f.write(f"[{today}] {msg}\n")
    except Exception:
        pass


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {"counter": {"LRN": 0, "ERR": 0, "FEAT": 0}, "patterns": {}}


def pattern_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:8]


def read_transcript(path: Path) -> list[dict]:
    """Read Claude Code JSONL transcript. Returns list of {role, tool_name} dicts."""
    events = []
    try:
        for line in path.read_text(errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            role = obj.get("role", "")
            content = obj.get("content") or []

            if role == "user":
                # Extract the user message text for context
                text_parts = []
                if isinstance(content, list):
                    for part in content:
                        if isinstance(part, dict) and part.get("type") == "text":
                            t = part.get("text", "")
                            if t and not t.startswith("<local-command"):
                                text_parts.append(t[:200])
                elif isinstance(content, str):
                    text_parts.append(content[:200])
                if text_parts:
                    events.append({"role": "user", "text": " ".join(text_parts)})

            elif role == "assistant":
                if isinstance(content, list):
                    for part in content:
                        if isinstance(part, dict) and part.get("type") == "tool_use":
                            events.append({
                                "role": "tool",
                                "tool_name": part.get("name", "unknown"),
                            })
    except Exception:
        pass
    return events


def find_tool_sequences(events: list[dict]) -> list[dict]:
    """Find runs of 5+ consecutive tool calls. Returns list of sequence dicts."""
    sequences = []
    i = 0
    while i < len(events):
        if events[i]["role"] != "tool":
            i += 1
            continue

        # Start of a tool run
        run_start = i
        tool_names = []
        context_before = ""

        # Grab the last user message before this run
        for j in range(run_start - 1, max(run_start - 5, -1), -1):
            if events[j]["role"] == "user":
                context_before = events[j].get("text", "")
                break

        while i < len(events) and events[i]["role"] == "tool":
            tool_names.append(events[i]["tool_name"])
            i += 1

        if len(tool_names) >= FEAT_MIN_TOOL_CALLS:
            sequences.append({
                "tool_names": tool_names,
                "context": context_before,
                "length": len(tool_names),
            })

    return sequences


def capture_feat(seq: dict, session_id: str) -> str:
    """Log a FEAT entry. Returns the pattern hash."""
    steps = ",".join(seq["tool_names"])
    env = os.environ.copy()
    env[RECURSION_ENV] = "1"
    try:
        subprocess.run(
            [
                "python3",
                str(BRAIN_DIR / "scripts" / "capture_learning.py"),
                "--type", "FEAT",
                "--note", f"Tool sequence of {seq['length']} calls detected in session {session_id}",
                "--steps", steps,
                "--context", seq["context"][:300] if seq["context"] else "",
                "--session", session_id,
            ],
            env=env, timeout=5, capture_output=True, text=True,
        )
    except Exception:
        pass
    return pattern_hash(f"FEAT:{steps}")


def get_skill_candidates(state: dict) -> list[dict]:
    """Find patterns that cross the skill candidate threshold."""
    cutoff = (dt.date.today() - dt.timedelta(days=RECURRENCE_WINDOW_DAYS)).isoformat()
    candidates = []
    for phash, data in state.get("patterns", {}).items():
        if data.get("last_seen", "") < cutoff:
            continue
        count = data.get("count", 0)
        sessions = len(data.get("sessions", []))
        ids = data.get("ids", [])
        entry_type = ids[0].split("-")[0] if ids else ""

        if entry_type == "FEAT" and count >= SKILL_CANDIDATE_MIN_COUNT and sessions >= SKILL_CANDIDATE_MIN_SESSIONS:
            candidates.append({"type": "skill_create", "hash": phash, "count": count, "ids": ids})
        elif entry_type == "ERR" and count >= ERROR_CANDIDATE_MIN_COUNT:
            candidates.append({"type": "skill_update", "hash": phash, "count": count, "ids": ids})

    return candidates


def read_skill_inventory() -> list[dict]:
    """Return list of {name, description} for existing skills."""
    skills = []
    if not SKILLS_DIR.exists():
        return skills
    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.exists():
            continue
        try:
            text = skill_file.read_text()
            name = skill_dir.name
            description = ""
            in_frontmatter = False
            for line in text.splitlines():
                if line.strip() == "---":
                    in_frontmatter = not in_frontmatter
                    continue
                if in_frontmatter and line.startswith("description:"):
                    description = line[len("description:"):].strip().strip('"')
                    break
            skills.append({"name": name, "description": description})
        except Exception:
            continue
    return skills


def read_candidate_entries(ids: list[str], source_file: Path) -> str:
    """Extract specific entries from a learnings file by ID."""
    if not source_file.exists():
        return ""
    text = source_file.read_text()
    sections = []
    current_id = None
    current_lines = []
    for line in text.splitlines():
        if line.startswith("### "):
            if current_id and current_id in ids:
                sections.append("\n".join(current_lines))
            current_id = line.split(" · ")[0].replace("### ", "").strip()
            current_lines = [line]
        elif current_id:
            current_lines.append(line)
    if current_id and current_id in ids:
        sections.append("\n".join(current_lines))
    return "\n\n".join(sections[:3])  # Cap at 3 examples


def call_haiku(prompt: str) -> str:
    env = os.environ.copy()
    env[RECURSION_ENV] = "1"
    try:
        result = subprocess.run(
            ["claude", "-p", "--model", MODEL, prompt],
            capture_output=True, text=True, timeout=90, env=env,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return ""


def write_draft_skill(name: str, content: str) -> None:
    skill_dir = SKILLS_DIR / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text(content)


def update_skill(name: str, section_content: str, rationale: str) -> None:
    skill_dir = SKILLS_DIR / name
    skill_file = skill_dir / "SKILL.md"
    if not skill_file.exists():
        return
    existing = skill_file.read_text()
    addition = f"\n\n## Auto-Update · {dt.date.today().isoformat()}\n\n{rationale}\n\n{section_content}\n"
    skill_file.write_text(existing.rstrip() + addition)


def main() -> None:
    if os.environ.get(RECURSION_ENV) == "1":
        sys.exit(0)

    try:
        raw = sys.stdin.read().strip()
        payload = json.loads(raw) if raw else {}
    except Exception:
        payload = {}

    transcript_path_str = payload.get("transcript_path", "")
    session_id = payload.get("session_id", "unknown")[:12]
    today = dt.date.today().isoformat()

    triggered = []

    # --- Trigger A: detect 5+ tool call sequences in this session ---
    if transcript_path_str:
        transcript_path = Path(transcript_path_str)
        for _ in range(TRANSCRIPT_WAIT_TRIES):
            if transcript_path.exists():
                break
            time.sleep(TRANSCRIPT_WAIT_SECONDS)

        if transcript_path.exists():
            events = read_transcript(transcript_path)
            sequences = find_tool_sequences(events)
            for seq in sequences:
                phash = capture_feat(seq, session_id)
                triggered.append(f"FEAT: {seq['length']}-call sequence ({phash})")

    # --- Reload state after potential FEAT writes ---
    state = load_state()

    # --- Trigger B & C: check recurrence thresholds ---
    candidates = get_skill_candidates(state)
    for c in candidates:
        triggered.append(f"{c['type']}: hash {c['hash']} count={c['count']}")

    if not triggered:
        LAST_EVOLVE_FILE.write_text(dt.datetime.now(dt.timezone.utc).isoformat() + "\n")
        log_event(f"EVOLVE SKIP: no patterns above threshold (session {session_id})")
        sys.exit(0)

    # --- Build Haiku prompt ---
    skills = read_skill_inventory()
    skills_list = "\n".join(f"- {s['name']}: {s['description']}" for s in skills)

    # Gather candidate entries text
    candidate_context_parts = []
    for c in candidates:
        source = CANDIDATES_FILE if c["type"] == "skill_create" else ERRORS_FILE
        entries = read_candidate_entries(c["ids"], source)
        if entries:
            candidate_context_parts.append(f"[{c['type']} hash={c['hash']}]\n{entries}")
    candidate_context = "\n\n---\n\n".join(candidate_context_parts)

    prompt = f"""You are reviewing repeated patterns captured by a second brain to decide whether to create or update skills.

TRIGGERED PATTERNS:
{chr(10).join(triggered)}

CANDIDATE ENTRIES:
{candidate_context or "(see pattern hashes above)"}

EXISTING SKILLS:
{skills_list}

For each triggered pattern, decide:
- CREATE: workflow that doesn't exist as a skill
- UPDATE: add this pattern to an existing skill
- SKIP: too session-specific to generalize

Output ONLY a JSON array. Each item must have these exact fields:
{{"action": "create", "skill_name": "kebab-name", "content": "FULL SKILL.md content including frontmatter", "rationale": "one sentence"}}
{{"action": "update", "skill_name": "existing-skill-name", "content": "section content to append", "rationale": "one sentence"}}
{{"action": "skip", "skill_name": "", "content": "", "rationale": "one sentence"}}

For CREATE, the SKILL.md frontmatter must include:
---
name: kebab-name
description: one-liner
auto-created: {today}
trigger-count: N
review-status: draft
allowed-tools: Read Write Edit Bash
---

Output ONLY the JSON array. No explanation, no markdown fences."""

    response = call_haiku(prompt)

    if not response:
        LAST_EVOLVE_FILE.write_text(dt.datetime.now(dt.timezone.utc).isoformat() + "\n")
        log_event(f"EVOLVE ERROR: Haiku call failed (session {session_id})")
        sys.exit(0)

    # Parse and act on the response
    try:
        # Strip potential markdown fences
        clean = response.strip()
        if clean.startswith("```"):
            clean = "\n".join(clean.split("\n")[1:])
            if clean.endswith("```"):
                clean = clean[: clean.rfind("```")]
        actions = json.loads(clean)
    except json.JSONDecodeError:
        LAST_EVOLVE_FILE.write_text(dt.datetime.now(dt.timezone.utc).isoformat() + "\n")
        log_event(f"EVOLVE ERROR: could not parse Haiku response (session {session_id})")
        sys.exit(0)

    created = 0
    updated = 0
    for action in actions:
        act = action.get("action", "skip")
        name = action.get("skill_name", "")
        content = action.get("content", "")
        rationale = action.get("rationale", "")

        if act == "create" and name and content:
            write_draft_skill(name, content)
            created += 1
            log_event(f"EVOLVE CREATE: .claude/skills/{name}/SKILL.md (draft) - {rationale}")
        elif act == "update" and name and content:
            update_skill(name, content, rationale)
            updated += 1
            log_event(f"EVOLVE UPDATE: .claude/skills/{name}/SKILL.md - {rationale}")
        else:
            log_event(f"EVOLVE SKIP: {rationale}")

    LAST_EVOLVE_FILE.write_text(dt.datetime.now(dt.timezone.utc).isoformat() + "\n")
    log_event(
        f"EVOLVE OK: {len(triggered)} triggers, {created} skills created, {updated} updated "
        f"(session {session_id})"
    )


if __name__ == "__main__":
    main()
