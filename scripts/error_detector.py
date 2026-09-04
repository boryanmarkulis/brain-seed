#!/usr/bin/env python3
"""
error_detector.py - PostToolUse Bash hook. Reads tool output, pattern-matches
for errors, and captures to learnings/ERRORS.md via capture_learning.py.

Fast - no Haiku, exits in <0.5s.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

BRAIN_DIR = Path(__file__).parent.parent
RECURSION_ENV = "BRAIN_FLUSH_RUNNING"

ERROR_PATTERNS = [
    r"Traceback \(most recent call last\)",
    r"\bError:",
    r"\berror:",
    r"\bFAILED\b",
    r"exit code [1-9]",
    r"command not found",
    r"No such file or directory",
    r"ModuleNotFoundError",
    r"SyntaxError",
    r"KeyError",
    r"TypeError",
    r"AttributeError",
    r"Permission denied",
    r"ENOENT",
    r"npm ERR!",
]

_COMPILED = [re.compile(p) for p in ERROR_PATTERNS]


def extract_error_text(payload: dict) -> str | None:
    """Pull tool output text from the PostToolUse payload."""
    # Claude Code PostToolUse payload shape: {"tool_name": ..., "tool_input": ..., "tool_response": ...}
    response = payload.get("tool_response") or payload.get("output") or ""

    if isinstance(response, dict):
        # May be {"type": "tool_result", "content": [...]}
        content = response.get("content") or response.get("output") or ""
        if isinstance(content, list):
            parts = []
            for c in content:
                if isinstance(c, dict) and c.get("type") == "text":
                    parts.append(c.get("text", ""))
                elif isinstance(c, str):
                    parts.append(c)
            return "\n".join(parts)
        if isinstance(content, str):
            return content
        return str(response)

    if isinstance(response, list):
        parts = []
        for c in response:
            if isinstance(c, dict):
                parts.append(c.get("text") or c.get("output") or "")
            elif isinstance(c, str):
                parts.append(c)
        return "\n".join(parts)

    return str(response) if response else None


def main() -> None:
    if os.environ.get(RECURSION_ENV) == "1":
        sys.exit(0)

    try:
        raw = sys.stdin.read().strip()
        payload = json.loads(raw) if raw else {}
    except Exception:
        sys.exit(0)

    output = extract_error_text(payload)
    if not output:
        sys.exit(0)

    # Check for error patterns
    matched = any(p.search(output) for p in _COMPILED)
    if not matched:
        sys.exit(0)

    # Capture the error
    excerpt = output.strip()[:500]
    env = os.environ.copy()
    env[RECURSION_ENV] = "1"

    try:
        subprocess.run(
            ["python3", str(BRAIN_DIR / "scripts" / "capture_learning.py"),
             "--type", "ERR", "--auto"],
            input=excerpt,
            text=True,
            env=env,
            timeout=5,
            capture_output=True,
        )
    except Exception:
        pass


if __name__ == "__main__":
    main()
