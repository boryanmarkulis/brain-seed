# Customising it

Change anything. Two things are load-bearing, and this page is mostly about
which two.

## The invariants (do not break these)

The block at the top of `CLAUDE.md` between the `compile:locked` markers:

- **`sources/` is immutable.** Never LLM-edited, ever. Every wiki page claims
  to derive from files in here. Let an agent "tidy" a source and the whole
  provenance chain silently becomes fiction.
- **`daily/`, `log.md`, `decisions/log.md` are append-only.** Rewriting history
  breaks the compile-since-timestamp logic and the union merge drivers that let
  two devices append at once.
- **`me/` is human-owned.** Agents propose, you approve. It is the tiebreaker
  when a wiki page and reality disagree, so it has to be something you actually
  endorse.
- **`CLAUDE.md` and `AGENTS.md` stay byte-identical** below the locked block.

Everything else is fair game.

## Changing the folder shape

Add folders freely. If a new one should be part of what the compiler reads,
update `collect_new_material()` in `scripts/compile.py` and add a row to the
routing table in `references/brain-operating-guide.md`.

If you rename a top-level folder, grep for it first. The scripts refer to
`sources/`, `daily/`, `wiki/`, `me/`, and `projects/` by name.

## Changing the voice

`.claude/rules/communication-style.md` is read every session. `/onboard` writes
it from three samples of your real writing; edit it any time.

To change how the **wiki** is written rather than how the agent talks to you,
edit `voice` in `brain.config.json`. That string is interpolated into the
compiler prompts.

## Changing what gets compiled

`brain.config.json`:

| Key | Effect |
|---|---|
| `domains` | The subjects the compiler treats as in-scope |
| `wiki_scope` | One line on what the wiki should and should not absorb |
| `compile_model` | Which model does routing and page rewrites |
| `extract_model` | Which model does transcript extraction (cheap and fast) |
| `local_model` | Which local model runs the free pipeline |

**The most common mistake is a narrow `domains` list.** People list their
current field only, and years of experience from a previous career get silently
dropped. A past career is not off-topic. Widen it and re-run.

For a deep dive on one subject, write a focus file instead of narrowing
`domains`. See `references/focus/example-copywriting.md`.

## Changing the hooks

`.claude/settings.json`. Two rules learned the hard way:

- **Every hook must exit 0.** A hook that raises blocks your session. Every
  script here wraps its body in a top-level try/except for exactly this reason.
- **Session-start hooks must return in milliseconds.** `maybe_compile.py` spawns
  a detached background process and returns immediately; it never waits. Copy
  that pattern rather than doing work inline.

Turn a hook off by deleting its block. Nothing else depends on it.

## Adding a background job to the health check

`brain.config.json`:

```json
"health_checks": [
  { "label": "push to GitHub", "ok": "PUSH OK", "fail": "PUSH FAILED" },
  { "label": "nightly export", "ok": "EXPORT OK", "fail": "EXPORT FAILED" }
]
```

Have the job append `<timestamp> EXPORT OK` or `EXPORT FAILED` to
`.git/push.log`. `health_check.py` reads the tail, finds the latest status, and
warns you with the streak length if it is failing.

Do this for every background job you add. An unwatched job is a job that will
fail silently for a month.

## Adding your own scripts

Follow the shape of the existing ones:

- take config from `brain_config.py`, never hardcode a person or a path
- derive the repo root as `Path(__file__).resolve().parent.parent`
- print JSON on stdout when the output might be piped
- fail loudly with the real error, never a swallowed exception
- if it runs in a hook, exit 0 no matter what

## Making it a template for other people

If you want to hand your version to someone else, strip it first:

```bash
grep -rniE "your-name|your-company|your-clients" --include="*.md" --include="*.py" .
```

Check `connections.md` for pasted secrets, check `.env` is gitignored, and reset
`brain.config.json` to its defaults. `brain_doctor.py` has a check that fails
when a credential pattern appears in `connections.md`, but a denylist only
catches what you thought to name. Read the diff.
