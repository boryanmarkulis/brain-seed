#!/usr/bin/env python3
"""
sync.py - repo-portable, self-healing Brain sync across devices.

Lives in version control (unlike .git/hooks and ~/Library/LaunchAgents), so
every clone gets device-to-device sync the moment Claude Code starts. Wired
into .claude/settings.json:

  sync.py pull   SessionStart: reconcile the latest from origin before any
                 work, so this device sees what other devices wrote.

  sync.py push   SessionEnd: reconcile, then push, so the work reaches origin
                 even on a device with no post-commit hook or launchd agent.

Design (why it can't drift like the old rebase version did):

  * COMMIT-FIRST. Any dirty or untracked file is committed before we touch
    origin. This kills the two classic failures: "untracked file would be
    overwritten by checkout" and autostash surprises. Nothing is ever lost.

  * MERGE, not rebase. A merge uses the union merge drivers from
    .gitattributes (log.md, daily/*.md, hook-trace.log, journal, ...), so
    append-only files from two devices auto-combine instead of conflicting.
    A merge of N diverged commits also can't half-apply and strand the repo
    the way a 37-commit rebase did.

  * FLAG, don't give up. A genuine content conflict (same editable file
    changed two ways on two devices) aborts the merge cleanly and writes
    .state/SYNC_CONFLICT so the statusline shows a warning until a human
    reconciles. The old code silently aborted and let the two sides drift
    apart forever; this surfaces it instead.

  * SELF-HEALING PUSH. If a push is rejected non-fast-forward (someone wrote
    to origin between our reconcile and our push), we reconcile once more and
    retry, instead of leaving local permanently ahead.

Safe to run anywhere. No-ops cleanly if this isn't a git repo, has no origin,
or is offline. Never raises into the hook chain (always exits 0). Logs to
.state/sync.log.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

try:
    import fcntl  # POSIX only; absent on Windows
except ImportError:  # pragma: no cover
    fcntl = None

REPO_ROOT = Path(__file__).resolve().parent.parent
LOG_FILE = REPO_ROOT / ".state" / "sync.log"
FLAG_FILE = REPO_ROOT / ".state" / "SYNC_CONFLICT"
LOCK_FILE = REPO_ROOT / ".state" / "sync.lock"
BRANCH = "main"

# Held for the process lifetime once acquired; kept in a module global so the
# file handle (and therefore the OS lock) is not garbage-collected mid-run.
_lock_handle = None


def log(msg: str) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.now().isoformat(timespec="seconds")
    with open(LOG_FILE, "a") as f:
        f.write(f"{ts} {msg}\n")


def git(*args: str, timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
        env={"GIT_TERMINAL_PROMPT": "0", **dict(os.environ)},
    )


def acquire_lock() -> bool:
    """Single-instance guard. SessionStart (pull) and SessionEnd (push) fire on
    overlapping sessions, and network-timeout retries stretch a run out, so
    multiple sync.py processes used to run at once and stomp on git's index/HEAD
    locks -- the half-state that lost files on 2026-06-17. Grab an exclusive,
    non-blocking lock; if another sync already holds it, return False and the
    caller no-ops (the next sync reconciles anyway). Degrades to allowing the run
    if file locking is unavailable, rather than blocking sync entirely."""
    global _lock_handle
    if fcntl is None:
        return True
    try:
        LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
        fh = open(LOCK_FILE, "w")
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        _lock_handle = fh  # keep the handle alive -> hold the lock until exit
        return True
    except BlockingIOError:
        return False
    except Exception as exc:
        log(f"LOCK unavailable, proceeding without it: {exc}")
        return True


def has_origin() -> bool:
    try:
        r = git("remote", timeout=10)
        return r.returncode == 0 and "origin" in r.stdout.split()
    except Exception:
        return False


def clear_stale_lock() -> None:
    """Remove an index.lock older than 10 min, like compile.py does."""
    lock = REPO_ROOT / ".git" / "index.lock"
    if lock.exists():
        try:
            if time.time() - lock.stat().st_mtime > 600:
                lock.unlink()
        except Exception:
            pass


def abort_in_progress() -> None:
    """Never inherit a half-finished merge/rebase from a crashed prior run."""
    if (REPO_ROOT / ".git" / "MERGE_HEAD").exists():
        git("merge", "--abort", timeout=30)
        log("RECOVER: aborted stale in-progress merge")
    if (REPO_ROOT / ".git" / "rebase-merge").exists() or (
        REPO_ROOT / ".git" / "rebase-apply"
    ).exists():
        git("rebase", "--abort", timeout=30)
        log("RECOVER: aborted stale in-progress rebase")


def set_flag(detail: str) -> None:
    try:
        FLAG_FILE.parent.mkdir(parents=True, exist_ok=True)
        ts = dt.datetime.now().isoformat(timespec="seconds")
        FLAG_FILE.write_text(
            f"SYNC CONFLICT at {ts}\n\n{detail}\n\n"
            "Local and origin both changed the same non-append file. The auto-merge\n"
            "was aborted and your tree restored. Resolve manually:\n"
            f"  git -C \"{REPO_ROOT}\" merge origin/{BRANCH}\n"
            "  # fix the conflicted files, then: git add -A && git commit\n"
        )
    except Exception:
        pass


def push_rescue_branch() -> None:
    """When main can't be reconciled, push the local commits to a named branch
    on origin so the work is never stranded -- critical on an ephemeral remote
    container whose filesystem is destroyed at session end. Branch name is keyed
    to the commit sha, so re-running while still conflicted is idempotent (no
    branch spam). The Mac surfaces the flag; resolve, then delete the branch."""
    try:
        sha = git("rev-parse", "--short", "HEAD", timeout=10).stdout.strip()
        if not sha:
            return
        host = re.sub(r"[^a-z0-9-]+", "-", socket.gethostname().split(".")[0].lower())
        branch = f"sync-rescue/{host or 'device'}-{sha}"
        r = git("push", "origin", f"HEAD:refs/heads/{branch}", timeout=45)
        if r.returncode == 0:
            log(f"RESCUE: local work safe on origin branch {branch}")
            try:
                with open(FLAG_FILE, "a") as f:
                    f.write(
                        f"\nYour local commits were also pushed to origin branch:\n"
                        f"  {branch}\n"
                        "(safety backup; delete it after you've merged.)\n"
                    )
            except Exception:
                pass
        else:
            log(f"RESCUE push failed: {(r.stderr or r.stdout).strip()[:160]}")
    except Exception as exc:
        log(f"RESCUE exception: {exc}")


def clear_flag() -> None:
    try:
        FLAG_FILE.unlink()
    except FileNotFoundError:
        pass
    except Exception:
        pass


def parse_deletions(porcelain: str) -> list[str]:
    """Tracked files that have vanished from the worktree (porcelain status 'D'
    in either column), excluding renames/copies. These are exactly what the old
    blind `git add -A` would have silently committed as intentional deletions."""
    deleted = []
    for line in porcelain.splitlines():
        if len(line) < 4:
            continue
        xy, path = line[:2], line[3:]
        if "R" in xy or "C" in xy:
            continue  # rename/copy renders as 'old -> new', not a real deletion
        if "D" in xy:
            deleted.append(path)
    return deleted


def guard_deletions(paths: list[str]) -> None:
    """Backstop for the silent-deletion bug. An automated sync should never be
    the thing that erases vault content, so for every vanished tracked file we
    back up its last committed bytes, restore it into the worktree from HEAD, and
    log it loudly. The original cause -- a racing sync that momentarily emptied
    the tree -- is thus self-healed instead of committed away. A deliberate human
    deletion reappears once and is logged: visible and recoverable, never silent
    (re-delete with an explicit commit if you really mean it)."""
    stamp = dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    backup_dir = REPO_ROOT / ".state" / "deleted-backups" / stamp
    for path in paths:
        try:
            # Restore the worktree copy from HEAD first (binary-safe for PDFs etc).
            git("checkout", "HEAD", "--", path, timeout=60)
            src = REPO_ROOT / path
            if src.exists():
                dest = backup_dir / path
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
            log(
                f"DELETION GUARD: refused to auto-commit deletion of {path}; "
                f"restored from HEAD, backup under {backup_dir}"
            )
        except Exception as exc:
            log(f"DELETION GUARD error on {path}: {exc}")


def commit_local() -> None:
    """Commit any dirty/untracked changes so the tree is clean before merge.

    Additions and modifications are committed normally. Deletions are NOT: a
    tracked file missing from the worktree is restored from HEAD and logged (see
    guard_deletions), because the only observed cause of an unexpected deletion
    here was a concurrency race, and an automated sync should never silently
    record vault content as deleted."""
    status = git("status", "--porcelain", timeout=60)
    if status.returncode != 0:
        log(f"COMMIT skip: git status failed: {status.stderr.strip()[:160]}")
        return
    if not status.stdout.strip():
        return
    deletions = parse_deletions(status.stdout)
    if deletions:
        guard_deletions(deletions)
        # Restores may have left nothing (or only safe changes) to commit.
        status = git("status", "--porcelain", timeout=60)
        if status.returncode != 0 or not status.stdout.strip():
            return
    if git("add", "-A", timeout=120).returncode != 0:
        log("COMMIT skip: git add failed")
        return
    today = dt.date.today().isoformat()
    c = git("commit", "-m", f"auto: session sync {today}", timeout=120)
    if c.returncode == 0:
        log("COMMIT ok")
    else:
        log(f"COMMIT note: {(c.stdout or c.stderr).strip()[:160]}")


def sweep_claude_branches() -> None:
    """Absorb work stranded on remote claude/* branches into main.

    Ephemeral cloud Claude Code sessions (remote /reflect, /journal, etc.)
    commit to a claude/* feature branch and push -- they never write main, and
    their container is then destroyed. sync.py only reconciles main, so that
    work would never reach any device's vault. This sweeps it in: each origin
    claude/* branch that is ahead of main is merged with the same union drivers
    as the main reconcile (so daily/, log.md, journal/ combine instead of
    conflict), main is pushed, and the branch is deleted. A redundant branch
    (nothing ahead of main) is just deleted. A genuine conflict leaves the
    branch intact and raises SYNC_CONFLICT for a human, rather than guessing.

    Called only after main is already reconciled, so HEAD is current. Bounded by
    the (normally 0-2) claude/* branches on origin; no-ops cleanly when none.
    """
    f = git(
        "fetch", "origin", "--prune",
        "+refs/heads/claude/*:refs/remotes/origin/claude/*",
        timeout=45,
    )
    if f.returncode != 0:
        return  # offline/transient: leave the branches for the next run
    refs = git(
        "for-each-ref", "--format=%(refname)",
        "refs/remotes/origin/claude/", timeout=30,
    ).stdout.split()
    for ref in refs:
        branch = ref.split("refs/remotes/origin/", 1)[-1]  # -> "claude/<name>"
        ahead = git("rev-list", "--count", f"{BRANCH}..{ref}", timeout=30)
        if ahead.returncode == 0 and ahead.stdout.strip() == "0":
            # Fully contained in main already: stale, just clean it up.
            if git("push", "origin", "--delete", branch, timeout=45).returncode == 0:
                log(f"SWEEP: deleted redundant {branch}")
            continue
        m = git("merge", "--no-edit", ref, timeout=60)
        if m.returncode != 0:
            conflicted = git(
                "diff", "--name-only", "--diff-filter=U", timeout=30
            ).stdout.strip()
            git("merge", "--abort", timeout=30)
            log(f"SWEEP conflict on {branch}, left intact. Files: {conflicted or '(unknown)'}")
            set_flag(
                f"Remote branch {branch} conflicts with main:\n"
                f"{conflicted or '(see git status)'}"
            )
            continue
        # Merged into local main. Push so origin has it, then drop the branch.
        if git("push", "origin", BRANCH, timeout=45).returncode != 0:
            log(f"SWEEP: merged {branch} locally; push deferred to next run")
            continue
        if git("push", "origin", "--delete", branch, timeout=45).returncode == 0:
            log(f"SWEEP: merged + deleted {branch}")
        else:
            log(f"SWEEP: merged {branch}; remote delete failed (will retry)")


def reconcile() -> bool:
    """Bring local into agreement with origin. Returns True if clean (safe to
    push), False if a genuine conflict was flagged for human resolution."""
    abort_in_progress()
    clear_stale_lock()

    fetch = git("fetch", "origin", BRANCH, timeout=45)
    if fetch.returncode != 0:
        # Offline or transient: not a conflict, just can't reach origin now.
        log(f"FETCH error (offline?): {(fetch.stderr or fetch.stdout).strip()[:160]}")
        return False

    # Commit-first: nothing untracked/dirty can block the merge checkout.
    commit_local()

    behind = git("rev-list", "--count", f"HEAD..origin/{BRANCH}", timeout=30)
    if behind.returncode == 0 and behind.stdout.strip() == "0":
        # Already have everything origin has; nothing to merge.
        clear_flag()
        sweep_claude_branches()
        return True

    merge = git(
        "-c", "merge.autostash=true",
        "merge", "--no-edit", f"origin/{BRANCH}",
        timeout=60,
    )
    if merge.returncode == 0:
        log("MERGE ok (origin reconciled)")
        clear_flag()
        sweep_claude_branches()
        return True

    # Genuine conflict (union drivers already handled the append-only files).
    conflicted = git("diff", "--name-only", "--diff-filter=U", timeout=30).stdout.strip()
    git("merge", "--abort", timeout=30)
    log(f"MERGE conflict, aborted. Files: {conflicted or '(unknown)'}")
    set_flag(f"Conflicting files:\n{conflicted or '(see git status)'}")
    # Network was up (fetch succeeded) -- stash the local work safely on origin
    # before this (possibly ephemeral) checkout disappears.
    push_rescue_branch()
    return False


def cmd_pull(_args: argparse.Namespace) -> int:
    if not has_origin():
        log("PULL skip: no origin remote")
        return 0
    if not acquire_lock():
        log("PULL skip: another sync is already running")
        return 0
    try:
        reconcile()
    except subprocess.TimeoutExpired:
        log("PULL timeout (slow network?)")
        abort_in_progress()
    except Exception as exc:
        log(f"PULL exception: {exc}")
        abort_in_progress()
    return 0


def cmd_push(_args: argparse.Namespace) -> int:
    if not has_origin():
        log("PUSH skip: no origin remote")
        return 0
    if not acquire_lock():
        log("PUSH skip: another sync is already running")
        return 0
    try:
        if not reconcile():
            log("PUSH held: unresolved conflict flagged, not pushing")
            return 0
        push = git("push", "origin", BRANCH, timeout=45)
        if push.returncode == 0:
            head = git("rev-parse", "--short", "HEAD", timeout=10).stdout.strip()
            log(f"PUSH ok -> {head}")
            return 0
        # Rejected (someone wrote to origin in the gap): reconcile once and retry.
        if "non-fast-forward" in (push.stderr + push.stdout) or "rejected" in (
            push.stderr + push.stdout
        ):
            log("PUSH rejected non-ff; reconciling and retrying once")
            if reconcile():
                retry = git("push", "origin", BRANCH, timeout=45)
                if retry.returncode == 0:
                    head = git("rev-parse", "--short", "HEAD", timeout=10).stdout.strip()
                    log(f"PUSH ok on retry -> {head}")
                    return 0
                log(f"PUSH retry error: {(retry.stderr or retry.stdout).strip()[:160]}")
        else:
            log(f"PUSH error: {(push.stderr or push.stdout).strip()[:160]}")
    except subprocess.TimeoutExpired:
        log("PUSH timeout (slow network?)")
        abort_in_progress()
    except Exception as exc:
        log(f"PUSH exception: {exc}")
        abort_in_progress()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Repo-portable, self-healing Brain sync.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("pull", help="SessionStart: reconcile latest from origin")
    sub.add_parser("push", help="SessionEnd: reconcile, then push")
    args = parser.parse_args()
    if args.cmd == "pull":
        return cmd_pull(args)
    if args.cmd == "push":
        return cmd_push(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
