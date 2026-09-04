#!/usr/bin/env python3
"""
health_check.py - SessionStart hook. Surfaces silently-failing background
background automations (git push, sync, backup, compile, any exporter you
add) so they never rot unnoticed. The failure mode this exists to kill: a
nightly job starts failing, writes to a log nobody opens, and 500 silent
failures later you discover the Brain stopped syncing weeks ago.

Which log markers to watch comes from `health_checks` in brain.config.json,
so adding your own background job means adding one entry there, not editing
this file.

Prints nothing when everything is healthy. On a problem, prints one short
line per issue. Never blocks the session: wrapped in a top-level try/except,
always exits 0.
"""

from __future__ import annotations

import datetime as dt
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from brain_config import cfg  # noqa: E402

ERR_STALE_HOURS = 48


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def check_push_log(root: Path) -> list[str]:
    """Look at the tail of .git/push.log for the latest status of each
    configured check. The file only grows (appended every commit) and can
    reach multiple MB, so read the tail rather than the whole file."""
    log_path = root / ".git" / "push.log"
    if not log_path.exists():
        return []

    # push.log is append-only and currently a few MB; read enough of the tail
    # to span the longest realistic failure streak. If this file grows much
    # larger over time, revisit (e.g. a bookmark file) rather than reading
    # the whole thing every session.
    tail = _tail_lines(log_path, max_bytes=4_000_000)

    warnings: list[str] = []
    for check in cfg.get("health_checks") or []:
        label = check.get("label", "background job")
        ok_marker = check.get("ok")
        fail_marker = check.get("fail")
        if not (ok_marker and fail_marker):
            continue
        last_status, since, streak = _last_status(tail, ok_marker, fail_marker)
        if last_status == "FAILED":
            warnings.append(
                f"BRAIN HEALTH: {label} failing since {since} "
                f"({streak} consecutive failures) - see .git/push.log"
            )
    return warnings


def _tail_lines(path: Path, max_bytes: int) -> list[str]:
    size = path.stat().st_size
    with path.open("rb") as f:
        if size > max_bytes:
            f.seek(size - max_bytes)
        data = f.read()
    return data.decode(errors="replace").splitlines()


_TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+(.+)$")


def _last_status(lines: list[str], ok_marker: str, fail_marker: str):
    """Scan tail lines newest-first for OK/FAILED entries of this kind.
    Returns (last_status, since_timestamp_of_streak_start, consecutive_fail_count).
    """
    entries = []  # (timestamp, status)
    for line in lines:
        m = _TS_RE.match(line)
        if not m:
            continue
        ts, rest = m.groups()
        if rest.startswith(ok_marker):
            entries.append((ts, "OK"))
        elif rest.startswith(fail_marker):
            entries.append((ts, "FAILED"))

    if not entries:
        return None, None, 0

    last_status = entries[-1][1]
    if last_status != "FAILED":
        return last_status, None, 0

    # Walk backward from the end counting the consecutive FAILED streak.
    streak = 0
    since = entries[-1][0]
    for ts, status in reversed(entries):
        if status != "FAILED":
            break
        streak += 1
        since = ts

    since_date = since.split(" ")[0]
    return last_status, since_date, streak


def check_state_dir(root: Path) -> list[str]:
    """Flag a live sync conflict marker and any *.err files with fresh
    content written recently - these mean a background job hit an exception."""
    state_dir = root / ".state"
    if not state_dir.exists():
        return []

    warnings: list[str] = []

    conflict = state_dir / "SYNC_CONFLICT"
    if conflict.exists():
        warnings.append(
            "BRAIN HEALTH: unresolved sync conflict - see .state/SYNC_CONFLICT"
        )

    now = dt.datetime.now().timestamp()
    for err_file in sorted(state_dir.glob("*.err")):
        try:
            if err_file.stat().st_size == 0:
                continue
            age_hours = (now - err_file.stat().st_mtime) / 3600
            if age_hours <= ERR_STALE_HOURS:
                warnings.append(
                    f"BRAIN HEALTH: {err_file.name} has fresh content "
                    f"({age_hours:.0f}h old) - a background job is erroring"
                )
        except OSError:
            continue

    return warnings


def main() -> None:
    root = repo_root()
    warnings: list[str] = []
    warnings += check_push_log(root)
    warnings += check_state_dir(root)
    for w in warnings:
        print(w)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
