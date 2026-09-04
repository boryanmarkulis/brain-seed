#!/usr/bin/env python3
"""
activator.py - UserPromptSubmit hook.

1. Correction signals: injects a system note reminding the agent to log the
   error to learnings/ before responding.
2. Heartbeat: if .state/last-compile.txt is older than 4 hours, spawns
   compile.py in a detached background process. Stays well inside the 2s hook
   timeout - spawn and return immediately.

Exits silently on normal turns with no match - zero overhead.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path

RECURSION_ENV = "BRAIN_FLUSH_RUNNING"

CORRECTION_SIGNALS = [
    "that didn't work",
    "didn't work",
    "that's wrong",
    "that's not right",
    "that is wrong",
    "that is not right",
    "no that's",
    "you made a mistake",
    "correct that",
    "fix that",
    "not what i wanted",
    "not what i asked",
    "try again",
    "you got it wrong",
    "wrong answer",
    "that failed",
    "it failed",
    "you're wrong",
    "you are wrong",
    "that's incorrect",
    "that is incorrect",
]

INJECTION = (
    "SYSTEM NOTE: A correction or failure was detected in this message. "
    "Before responding, if a skill was active or something failed, call: "
    "python3 scripts/capture_learning.py --type ERR "
    '--note "brief description" [--skill "skill-name"]. '
    "Then continue with your normal response."
)

HEARTBEAT_HOURS = 4


def maybe_spawn_compile(repo_root: Path) -> None:
    """Spawn compile.py in the background if last compile is older than HEARTBEAT_HOURS."""
    state_file = repo_root / ".state" / "last-compile.txt"
    if not state_file.exists():
        return
    try:
        last = dt.datetime.fromisoformat(state_file.read_text().strip())
        age = (dt.datetime.now() - last).total_seconds() / 3600
        if age <= HEARTBEAT_HOURS:
            return
    except Exception:
        return

    env = os.environ.copy()
    env[RECURSION_ENV] = "1"
    log_out = str(repo_root / ".state" / "compile.log")
    log_err = str(repo_root / ".state" / "compile.err")
    try:
        with open(log_out, "a") as out, open(log_err, "a") as err:
            subprocess.Popen(
                [sys.executable, str(repo_root / "scripts" / "compile.py")],
                stdout=out,
                stderr=err,
                start_new_session=True,
                env=env,
                cwd=str(repo_root),
            )
    except Exception:
        pass


def main() -> None:
    if os.environ.get(RECURSION_ENV) == "1":
        sys.exit(0)

    try:
        raw = sys.stdin.read().strip()
        payload = json.loads(raw) if raw else {}
    except Exception:
        sys.exit(0)

    prompt = payload.get("prompt") or payload.get("message") or ""
    if not isinstance(prompt, str):
        sys.exit(0)

    repo_root = Path(__file__).resolve().parent.parent
    maybe_spawn_compile(repo_root)

    prompt_lower = prompt.lower()
    if not any(signal in prompt_lower for signal in CORRECTION_SIGNALS):
        sys.exit(0)

    # Output the injection as a hook message
    # Claude Code UserPromptSubmit hooks can inject via stdout as JSON
    print(json.dumps({"type": "inject", "content": INJECTION}))


if __name__ == "__main__":
    main()
