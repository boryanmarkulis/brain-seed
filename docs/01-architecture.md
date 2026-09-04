# Architecture

## The one idea

**Raw truth is immutable. Everything else is derived and disposable.**

`sources/` and `daily/` are append-only and never edited by a model. Every wiki
page cites the exact source paths it was built from. That single constraint is
what makes the system trustworthy: if a page says something surprising, you can
walk back to the sentence in the transcript it came from.

Break that and you get a very confident wiki with no way to check it. Which is
worse than no wiki.

## Layers

```
  Layer 0   sources/            raw external truth, immutable
  Layer 1   daily/              chronological session capture, append-only
  Layer 2   resonant excerpts   exact language, objections, proof, mistakes
  Layer 3   "use this" material prompts, checklists, scripts, playbooks
  Layer 4   wiki/, areas/       synthesis
  Layer 5   outputs/            expressed work: docs, code, published things
```

Do not summarise everything. Summarise when something is being reused,
repeated, or turned into action. Most captured material should stay at layer 0
or 1 forever, and that is fine. Storage is cheap and premature synthesis loses
detail you cannot get back.

## PARA, with two extra layers

The action-horizon overlay is standard PARA:

| PARA role | Here | Meaning |
|---|---|---|
| Projects | `projects/` | Active outcomes with a finish line |
| Areas | `areas/` | Ongoing responsibilities, no finish line |
| Resources | `wiki/`, `references/` | Reusable knowledge |
| Archives | `archives/` | Inactive context |

Plus two protected capture layers PARA does not have: `sources/` and `daily/`.
They are adjacent to PARA, not normal moveable PARA material. Do not tidy them.

Routing rule when something could go in two places: **choose the folder that
matches the next action, and link to the rest.**

## The human-owned boundary

`me/` is yours. An agent proposes changes there and never silently rewrites
them. This is not politeness; it is a correctness constraint. `me/priorities.md`
is the tiebreaker whenever a wiki page and current reality disagree, so it has
to be something you actually endorse rather than something a model drifted into.

`.claude/rules/priorities-auto-update.md` defines how a proposal is surfaced:
a full draft, a visible diff, and a single yes/no/edit.

## Config, not hardcoding

Every LLM prompt in `scripts/` is written against placeholders: `{owner}`,
`{mission}`, `{work}`, `{voice}`, `{domains}`. `scripts/brain_config.py` fills
them from `brain.config.json`, which `/onboard` writes.

This is why the same compiler produces a useful wiki for a solar founder and for
a PhD student. Nothing about a person is baked into the code.

```bash
python3 scripts/brain_config.py    # see the resolved config
BRAIN_OWNER="Someone Else" python3 scripts/compile.py   # env always wins
```

## Two mirrored operating files

`CLAUDE.md` and `AGENTS.md` must stay byte-identical. Claude Code reads the
first, most other agents read the second. `compile.py` writes both, and
`brain_doctor.py` checks they match.

`CLAUDE.md` has three machine-managed regions:

```
<!-- compile:locked start -->    never touched by the compiler: the invariants
<!-- compile:efficiency start --> token-efficiency guidance
<!-- compile:rules start -->     written from your feedback memories
```

Everything outside those markers is yours to edit freely.

## Sync

`scripts/sync.py` runs on `SessionStart` (pull) and `SessionEnd` (push). Three
design choices, each from a real failure:

- **Commit-first.** Any dirty or untracked file is committed before touching
  origin. Kills "untracked file would be overwritten by checkout" and autostash
  surprises. Nothing is ever lost.
- **Merge, not rebase.** `.gitattributes` sets `merge=union` on append-only
  files, so two devices appending to `log.md` combine automatically instead of
  conflicting. A merge of many diverged commits also cannot half-apply and
  strand the repo, which a long rebase can.
- **Flag, do not give up.** A genuine content conflict aborts cleanly and writes
  `.state/SYNC_CONFLICT` so the status line nags until a human reconciles.
  Silent divergence is the worst outcome and this makes it loud.

## What runs when

| Trigger | Runs | Why |
|---|---|---|
| SessionStart | `sync.py pull` | see what other devices wrote |
| SessionStart | `maybe_compile.py` | spawn a compile if one is overdue, non-blocking |
| SessionStart | `health_check.py` | surface silently failing background jobs |
| UserPromptSubmit | `activator.py` | catch correction signals, heartbeat the compiler |
| PostToolUse (Bash) | `error_detector.py` | log error patterns to `learnings/` |
| SessionEnd | `session_end_post.py` | mark a compile as needed |
| SessionEnd | `evolve.py` | look for repeated workflows worth a skill |
| SessionEnd | `sync.py push` | get the work to origin |
| PreCompact (manual) | `flush.py` | extract the transcript before context is lost |

Every hook is wrapped so it cannot raise into the session, and every one exits 0.
A broken hook must never block you from working.

## State

`.state/` holds machine-local state: last-compile timestamps, locks, logs,
embedding indexes. It is gitignored on purpose. It is per-machine, and syncing
it would make two devices fight over whose turn it is to compile.
