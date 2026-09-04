#!/usr/bin/env python3
"""
maybe_wiki.py - state-gated catch-up launcher for the local wiki compiler.

The local extractor already reads sources/, daily/ and projects/, so folding
the day that just ended is the same work stage 1 does anyway. This gate is what
makes the wiki compile itself with no cloud agent and no paid API call.

launchd fires this hourly (RunAtLoad + StartInterval). It is a catch-up gate,
not a wall-clock schedule: whenever the Mac is awake and the last successful
run is older than THRESHOLD_HOURS, it spawns wiki_daylight.sh and returns.

Guards:
  - lock file .state/wiki-running holds the live pid; a stale lock is cleared
  - .state/wiki-stop present means you halted it on purpose, so stay out
  - the Mac must have been idle IDLE_MIN_SECONDS
  - it must be inside the local overnight window on AC power and Wi-Fi, or the
    last clean run must be older than STALE_HOURS
  - nothing pending in either stage means exit without waking the model
  - mid-run battery floor and nice'ing are wiki_daylight.sh's own job

Stamp .state/last-wiki.txt is written when the child EXITS cleanly, not at
launch, so a crashed run retries on the next fire instead of waiting a day.

The stamp is always UTC. launchd runs this job with TZ unset (so naive local
time there IS UTC) while a hand-run from your own shell picks up whatever zone
you are sitting in. A naive stamp therefore drifts by the UTC offset, and in a
zone ahead of UTC the stamp reads as the future, THRESHOLD_HOURS
never elapses, and the wiki stops compiling with no error anywhere. Never make
this naive again.
"""

from __future__ import annotations

import datetime as dt
import os
import subprocess
import sys
from pathlib import Path

THRESHOLD_HOURS = 20

# The Mac must have been untouched this long before any run starts. Idle stays
# the primary question: a clock window alone was too loose (it happily started
# at 02:00 while you were still at the desk).
IDLE_MIN_SECONDS = 15 * 60

# Preferred window, LOCAL time. This is meant to be an
# overnight job on AC and Wi-Fi, not something that eats 19GB mid-afternoon.
# Inside the window: idle + AC + Wi-Fi are the gates. Outside it: the run is
# refused UNLESS the wiki has gone STALE_HOURS without a clean run, which keeps
# a stretch of unplugged travel nights from stalling the compiler for good.
NIGHT_START_HOUR = 22
NIGHT_END_HOUR = 8
STALE_HOURS = 60

# AC power is required in the window. wiki_daylight.sh keeps its own mid-run
# battery floor; this refuses to even start the model on battery.
REQUIRE_AC = True

# Wi-Fi must be associated with an IP. Fails OPEN when no Wi-Fi device can be
# found at all (Ethernet dock, odd hardware), because a missing device is not
# evidence of a missing network and must not stall the wiki forever.
REQUIRE_WIFI = True

LOG_DIR = Path.home() / "Library" / "Logs" / "brain"


def now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def local_now() -> dt.datetime:
    """Real local wall-clock time, resolved from /etc/localtime.

    launchd runs this job with TZ unset, so a naive datetime.now() there is UTC,
    not local. You may also change timezone while travelling, so
    the zone can never be hardcoded. Falls back to UTC if the link is unreadable.
    """
    try:
        target = os.path.realpath("/etc/localtime")
        marker = "/zoneinfo/"
        if marker in target:
            from zoneinfo import ZoneInfo
            return now().astimezone(ZoneInfo(target.split(marker, 1)[1]))
    except Exception:
        pass
    return now()


def in_night_window(when: dt.datetime) -> bool:
    """True inside the overnight window, which wraps past midnight."""
    h = when.hour
    if NIGHT_START_HOUR <= NIGHT_END_HOUR:
        return NIGHT_START_HOUR <= h < NIGHT_END_HOUR
    return h >= NIGHT_START_HOUR or h < NIGHT_END_HOUR


def on_ac_power() -> bool:
    """True when pmset reports AC. Unreadable pmset fails closed."""
    try:
        out = subprocess.run(
            ["pmset", "-g", "batt"], capture_output=True, text=True, timeout=15,
        ).stdout
    except Exception:
        return False
    return "AC Power" in out


def wifi_device() -> str | None:
    """The BSD name of the Wi-Fi port (usually en0), or None if there is none."""
    try:
        out = subprocess.run(
            ["networksetup", "-listallhardwareports"],
            capture_output=True, text=True, timeout=15,
        ).stdout
    except Exception:
        return None
    lines = out.splitlines()
    for i, line in enumerate(lines):
        if "Wi-Fi" in line or "AirPort" in line:
            for nxt in lines[i + 1:i + 4]:
                if nxt.startswith("Device:"):
                    return nxt.split(":", 1)[1].strip()
    return None


def on_wifi() -> bool:
    """True when the Wi-Fi device holds an IP. No Wi-Fi device at all is True."""
    dev = wifi_device()
    if not dev:
        return True
    try:
        got = subprocess.run(
            ["ipconfig", "getifaddr", dev],
            capture_output=True, text=True, timeout=15,
        )
    except Exception:
        return True
    return bool(got.stdout.strip())


def hid_idle_seconds() -> float:
    """Seconds since the last keyboard or mouse event, or -1 if unreadable.

    Unreadable means "assume active". Idle is now the ONLY start gate, so a
    broken sensor must not hand the machine's RAM away while you are using it.
    That fails closed, so main() logs the refusal rather than dying silently.
    """
    try:
        out = subprocess.run(
            ["ioreg", "-c", "IOHIDSystem"],
            capture_output=True, text=True, timeout=15,
        ).stdout
        for line in out.splitlines():
            if "HIDIdleTime" in line:
                return int(line.rsplit("=", 1)[1].strip()) / 1e9
    except Exception:
        pass
    return -1.0


def log(msg: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOG_DIR / "wiki.log", "a") as out:
        out.write(f"[{local_now():%Y-%m-%d %H:%M:%S}] {msg}\n")


def stale(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return True
    return False


def _status(repo: Path, script: str) -> str:
    try:
        return subprocess.run(
            [sys.executable, str(repo / "scripts" / script), "--status"],
            capture_output=True, text=True, cwd=str(repo), timeout=300,
        ).stdout
    except Exception:
        return ""


def pending(repo: Path) -> bool:
    """True if either stage has work. Neither --status call loads the model.

    An unreadable status is treated as work pending: wiki_daylight.sh re-checks
    both counts itself and exits in seconds if there is nothing to do, so a
    false positive is cheap and a false negative stalls the wiki for a day.
    """
    ext = _status(repo, "wiki_extract.py")
    if not ext:
        return True
    # "chunks: 524 total, 624 done, 66 pending"
    for line in ext.splitlines():
        if "chunks:" in line and "pending" in line:
            parts = line.replace(",", "").split()
            for i, tok in enumerate(parts):
                if tok == "pending" and i and parts[i - 1].isdigit():
                    if int(parts[i - 1]) > 0:
                        return True

    con = _status(repo, "wiki_consolidate.py")
    if not con:
        return True
    # "[00:43:34] pending: 0 concepts (min 2 records each)"
    for line in con.splitlines():
        if "pending:" in line:
            parts = line.split("pending:")[1].split()
            if parts and parts[0].isdigit() and int(parts[0]) > 0:
                return True
    return False


def main() -> None:
    repo = Path(__file__).resolve().parent.parent
    state = repo / ".state"
    stamp = state / "last-wiki.txt"
    lock = state / "wiki-running"
    stop = state / "wiki-stop"

    if stop.exists():
        sys.exit(0)

    idle = hid_idle_seconds()
    if idle < 0:
        log("cannot read HIDIdleTime, refusing to start (fail closed)")
        sys.exit(0)
    if idle < IDLE_MIN_SECONDS:
        sys.exit(0)

    if lock.exists():
        try:
            if not stale(int(lock.read_text().strip())):
                sys.exit(0)
        except Exception:
            pass
        lock.unlink(missing_ok=True)

    age_hours = float("inf")
    if stamp.exists():
        try:
            last = dt.datetime.fromisoformat(stamp.read_text().strip())
            if last.tzinfo is None:  # pre-2026-08-22 naive stamp: distrust it
                raise ValueError("naive stamp")
            age_hours = (now() - last).total_seconds() / 3600
            if age_hours < THRESHOLD_HOURS:
                sys.exit(0)
        except Exception:
            age_hours = float("inf")

    if in_night_window(local_now()):
        if REQUIRE_AC and not on_ac_power():
            log(f"night window but on battery, skipping (wiki {age_hours:.0f}h old)")
            sys.exit(0)
        if REQUIRE_WIFI and not on_wifi():
            log(f"night window but Wi-Fi is down, skipping (wiki {age_hours:.0f}h old)")
            sys.exit(0)
    elif age_hours < STALE_HOURS:
        sys.exit(0)
    else:
        log(f"outside the night window but the wiki is {age_hours:.0f}h old "
            f"(stale floor {STALE_HOURS}h), running anyway")

    if not pending(repo):
        stamp.write_text(now().isoformat())
        sys.exit(0)

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    runner = repo / "scripts" / "wiki_runner.sh"
    with open(LOG_DIR / "wiki.log", "a") as out:
        subprocess.Popen(
            ["/bin/bash", str(runner)],
            stdout=out, stderr=subprocess.STDOUT,
            start_new_session=True, cwd=str(repo),
        )


if __name__ == "__main__":
    main()
