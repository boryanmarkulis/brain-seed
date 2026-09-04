# The loop

Three loops run. They are what make this different from a folder of notes.

---

## Loop 1: session capture

**Problem it solves.** The most valuable thinking you do happens in a session
with your agent, and then it evaporates. You solved something at 11pm on a
Tuesday and by Friday neither of you remembers how.

**How it works.**

1. You work. Normal session, nothing special.
2. `SessionEnd` writes a marker to `.state/needs-compile`.
3. `flush.py` reads the session transcript (JSONL from Claude Code or Codex) and
   sends it to a cheap fast model with one instruction: extract what actually
   happened, and what is worth keeping long term.
4. The result is appended to `daily/YYYY-MM-DD.md` under dated headings.

The extraction captures two different things on purpose:

- **What happened** - the work done, the people touched, the decisions made.
  This is the activity log.
- **What is worth keeping** - decisions, lessons, patterns, references, open
  threads. This is what the wiki compiler eats.

**Run it by hand:**

```bash
python3 scripts/flush.py --inbox path/to/transcript.txt
```

The `--inbox` path takes any pasted transcript: a web chat, a meeting, a Codex
session, anything. Same extraction, same destination.

**Watch out for.** Transcripts are written asynchronously, so `flush.py` waits
up to 60 seconds for the file to appear. If your daily file is missing a
session, check `log.md` for a `MIGRATION/ERROR` line rather than assuming the
hook did not fire.

---

## Loop 2: the self-compiling wiki

**Problem it solves.** Capture without synthesis is hoarding. You end up with
two thousand files and no answers.

**How it works.**

1. `compile.py` reads `.state/last-compile.txt` and collects everything in
   `sources/`, `daily/`, and `projects/` modified since.
2. It builds a payload: the wiki index, existing pages, the new material, and
   your operating context (project READMEs, the PARA map, your favorite
   problems).
3. It asks a model which concept pages need creating or updating, and gets back
   full page content for each.
4. It writes those pages, updates `wiki/index.md`, and commits.

**Every page carries frontmatter:**

```yaml
---
type: concept | lesson | person | playbook
updated: 2026-09-04
sources: [sources/web/some-article.md, daily/2026-08-30.md]
confidence: high | medium | low
---
```

`sources` is the provenance chain. `confidence` is how well-supported the claims
are. `updated` is what you check against `me/priorities.md` when a page and
reality disagree. **Reality wins.** A wiki page is synthesis, not ground truth.

**Focused runs.** A general compile averages everything. To make one lane of
your knowledge deep, write a focus definition:

```bash
cp references/focus/example-copywriting.md references/focus/negotiation.md
# edit the Include and Skip lists
python3 scripts/compile.py --focus negotiation
```

**Querying it.** Never load `wiki/index.md`. It grows to tens of thousands of
tokens and it is only a table of contents.

```bash
python3 scripts/wiki_search.py --pages -k 6 "how should I price a retainer"
```

Section-level semantic search. Read only the hits. Pass `--stop` on your last
query to free the embedding server's memory.

---

## Loop 3: correction becomes standing context

This is the one that makes the system feel alive.

**Problem it solves.** You correct your agent. It apologises. Next week it makes
the identical mistake, because nothing about the correction survived the session.

**How it works.**

1. You correct the agent. `activator.py` also watches for correction phrases
   ("that's wrong", "not what I asked") and nudges it to log the error.
2. Per `.claude/rules/learn-from-corrections.md`, the agent writes a
   `feedback_*.md` memory: the rule, why it matters, how to apply it.
3. `compile.py` reads every feedback memory, clusters them by theme, and
   rewrites the `## Learned Rules` block inside `CLAUDE.md` and `AGENTS.md`.
4. Every future session loads that block automatically.

**What it looks like after a few months.** A dozen dense lines, each one a
cluster of related corrections pointing at the rule files that hold the detail:

```
- Validate operational claims against authoritative records before reporting;
  verify sample size, scope, and provenance -> feedback_verify_segment_cuts.md
- Preserve exact supplied wording, names, and punctuation; use real examples
  from the target channel -> feedback_templates_are_verbatim.md
```

Nobody wrote that by hand. It is the compressed memory of every time you had to
correct something.

**Adjacent: `evolve.py`.** On session end it looks for repeated tool-call
patterns across sessions and repeated error patterns. When a threshold trips, it
proposes a new skill or a skill update into `learnings/SKILL-CANDIDATES.md`. It
only calls a model when a threshold actually fires, so it is nearly free.

---

## Keeping the loops honest

`health_check.py` runs at session start and prints nothing when everything is
fine. When a background job has been failing it says so, with the date the
streak started and the count.

This exists because of a real nine-day outage where an export failed 573 times
in a row, logged every failure, and nobody read the log. **Silent failure is the
default failure mode of every system like this.** The loop that watches the
loops is not optional.

Add your own job to the watch list by adding an entry to `health_checks` in
`brain.config.json`.
