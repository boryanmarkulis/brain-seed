#!/usr/bin/env python3
"""
session_end_post.py - writes .state/needs-compile marker at session end.

The existing launchd job picks it up on next fire. Keeps compile non-blocking.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

BRAIN_DIR = Path(__file__).parent.parent
STATE_FILE = BRAIN_DIR / ".state" / "needs-compile"
LOG_FILE = BRAIN_DIR / "log.md"


def main() -> None:
    # Read hook payload if available (may be empty in manual runs)
    try:
        payload = json.loads(sys.stdin.read().strip() or "{}")
    except Exception:
        payload = {}

    now = dt.datetime.now(dt.timezone.utc).isoformat()
    STATE_FILE.write_text(now + "\n")

    today = dt.date.today().isoformat()
    with open(LOG_FILE, "a") as f:
        f.write(f"[{today}] NEEDS-COMPILE: session ended\n")


if __name__ == "__main__":
    main()
