#!/usr/bin/env python3
"""
maybe_compile.py - SessionStart hook. Spawns compile.py in the background if:
  - .state/last-compile.txt is older than 12 hours, OR
  - .state/needs-compile marker exists.

Returns immediately (~10ms) so it never blocks session startup.
"""

from __future__ import annotations

import datetime as dt
import os
import subprocess
import sys
from pathlib import Path

THRESHOLD_HOURS = 12
RECURSION_ENV = "BRAIN_FLUSH_RUNNING"


def main() -> None:
    if os.environ.get(RECURSION_ENV) == "1":
        sys.exit(0)

    repo_root = Path(__file__).resolve().parent.parent
    state_file = repo_root / ".state" / "last-compile.txt"
    needs_marker = repo_root / ".state" / "needs-compile"

    should_run = needs_marker.exists()

    if not should_run:
        if not state_file.exists():
            should_run = True
        else:
            try:
                last = dt.datetime.fromisoformat(state_file.read_text().strip())
                age = (dt.datetime.now() - last).total_seconds() / 3600
                if age > THRESHOLD_HOURS:
                    should_run = True
            except Exception:
                should_run = True

    if not should_run:
        sys.exit(0)

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


if __name__ == "__main__":
    main()
