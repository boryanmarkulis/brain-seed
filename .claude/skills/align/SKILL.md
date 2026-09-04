---
name: align
description: Strategic alignment audit. Checks whether the owner's actual work in the last 14 days matches their stated mission, priorities, and direction. Flags drift, cold priorities, and profit/build imbalance.
triggers:
  - /align
  - "am I on track"
  - "am I aligned"
  - "check alignment"
  - "mission check"
  - "am I drifting"
allowed-tools: Read Bash Glob
---

# /align - Mission & Time Alignment Audit

Read-only diagnostic. Never edit files. The only writable side-effect is the optional saved report.

## What to Read

Gather these before producing output. Never write to them.

**Intent layer** (what should be happening):
- `CLAUDE.md` - mission, identity, active work, current thread list
- `me/priorities.md` - current prioritized list
- `me/goals.md` - milestones, paused items
- `me/me.md` - identity and context
- `me/work.md` - revenue, strategy, tools
- `areas/favorite-problems.md` - mission filter questions
- `decisions/log.md` - last 60 days of direction changes

**Activity layer** (what actually happened):
- `daily/` - last 14 days of daily entries, including the matching `daily/sessions/*-sessions.md` capture files (read each file)
- `log.md` - last 50 lines
- `network/log.md` - last 30 lines
- `projects/*/README.md` - all active project READMEs
- Run: `git log --since="14 days ago" --oneline` - commit signal
- Whichever publishing or distribution channel `connections.md` lists, if any: how recently the owner shipped, and what the last few pieces were about

---

## Analysis Steps

### 1. Build the priority list

From `me/priorities.md`, extract each numbered priority. This is the ground truth for what should be getting attention.

### 2. Build the activity signal

Scan all daily files, `log.md` tail, and git commits. For each priority, count:
- Daily file mentions (how many days had an entry touching it)
- Commit count touching it
- Whether any session log entries reference it

Classify each priority:
- **Active** - touched on 3+ of last 14 days
- **Warm** - touched 1–2 days
- **Cold** - zero touches in 14 days

### 3. Mission check

For each major activity cluster identified from the activity layer, ask: does it advance one of the `favorite-problems.md` questions? Group into:
- **On-mission** - directly advances the mission in `CLAUDE.md`, or the tools and systems that do
- **Infrastructure** - builds capability that enables the mission (acceptable)
- **Off-thesis** - neither

### 4. Big picture check

Step back from tactical activity and ask whether the current bets are still the right bets. Read `me/work.md` and the last 60 days of `decisions/log.md` to understand what's being wagered.

Then ask these questions honestly:

1. **Bet validity** - Are the current product bets still the highest-leverage path to the mission given what's happened in the last 14 days? Have any market signals, results, or new information changed the calculus?

2. **Skills-to-impact fit** - Read the strengths in `me/me.md`. Is the owner deploying those at the highest-leverage levers available to them? Or is there a more impactful path they already have the skills for that is being ignored?

3. **Opportunity cost** - Is there an obvious bet being left on the table that would have higher mission impact and a plausible path to profitability?

4. **Thesis integrity** - Does a clear chain still connect the daily work to the mission stated in `CLAUDE.md`? If the chain needs more than two hops to make sense, flag it.

If all four hold, say so briefly. If any surface a real concern, name it directly. This is not a pep talk.

### 5. Drift signals

Check each of these:
- Priorities with zero touches in 14 days (cold priorities)
- Work that appears frequently in activity but is absent from `me/priorities.md` - was there a decision logged for it?
- Projects in `projects/*/README.md` that have recent activity but are not in the priority list
- Items in `me/goals.md` marked paused that still appear in activity

### 6. Publishing check

If the owner has a publishing habit listed in `connections.md` or `me/work.md`, check when they last shipped. More than 7 days ago is cold. If they have no publishing habit, skip this section entirely rather than inventing one.

Read whatever they published in the last 14 days and identify the theme of each piece. Classify each:
- **On-mission** - squarely inside the mission stated in `CLAUDE.md`
- **Adjacent** - founder life, productivity, mindset (builds the brand that serves the mission)
- **Off-thesis** - neither

Note: publishing is a distribution channel and a brand asset, so Adjacent counts as acceptable. Off-thesis is the flag.

### 7. Profit vs build balance

From `me/work.md`, identify the paid engagements and what each pays. Count activity items tied to paid work against unpaid tool-building or exploration.

Classify:
- **Healthy** - paid work has equal or more activity than unpaid builds
- **Inverted** - unpaid work dominates; revenue-generating work is cold

### 8. Verdict

Based on the above, assign one overall verdict:
- **Aligned** - top priorities are active, no major drift, paid work is healthy
- **Drifting** - 1–2 priorities cold, or mild off-thesis activity building up
- **Off-track** - multiple cold priorities, profit/build inverted, or significant off-thesis work

---

## Output Format

Produce this exactly. Fill in real values from your analysis.

```
## Alignment Audit - {YYYY-MM-DD}

**Verdict: {Aligned | Drifting | Off-track}**
{One sentence explaining why.}

### Mission Check
Mission: {read from CLAUDE.md}
{N} major activity clusters in last 14 days:
- On-mission: {M} ({list them})
- Infrastructure: {K} ({list them})
- Off-thesis: {O} ({list them or "none"})

### Priority Alignment
| # | Priority | Touches (14d) | Status |
|---|----------|---------------|--------|
| 1 | {priority name} | {X days, Y commits} | Active/Warm/Cold |
| 2 | ...
| ...

### Drift Signals
- Priorities with zero touches: {list or "none"}
- Unlogged work that grew: {list or "none"}
- Active projects off the priority list: {list or "none"}
- Paused items still showing up: {list or "none"}

### Publishing
Last published: {YYYY-MM-DD} ({X} days ago) - {Active (<7d) | Warm (7-14d) | Cold (14d+)}
Posts in last 14d: {N} - On-mission: {M}, Adjacent: {K}, Off-thesis: {O}
{One line only if cold or off-thesis.}

### Profit vs Build Balance
{Client or income source, and what it pays}: {X activity items}
Unpaid builds: {Y activity items}
Ratio: {Healthy | Inverted}
{One line if inverted.}

### Big Picture
Bets currently in play: {list from me/work.md}
1. Bet validity: {holding / concern - one line}
2. Skills-to-impact fit: {holding / concern - one line}
3. Opportunity cost: {none visible / flagging X - one line}
4. Thesis chain: {intact / broken at X - one line}
Overall: {Sound | Questionable | Broken}
{One sentence if anything is not holding.}

### Top 3 Realignment Moves
1. {Specific action - what to start, stop, or re-prioritize}
2. {Specific action}
3. {Specific action}
```

---

## Tone

Honest, not reassuring. If something is cold, say it's cold. If profit/build is inverted, say so. The point is to catch drift early, not to feel good.

No emojis. No em dashes. Dense output.

---

## Decision Logging

After producing the audit output, check whether the session surfaced any strategic decisions or clarity not already in `decisions/log.md`. If yes, append them automatically -- no need to ask.

Format: `[YYYY-MM-DD] DECISION: ... | REASONING: ... | CONTEXT: align audit {YYYY-MM-DD}`

Only log if something meaningfully new emerged: a direction change, a confirmed bet, a resolved strategic question. Do not log the audit itself as a decision.

---

## Save Report (optional)

If you asks to save, write to `audits/align-{YYYY-MM-DD}.md`. Create the `audits/` folder if needed. Never save unless asked.
