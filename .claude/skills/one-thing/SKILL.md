---
name: one-thing
description: Find the single highest-leverage move. Analyzes the whole Brain for what has actually produced valued results, maps the path that creates them, finds the constraint, and argues in detail for the ONE thing to do such that everything else gets easier or unnecessary.
triggers:
  - /one-thing
  - /onething
  - "what is the one thing"
  - "what's the lever"
  - "where's my leverage"
  - "what should I focus on"
  - "distill this down"
allowed-tools: Read Bash Glob Grep Task
---

# /one-thing - The Focusing Question

Read-only analysis. Never edit Brain files. The only writable side-effect is the optional saved report and an appended decision log entry.

## The question this skill answers

> **What is the ONE thing I can do right now, such that by doing it everything else becomes easier or unnecessary?**

This is not `/align` and not `/action`.

- `/align` asks: am I working on the right priorities? (compliance check)
- `/action` asks: what do I do today? (a day plan)
- `/one-thing` asks: where is the lever? (leverage analysis)

The output is one lever, a detailed argument for it, the named runners-up and why they lose, and the first concrete move.

---

## Altitude: this is the whole point of the skill

The answer must be **a way to spend your time**. A channel. A capability. A category of work
you could pour forty hours into next week.

It is never a task, a toggle, a setting, a single fix, or one item off a checklist. Those are
`/action` output. If the answer could be finished in an afternoon, the altitude is wrong. Go up
a level and ask what that fix is an instance of.

Derive the right altitude from the owner's own mission and work. Read the mission in `CLAUDE.md`,
then read `me/work.md` for the result that matters and the broad ways the owner can create it.
Candidates must be whole **strategies or capabilities**, not settings or isolated tasks.

### The ladder

Every run walks the same four rungs. Only rung 4 is up for debate.

1. **Mission** - read it from `CLAUDE.md`. Settled, not up for debate in this run.
2. **Result** - the concrete value-producing moment defined by the owner's work. Derive it from `me/work.md` every run.
3. **Constraint** - which stage of the value path is limiting that result right now.
4. **THE ONE THING** - the strategy or capability that fixes that constraint and keeps fixing it.

The evidence work still matters. Pull the real numbers, find the real constraint. But the numbers
choose between strategies or capabilities. They are not the answer themselves. A finding like
"this setting is off" is supporting evidence and belongs in the first domino, never in the headline.

---

## Core model: result vs lever

The **result** is the concrete moment when the owner's work creates the value described in
`me/work.md`. Do not assume what that moment is or carry one over from another user. Derive it each
run and state the evidence for it.

Everything else is a **lever**: a strategy or capability that produces that result. A system or
automation can be a lever when evidence shows that it compounds output rather than merely adding
maintenance. Judge it by the leverage test, not by its category.

### The leverage test

A candidate wins on these three:

1. **Multiplier** - does it keep producing next week and every week after without the same input
   of the owner's time?
2. **Durable** - does it survive normal changes in tools, collaborators, clients, or priorities?
3. **Constraint fit** - does it unblock the stage that is actually limiting the result?

A candidate is **hours-bound** if it stops the moment the owner's hands stop. Hours-bound work can
be urgent and necessary. It is rarely the ONE thing unless `me/work.md` shows that direct time is
itself the durable source of value.

---

## What to read

Gather evidence before arguing. Never write to these.

**What creates value (the ground truth)**
- `me/work.md` - what the owner does, who values it, and what result matters
- `me/priorities.md` - the stated shape of the current work
- `decisions/log.md` - last 60 days
- `network/deals/` - live deal stages
- `areas/finances/` if present - what actually landed in the account

**What actually happened**
- `daily/` - last 21 days, plus each matching `daily/sessions/*-sessions.md`
- `log.md` tail 80, `network/log.md` tail 40
- `git log --since="21 days ago" --oneline`
- `projects/*/README.md` for every active project

**What you already learned** (your compiled wiki pages, however many exist)
- `python3 scripts/wiki_search.py --pages -k 6 "<the bottleneck you think you found>"` - run it once you have a candidate lever, not before. It answers "have we already tried this, and what happened". Read only the hits; never read `wiki/index.md`.
- Wiki pages are synthesis, not ground truth. A page's `updated:` date and `sources:` list are the check. If a page contradicts `me/priorities.md`, priorities win and the page is stale.

**Hard numbers where they exist** (prefer real data over the daily-note narrative)
- Read `connections.md` and use whatever is actually wired up: project systems,
  analytics, billing, or other sources named there. Pull the numbers, do not estimate them.
- Any report scripts already built under `scripts/`.
- If nothing is wired up yet, say so plainly rather than guessing. A run built on
  invented numbers is worse than no run.

**Verify every record before counting it.** Check its creator, timestamp, and name against the
source system before it enters a total. Integration-created and test records can inflate counts,
so exclude any record that cannot be matched to a real source event.

If a number is not available in under two minutes of digging, say "unmeasured" and move on. Do not stall the analysis chasing data.

---

## Analysis steps

### 1. Restate the result

One sentence. What is the concrete value-producing moment right now, derived from `me/work.md` and
the mission in `CLAUDE.md`? If the work does not share one result, say so plainly, because that
itself is the finding.

### 2. Map the value path

Draw the real chain from effort to the result named in step 1. Derive every stage from the owner's
files and connected systems. Do not start from a preset commercial funnel. For each stage, get the
real number if one exists and the conversion or handoff to the next stage.

### 3. Find the bottleneck

The bottleneck is the stage with the worst conversion AND meaningful volume above it. Two traps to avoid:

- A stage with terrible conversion but 3 people in it is noise, not a bottleneck. (See `feedback_verify_segment_cuts_on_long_window.md`.)
- The stage you spend the most hours on is often not the constraint. Hours spent is a symptom, not evidence.

Name the bottleneck in one line, with the number behind it.

### 4. Build the candidate list

The candidates are **strategies or capabilities**, at the altitude named above. Build the set only
from evidence in `me/work.md`, `me/priorities.md`, active projects, recent activity, and connected
systems. Do not supply a standing list or import candidates from another user's work.

Never substitute a task for a strategy or capability. If a candidate could be finished in an
afternoon, it is a domino, not a candidate.

### 5. Score every candidate

For each, fill this out honestly:

| Field | What to write |
|---|---|
| Lever | The move, in one line |
| Evidence it works | What in the Brain shows this has produced results before. Cite the file or the number. If nothing, say "unproven." |
| Multiplier? | Does it keep producing without your hours? Yes/No + why |
| Constraint? | Does it hit the stage named in step 3? Yes/No |
| Makes unnecessary | What drops off the list entirely if this is done |
| Time to first result | Hours/days/weeks |
| Cost if wrong | What is burned |

Then score 1 to 5 on each of: **Multiplier**, **Constraint fit**, **Speed to result**, **Proven by past results**. Total out of 20.

### 6. Pick one and argue it

Pick the winner. Then write a real argument, not a summary. It must contain:

- **The claim** - the one thing, in one sentence, concrete enough to start today.
- **Why it wins** - three to five reasons tied to actual evidence from the Brain, with citations.
- **What it makes easier or unnecessary** - the explicit list of work that drops away or gets cheaper. This is the part that justifies the name of the skill. If nothing drops away, the candidate is probably not the ONE thing, so reconsider.
- **The steel-man against it** - the strongest case for the runner-up, stated fairly, then why it still loses.
- **What would prove this wrong** - the specific signal, within a named window, that means abandon it.

### 7. The first domino

Now, and only now, get specific. Name the one concrete action that starts the winning strategy or
capability moving. Use real work, never "map", "draft", "outline", "plan", or "think about."
(See `feedback_plan_action_quality.md`.) Name the artifact, system, or collaborator involved.

Then name the next two dominoes after it, so the path is visible.

### 8. The stop list

Name up to three things currently getting your hours that the winner makes unnecessary or lower priority. Be specific and cite where you saw the hours going. This is the honest part. It will sting a little. Say it anyway.

---

## Output format

```
## The One Thing - {YYYY-MM-DD}

**Mission:** {read from CLAUDE.md}
**The result:** {the conversion moment, read from me/work.md}
**The constraint right now:** {one line + the number behind it}

### THE ONE THING
{The strategy or capability. A way to spend your time, not a task.
One sentence, plus one on what it means in practice.}

### Why this wins
1. {reason + evidence citation}
2. {reason + evidence citation}
3. {reason + evidence citation}

### What this makes easier or unnecessary
- {work that drops off entirely}
- {work that gets cheaper}

### The value path
| Stage | Number | Conversion |
|---|---|---|
| ... | ... | ... |

### Candidates considered
| Lever | Mult | Bottle | Speed | Proven | Total |
|---|---|---|---|---|---|
| **{winner}** | x | x | x | x | **xx/20** |
| {runner-up} | ... | | | | xx/20 |
| ... | | | | | |

### The strongest case against
{Steel-man the runner-up in 2-3 sentences, then one sentence on why it still loses.}

### First domino
**Now:** {the concrete action}
**Then:** {next}
**Then:** {next}

### Stop list
- {thing to stop, and where the hours were going}
- {thing to stop}

### Kill signal
{The specific signal, by a named date, that means this was the wrong lever.}
```

---

## Tone

Talk like a friend who has read everything and is not going to flatter you. Take a real position. A list of options with no pick is a failed run of this skill.

Rules: no emojis, no em dashes, no jargon. Short sentences. Dense.

---

## Hard rules

1. **Altitude first.** The headline is a channel, a way to spend your time. If it could be done in
   an afternoon, it is a domino, not the one thing. Re-read the Altitude section before answering.
2. **Pick one.** Never hedge, never return two co-winners.
3. **Cite evidence.** Every claim about what has worked points at a file, a number, or a dated daily entry. If it is a hunch, label it a hunch.
4. **Automation is not drift.** Judge it by the leverage test, never by how it looks.
5. **Volume before verdict.** Never call a stage broken on a handful of data points.
6. **No new-work bias.** The winner is often something already half-built that needs finishing, not a new idea. Weight existing assets heavily.
7. **Real actions only.** No "map" or "draft" steps in the dominoes.

---

## Decision logging

If the run surfaces a genuine strategic call, append to `decisions/log.md`:

`[YYYY-MM-DD] DECISION: ... | REASONING: ... | CONTEXT: /one-thing {YYYY-MM-DD}`

Only when something meaningfully new lands. Do not log the analysis itself.

If the run materially changes what the top priority is, follow `.claude/rules/priorities-auto-update.md`: draft the update to `me/priorities.md`, show the before and after, and ask for one-tap confirm. Never write `me/` silently.

## Save report (optional)

Only if asked: write to `audits/one-thing-{YYYY-MM-DD}.md`.
