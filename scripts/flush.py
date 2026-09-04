#!/usr/bin/env python3
"""
flush.py - extract decisions, lessons, patterns, and references from a session
transcript and append them to daily/YYYY-MM-DD.md.

Two modes:

1. Hook mode (default): invoked by Claude Code SessionEnd hook.
   Reads the hook payload JSON from stdin, finds `transcript_path`, extracts,
   appends to today's daily file.

2. Inbox mode: `flush.py --inbox <path>` - treats <path> as a pasted transcript
   (plain text or JSONL) from web Claude, Codex, a meeting, or wherever. Same
   extraction and append logic.

Uses the `claude` CLI in headless mode (`claude -p --model haiku`), which
inherits the project's existing Claude Code auth. No ANTHROPIC_API_KEY needed.

Failures are silent to the user but logged to `log.md` with a MIGRATION/ERROR tag
so they're visible in the event log.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from brain_config import cfg  # noqa: E402

# How long to wait for an async-flushed transcript to appear on disk.
# Claude Code writes the JSONL shortly after SessionEnd fires; large transcripts
# (>500KB) can take several seconds. 60 × 1.0s = up to 60s total.
TRANSCRIPT_WAIT_TRIES = 60
TRANSCRIPT_WAIT_SECONDS = 1.0

# If Haiku returns SKIP but the rendered transcript is at least this large,
# still write a stub header to daily/ so the session shows up in the activity
# ledger. Prevents substantive work (e.g. /networking briefs) from silently
# vanishing when extraction decides nothing crosses the "lesson" bar.
STUB_FALLBACK_CHARS = 5_000

# Recursion guard. flush.py spawns `claude -p`, which is itself a Claude Code
# session. When that subprocess session ends, it fires the SessionEnd hook,
# which would re-invoke flush.py - infinite loop. We set this env var before
# spawning claude, and bail at the top of main() if we see it.
RECURSION_ENV = "BRAIN_FLUSH_RUNNING"

# Keep model pinned but easy to bump. Haiku 4.5 is cheap and strong enough
# for extraction-style work.
MODEL = cfg.extract_model

# Cap transcript size fed to Haiku to keep cost + latency bounded.
# Roughly ~100k chars = ~25k tokens of raw text.
MAX_TRANSCRIPT_CHARS = 100_000

# Below this, a session isn't worth summarizing.
MIN_TRANSCRIPT_CHARS = 400

EXTRACTION_PROMPT = """\
You are extracting durable knowledge AND a concrete activity log from a session
transcript for a second-brain system.

About the owner of this Brain:
- Name: {owner}
- Mission: {mission}
- Work: {work}

Read the transcript. Capture two things:
1. What actually happened (the work done, the people touched).
2. What's worth keeping long-term (decisions, lessons, patterns, references,
   open threads).

Output strict markdown in this exact shape. Omit any section that has nothing
worth recording. Do not add headings, preamble, or closing remarks outside this
structure.

### Work
- [one concrete thing that got done this session - built, ingested, sent, published, fixed, debugged, reviewed. Include specifics: file names, people contacted, URLs published, systems touched.]

### People
- [Name - new info learned, status change, outreach sent/received, note worth remembering. One line each.]

### Decisions
- [one decision, one line, imperative or past tense]

### Lessons
- [one lesson or insight, one line]

### Patterns
- [recurring pattern in behavior, work, or thinking - one line]

### References
- [external link, paper, tweet, file path mentioned - title plus url/path]

### Open Threads
- [unresolved question or loose end worth tracking]

Rules:
- Be terse. One short line per bullet. No fluff, no hedging.
- Don't invent. If the transcript doesn't contain a type of item, omit that section entirely.
- Don't include generic advice. Only things specific to this session.
- No code blocks, no tables.
- SKIP rule: Return the single token SKIP ONLY if the transcript is truly empty
  of user intent - e.g. pure /clear, pure plugin install with no follow-up,
  hook-debug noise with no real work. If real work happened (a skill ran, files
  were edited, messages were drafted, ingests completed, research was done),
  ALWAYS produce at least a ### Work section. Do not return SKIP just because
  nothing rises to the level of a "decision" or "lesson."
- Output format: your response MUST begin with "### " (a section header) or the
  single word SKIP. Do not respond conversationally. Do not continue or reply to
  the conversation in the transcript.
"""


def log_event(repo_root: Path, msg: str) -> None:
    """Append a line to log.md. Best-effort; never raises."""
    try:
        today = dt.date.today().isoformat()
        with (repo_root / "log.md").open("a") as f:
            f.write(f"[{today}] {msg}\n")
    except Exception:
        pass


def _summarize_tool_use(part: dict) -> str:
    """One-line summary of an assistant tool_use block.

    Tool-heavy sessions (/networking, /pull, /ingest) have little text but
    rich tool-call history; a one-line summary gives Haiku enough signal to
    extract what actually happened.
    """
    name = part.get("name", "?")
    inp = part.get("input") or {}
    if not isinstance(inp, dict):
        return f"[tool] {name}"

    for key in ("file_path", "path", "command", "pattern", "url", "query", "prompt", "description"):
        val = inp.get(key)
        if isinstance(val, str) and val:
            snippet = val.strip().replace("\n", " ")
            if len(snippet) > 160:
                snippet = snippet[:160] + "..."
            return f"[tool] {name}: {snippet}"
    return f"[tool] {name}"


def _summarize_tool_result(part: dict) -> str:
    """One-line preview of a tool_result block.

    Full tool output is usually noise (long file contents, command output), but
    a short preview gives Haiku signal about what the tool actually returned -
    e.g. whether a Bash command succeeded, what a Read showed.
    """
    content = part.get("content")
    if isinstance(content, list):
        pieces: list[str] = []
        for c in content:
            if isinstance(c, dict) and c.get("type") == "text":
                pieces.append(c.get("text", ""))
            elif isinstance(c, str):
                pieces.append(c)
        text = " ".join(pieces)
    elif isinstance(content, str):
        text = content
    else:
        return ""

    text = text.strip().replace("\n", " ")
    if not text:
        return ""
    if len(text) > 120:
        text = text[:120] + "..."
    return f"[result] {text}"


def _json_text_parts(content) -> list[str]:
    """Extract text from Claude/Codex message content shapes."""
    parts: list[str] = []
    if isinstance(content, str):
        if content:
            parts.append(content)
    elif isinstance(content, list):
        for part in content:
            if isinstance(part, str):
                parts.append(part)
                continue
            if not isinstance(part, dict):
                continue
            text = part.get("text")
            if isinstance(text, str) and text:
                parts.append(text)
    return parts


def _summarize_json_args(args) -> str:
    """Compact tool/function arguments into one useful line."""
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            snippet = args.strip().replace("\n", " ")
            return snippet[:180] + ("..." if len(snippet) > 180 else "")
    if not isinstance(args, dict):
        return ""

    for key in ("cmd", "command", "path", "file_path", "ref_id", "query", "pattern", "url"):
        val = args.get(key)
        if isinstance(val, str) and val:
            snippet = val.strip().replace("\n", " ")
            return snippet[:180] + ("..." if len(snippet) > 180 else "")
        if isinstance(val, list) and val:
            snippet = " ".join(str(x) for x in val).strip().replace("\n", " ")
            return snippet[:180] + ("..." if len(snippet) > 180 else "")

    try:
        snippet = json.dumps(args, ensure_ascii=False, sort_keys=True)
    except TypeError:
        snippet = str(args)
    return snippet[:180] + ("..." if len(snippet) > 180 else "")


def _preview_text(value, limit: int = 160) -> str:
    if isinstance(value, str):
        text = value
    else:
        try:
            text = json.dumps(value, ensure_ascii=False)
        except TypeError:
            text = str(value)
    text = text.strip().replace("\n", " ")
    if len(text) > limit:
        text = text[:limit] + "..."
    return text


def _looks_like_codex_jsonl(path: Path) -> bool:
    for line in path.read_text(errors="replace").splitlines()[:20]:
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("type") in {"session_meta", "response_item", "event_msg"}:
            payload = obj.get("payload")
            if isinstance(payload, dict) and (
                payload.get("originator", "").startswith("codex")
                or payload.get("type") in {"message", "function_call", "function_call_output"}
                or obj.get("type") == "response_item"
            ):
                return True
    return False


def read_codex_jsonl(path: Path) -> str:
    """Read a Codex JSONL rollout transcript, return a plain-text rendering.

    Codex stores rich event streams. Keep only human/agent messages and compact
    tool summaries so extraction sees work, not platform scaffolding.
    """
    out: list[str] = []
    seen_agent_messages: set[str] = set()

    for line in path.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue

        kind = obj.get("type")
        payload = obj.get("payload")
        if not isinstance(payload, dict):
            continue

        if kind == "response_item":
            ptype = payload.get("type")
            if ptype == "message":
                role = payload.get("role", "")
                if role not in {"user", "assistant"}:
                    continue
                text = "\n".join(_json_text_parts(payload.get("content"))).strip()
                if not text:
                    continue
                if role == "assistant":
                    seen_agent_messages.add(text)
                display_role = {"user": "human", "assistant": "agent"}.get(role, role)
                out.append(f"[{display_role}] {text}")
            elif ptype == "function_call":
                name = payload.get("name", "tool")
                summary = _summarize_json_args(payload.get("arguments"))
                out.append(f"[tool] {name}" + (f": {summary}" if summary else ""))
            elif ptype == "function_call_output":
                preview = _preview_text(payload.get("output"), limit=180)
                if preview:
                    out.append(f"[result] {preview}")

        # event_msg records duplicate most response_item messages and include
        # platform chatter. response_item is the canonical transcript stream.

    return "\n\n".join(out)


def read_transcript_jsonl(path: Path) -> str:
    """Read a Claude Code JSONL transcript, return a plain-text rendering.

    Keeps role/content text, one-line summaries of assistant tool calls, and
    short previews of tool results.
    """
    if _looks_like_codex_jsonl(path):
        return read_codex_jsonl(path)

    out: list[str] = []
    for line in path.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue

        msg = obj.get("message", obj)
        role = msg.get("role") or obj.get("type") or ""
        content = msg.get("content", "")

        parts_out: list[str] = []
        if isinstance(content, str):
            parts_out.append(content)
        elif isinstance(content, list):
            for part in content:
                if not isinstance(part, dict):
                    continue
                ptype = part.get("type")
                if ptype == "text":
                    parts_out.append(part.get("text", ""))
                elif ptype == "tool_use":
                    parts_out.append(_summarize_tool_use(part))
                elif ptype == "tool_result":
                    preview = _summarize_tool_result(part)
                    if preview:
                        parts_out.append(preview)

        text = "\n".join(p for p in parts_out if p).strip()
        if not text:
            continue

        display_role = {"user": "human", "assistant": "agent"}.get(role, role)
        out.append(f"[{display_role}] {text}")

    return "\n\n".join(out)


def load_transcript(source: Path) -> str:
    """Return plain-text transcript from a file (JSONL or plain text)."""
    if source.suffix == ".jsonl":
        return read_transcript_jsonl(source)
    return source.read_text(errors="replace")


def call_claude(prompt: str, transcript: str) -> str:
    """Run the claude CLI in headless mode with the extraction prompt."""
    full = f"{prompt}\n\n<transcript>\n{transcript}\n</transcript>"
    env = os.environ.copy()
    env[RECURSION_ENV] = "1"
    try:
        result = subprocess.run(
            ["claude", "-p", "--model", MODEL, full],
            capture_output=True,
            text=True,
            timeout=90,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"claude CLI timed out after {exc.timeout}s") from exc
    if result.returncode != 0:
        err = result.stderr.strip()[:1000]
        out = result.stdout.strip()[:1000]
        cli = subprocess.run(["which", "claude"], capture_output=True, text=True).stdout.strip()
        raise RuntimeError(
            f"claude CLI failed rc={result.returncode} cli={cli!r} stderr={err!r} stdout={out!r}"
        )
    return result.stdout.strip()


def call_codex(prompt: str, transcript: str, repo_root: Path) -> str:
    """Run the Codex CLI non-interactively with the extraction prompt."""
    full = f"{prompt}\n\n<transcript>\n{transcript}\n</transcript>"
    with tempfile.NamedTemporaryFile("w+", delete=False) as out:
        out_path = out.name
    cmd = [
        "codex",
        "exec",
        "--ephemeral",
        "--skip-git-repo-check",
        "--sandbox",
        "read-only",
        "-C",
        str(repo_root),
        "-o",
        out_path,
        "-",
    ]
    model = os.environ.get("BRAIN_CODEX_FLUSH_MODEL")
    if model:
        cmd[2:2] = ["-m", model]
    try:
        result = subprocess.run(
            cmd,
            input=full,
            capture_output=True,
            text=True,
            timeout=180,
            cwd=repo_root,
        )
        if result.returncode != 0:
            err = result.stderr.strip()[:1000]
            out_text = result.stdout.strip()[:1000]
            cli = subprocess.run(["which", "codex"], capture_output=True, text=True).stdout.strip()
            raise RuntimeError(
                f"codex CLI failed rc={result.returncode} cli={cli!r} stderr={err!r} stdout={out_text!r}"
            )
        return Path(out_path).read_text(errors="replace").strip()
    finally:
        try:
            Path(out_path).unlink()
        except OSError:
            pass


def call_extractor(prompt: str, transcript: str, repo_root: Path, backend: str) -> str:
    prompt = cfg.render(prompt)
    if backend == "codex":
        return call_codex(prompt, transcript, repo_root)
    if backend == "claude":
        return call_claude(prompt, transcript)
    raise ValueError(f"unknown extractor backend: {backend}")


def append_daily(
    repo_root: Path,
    session_id: str,
    body: str,
    session_date: str | None = None,
    heading_label: str = "Session",
) -> Path:
    """Append the extracted block to daily/sessions/YYYY-MM-DD-sessions.md.

    Machine captures live in their own file so the human-owned
    daily/YYYY-MM-DD.md (Plan + Reflection, edited in Obsidian/VS Code) is
    never touched by automated writes. Returns the file path."""
    today = session_date or dt.date.today().isoformat()
    sessions_dir = repo_root / "daily" / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    path = sessions_dir / f"{today}-sessions.md"

    header = f"\n---\n\n## {heading_label} {session_id} · {dt.datetime.now().strftime('%H:%M')}\n\n"
    if not path.exists():
        path.write_text(f"# {today} - Session Captures\n")
    with path.open("a") as f:
        f.write(header)
        f.write(body.rstrip() + "\n")
    return path


def _first_user_line(text: str) -> str:
    """First non-caveat user line, truncated - used as a hint in stub entries."""
    for line in text.splitlines():
        if not line.startswith("[human] "):
            continue
        body = line[len("[human] "):].strip()
        # Skip Claude Code's local-command wrappers.
        if body.startswith("<local-command-") or body.startswith("<command-"):
            continue
        if not body:
            continue
        if len(body) > 160:
            body = body[:160] + "..."
        return body
    return ""


def flush(
    transcript_path: Path,
    session_id: str,
    repo_root: Path,
    tag: str = "",
    hook_payload: dict | None = None,
    session_date: str | None = None,
    heading_label: str = "Session",
    backend: str = "claude",
) -> str:
    # Claude Code flushes the JSONL asynchronously; at SessionEnd the file
    # may not yet exist. Poll up to TRANSCRIPT_WAIT_TRIES * TRANSCRIPT_WAIT_SECONDS.
    # For source='other' (/clear), short sessions never write a transcript - cap at 10s
    # so we don't block for 60s on throwaway clears. Long /clear sessions still land
    # within that window.
    source = (hook_payload or {}).get("source", "") if hook_payload else ""
    wait_tries = 10 if source == "other" else TRANSCRIPT_WAIT_TRIES
    for _ in range(wait_tries):
        if transcript_path.exists():
            break
        time.sleep(TRANSCRIPT_WAIT_SECONDS)
    if not transcript_path.exists():
        total = TRANSCRIPT_WAIT_TRIES * TRANSCRIPT_WAIT_SECONDS
        payload_hint = ""
        if hook_payload:
            cwd = hook_payload.get("cwd", "")
            source = hook_payload.get("source") or hook_payload.get("reason") or ""
            payload_hint = f" cwd={cwd!r} source={source!r}"
        log_event(repo_root, f"FLUSH SKIP{tag}: transcript missing after {total:.0f}s session={session_id}{payload_hint} path={transcript_path}")
        return "skip"

    text = load_transcript(transcript_path)
    if len(text) < MIN_TRANSCRIPT_CHARS:
        log_event(repo_root, f"FLUSH SKIP{tag}: session {session_id} too short ({len(text)} chars)")
        return "skip"
    rendered_len = len(text)
    if rendered_len > MAX_TRANSCRIPT_CHARS:
        text = text[-MAX_TRANSCRIPT_CHARS:]

    try:
        extracted = call_extractor(EXTRACTION_PROMPT, text, repo_root, backend)
    except Exception as exc:
        log_event(repo_root, f"FLUSH ERROR{tag}: session {session_id}: {exc}")
        if "out of extra usage" in str(exc).lower():
            return "quota"
        return "error"

    # Malformed: Haiku responded conversationally instead of extracting.
    is_valid = extracted.strip().upper() == "SKIP" or extracted.strip().startswith("### ")
    if not is_valid and extracted.strip():
        hint = extracted.strip()[:120].replace("\n", " ")
        log_event(repo_root, f"FLUSH MALFORMED{tag}: session {session_id} - response didn't start with '### ': {hint!r}")
        extracted = "SKIP"

    if extracted.strip().upper() == "SKIP" or not extracted.strip():
        # Haiku decided nothing was worth keeping. If the session was
        # substantial, still log a stub so the activity ledger isn't silent.
        if rendered_len >= STUB_FALLBACK_CHARS:
            hint = _first_user_line(text)
            stub_body = f"(no extract; {rendered_len // 1000}k chars"
            if hint:
                stub_body += f"; first user: {hint}"
            stub_body += ")"
            path = append_daily(
                repo_root,
                session_id,
                stub_body,
                session_date=session_date,
                heading_label=heading_label,
            )
            log_event(repo_root, f"FLUSH STUB{tag}: session {session_id} ({rendered_len} chars) → {path.relative_to(repo_root)}")
        else:
            log_event(repo_root, f"FLUSH SKIP{tag}: session {session_id} had nothing to extract ({rendered_len} chars)")
            return "skip"
        return "stub"

    path = append_daily(
        repo_root,
        session_id,
        extracted,
        session_date=session_date,
        heading_label=heading_label,
    )
    log_event(repo_root, f"FLUSH OK{tag}: session {session_id} → {path.relative_to(repo_root)}")
    return "ok"


def from_hook_stdin(repo_root: Path) -> None:
    """Read the SessionEnd hook JSON payload from stdin and flush."""
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        log_event(repo_root, f"FLUSH ERROR: invalid hook payload: {exc}")
        return

    transcript_path = payload.get("transcript_path")
    if not transcript_path:
        log_event(repo_root, "FLUSH SKIP: hook payload had no transcript_path")
        return

    session_id = payload.get("session_id", "unknown")[:12]
    flush(Path(transcript_path), session_id, repo_root, hook_payload=payload)


def main() -> None:
    # Recursion guard: if we're the child of a flush.py that's calling claude -p,
    # and that subprocess's SessionEnd hook fired this script, bail immediately.
    if os.environ.get(RECURSION_ENV) == "1":
        sys.exit(0)

    # Trace that Python actually started - distinguishes "hook never fired"
    # from "hook fired but flush.py died early".
    repo_root_early = Path(__file__).resolve().parent.parent
    log_event(repo_root_early, f"FLUSH ENTERED pid={os.getpid()}")

    parser = argparse.ArgumentParser(description="Extract session knowledge into daily/.")
    parser.add_argument("--inbox", type=Path, help="Path to a pasted transcript to flush manually.")
    parser.add_argument("--session-id", default="inbox", help="Session id for the daily/ header.")
    parser.add_argument("--date", help="Daily date to append to, YYYY-MM-DD. Defaults to today.")
    parser.add_argument("--render-only", action="store_true",
                        help="Render the transcript and print it; do not summarize or write daily/.")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent

    if args.render_only:
        if not args.inbox:
            parser.error("--render-only requires --inbox")
        print(load_transcript(args.inbox))
    elif args.inbox:
        flush(args.inbox, args.session_id, repo_root, session_date=args.date)
    else:
        from_hook_stdin(repo_root)


if __name__ == "__main__":
    main()
