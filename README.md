# brain-seed

A second brain that runs itself.

Clone it, spend 40 minutes answering questions, and you get a plain-markdown
knowledge system that captures what you do, compiles it into a wiki you can
actually query, and gets sharper every time you correct it. No app, no
subscription, no database. Just folders, markdown, and a handful of Python
scripts your AI coding agent already knows how to run.

It works in Claude Code, Codex, Cursor, Claude Desktop, VS Code, VS Codium, or
any agent that can read a repo and run a shell command. It is markdown all the
way down, so nothing here locks you in.

---

## Why this exists

Most "second brain" setups fail for the same reason: **you have to maintain
them.** You capture things enthusiastically for three weeks, the folder
structure drifts, nothing gets linked, and six months later you have a graveyard
of notes you never read.

This one is built the other way around. The maintenance is the software's job:

- **Your sessions are captured automatically.** Every working session with your
  agent gets extracted into a dated daily file. You do not write it.
- **The wiki compiles itself.** A background job reads new sources and daily
  notes, decides which concept pages they belong to, and rewrites those pages,
  citing the exact source files. Optionally on a local model, so it is free.
- **The agent's instructions rewrite themselves.** When you correct the agent,
  it saves the correction as a memory. A compiler clusters those memories and
  rewrites the rules section of `CLAUDE.md`. Your operating context is a living
  document, not a file you keep meaning to update.
- **It tells you what is broken.** A health check surfaces background jobs that
  have been silently failing, which is the failure mode that kills these systems.

You still do the thinking. The system stops being a chore.

---

## The loop

```
      you work with your agent
               |
               v
    [ session capture ]  hooks extract decisions, lessons, and what
               |         actually happened into daily/YYYY-MM-DD.md
               v
       sources/  +  daily/          <- immutable raw truth
               |
               v
    [ compile ]  routes new material to concept pages, rewrites them
               |  in place, cites the source paths it used
               v
            wiki/                   <- distilled, linked, queryable
               |
               v
    [ wiki_search ]  semantic search so a skill loads the one paragraph
               |     it needs instead of the whole vault
               v
      your next session, better informed
```

And running alongside it:

```
    you correct the agent  ->  feedback memory saved
               |
               v
    [ compile ]  clusters memories, rewrites the Learned Rules
               |  block inside CLAUDE.md
               v
    every future session starts already knowing
```

---

## Quickstart

**Requires:** Python 3.10+, git, and an AI coding agent CLI (`claude` or `codex`)
that you are already logged into. `pip3 install numpy` if you want semantic
search.

```bash
git clone https://github.com/boryanmarkulis/brain-seed.git my-brain
cd my-brain
rm -rf .git && git init          # make it yours, drop this repo's history
python3 scripts/brain_doctor.py  # see where you stand: 22/100, that's correct
```

Then open the folder in your agent and say:

```
/onboard
```

That is the whole setup. `/onboard` interviews you for about 40 minutes and
writes `me/`, `CLAUDE.md`, `brain.config.json`, and your voice rule from your
own words. It is a real conversation, not a form. Answer properly; everything
you say there becomes standing context for every future session.

After that:

```
/connect notion       # wire up wherever your notes already live
/pull <url>           # feed it. your own writing first.
/doctor               # check progress. it names one next action.
```

Then run `/action` in the morning and `/reflect` at night. The loop needs a few
days of daily files before the wiki starts producing anything good. That is
normal. It compounds.

---

## What you get

### Folders

| Folder | Holds | Rule |
|---|---|---|
| `sources/` | Raw external truth: transcripts, articles, exports | **Immutable.** Never LLM-edited. This is what makes everything else trustworthy. |
| `daily/` | Session captures, one file per day | Append-only. Written by hooks, not by you. |
| `wiki/` | Compiled concepts, lessons, people, playbooks | LLM-maintained. Every page cites its sources. |
| `me/` | Who you are, what you do, what matters now | Human-owned. The agent proposes changes, never silently rewrites. |
| `projects/` | Active work with a finish line | Each one has a README the agent reads first. |
| `areas/` | Ongoing responsibilities with no finish line | Includes `favorite-problems.md`, the filter for what to notice. |
| `decisions/log.md` | Every real decision, dated | Append-only. Reversals are new entries, not edits. |
| `references/` | SOPs, API notes, operating guides | Durable instructions the agent follows. |
| `outputs/` | Finished, shippable artifacts | The Express layer. |
| `archives/` | Retired work | Nothing gets deleted, just moved out of the way. |

It is [PARA](https://fortelabs.com/blog/para/) as an overlay, with two protected
capture layers (`sources/`, `daily/`) that PARA does not have and that this
system depends on.

### Skills

Rituals your agent can run. `/onboard`, `/connect`, `/doctor`, `/audit`,
`/action`, `/reflect`, `/pull`, `/ingest`, `/update`, `/journal`, `/one-thing`,
`/level-up`, `/align`, `/roast`, `/grill-me`, `/review`, `/para-organizer`,
`/session-handoff`, `/skill-builder`.

Start with three: **`/onboard`** to set up, **`/reflect`** every night to close
the day, **`/doctor`** whenever you want to know what to do next.

Full list and what each one is for: [`docs/05-the-skills.md`](docs/05-the-skills.md).

### Scripts

The engine. All plain Python, no framework.

| Script | Does |
|---|---|
| `brain_doctor.py` | Scores setup completeness, names your single next action |
| `brain_audit.py` | Link graph, orphans, broken links, source coverage |
| `compile.py` | Routes new material into wiki pages, rewrites `CLAUDE.md` rules |
| `flush.py` | Extracts a session transcript into today's daily file |
| `sync.py` | Commit-first, merge-based, self-healing sync across devices |
| `health_check.py` | Surfaces background jobs that have been quietly failing |
| `wiki_extract.py` / `wiki_consolidate.py` | The free local-model wiki pipeline |
| `wiki_embed.py` / `wiki_search.py` | Semantic search over the wiki |
| `pull.py` / `ingest.py` | Get external material into `sources/` |
| `evolve.py` | Watches for repeated workflows, proposes new skills |

---

## Two ways to compile the wiki

**Cloud (default).** `compile.py` shells out to whichever agent CLI you are
already logged into. No API key, no extra bill beyond your existing plan.

**Local and free.** A two-stage pipeline runs on
[llama.cpp](https://github.com/ggerganov/llama.cpp) against a quantised model on
your own machine. Stage 1 extracts claims with verbatim evidence quotes,
machine-verified against the source. Stage 2 merges verified claims into pages.
Nothing leaves your laptop and nothing costs money. It is gated so it only runs
when the machine is idle and on power.

Setup: [`docs/04-the-local-model.md`](docs/04-the-local-model.md).

---

## Portability

Everything is markdown and Python. Nothing is tied to one vendor.

- **Claude Code** - hooks in `.claude/settings.json` run the loop automatically.
- **Codex, Cursor, and others** - read `AGENTS.md` (byte-identical to
  `CLAUDE.md`). Run the scripts manually or from cron.
- **Claude Desktop / claude.ai** - point it at the repo, or sync via git.
- **Obsidian** - the vault is standard markdown with `[[wikilinks]]`. Open the
  folder and the graph view just works.
- **No agent at all** - it is still a well-organised folder of notes.

Details and per-tool setup: [`docs/06-running-it-anywhere.md`](docs/06-running-it-anywhere.md).

---

## Docs

| | |
|---|---|
| [`00-quickstart.md`](docs/00-quickstart.md) | The first hour, step by step |
| [`01-architecture.md`](docs/01-architecture.md) | How the pieces fit and why |
| [`02-the-loop.md`](docs/02-the-loop.md) | Session capture, compile, and self-improvement in detail |
| [`03-getting-your-stuff-in.md`](docs/03-getting-your-stuff-in.md) | Backfilling years of notes, transcripts, and writing |
| [`04-the-local-model.md`](docs/04-the-local-model.md) | Running the wiki compiler free, offline |
| [`05-the-skills.md`](docs/05-the-skills.md) | Every skill, what it does, when to run it |
| [`06-running-it-anywhere.md`](docs/06-running-it-anywhere.md) | Codex, Cursor, VS Code, Obsidian, phone |
| [`07-customising.md`](docs/07-customising.md) | Make it yours without breaking the invariants |

---

## Credit

The original seed idea and folder shape come from
[AIS-OS](https://github.com/nateherkai/AIS-OS) by @nateherkai, and the
walkthrough video that goes with it. This repo is what that grew into after
months of daily use: the self-compiling wiki,
the local model pipeline, the correction-to-rules loop, the health checks, and
the interview that sets it all up.

## License

MIT. Take it, fork it, make it yours. That is the point.
