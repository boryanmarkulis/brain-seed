---
name: reflect
description: Use when the owner is ending their day, reflecting on what happened, closing the daily loop, or preparing tomorrow's plan.
allowed-tools: Read Write Edit Bash Glob Skill
---

End-of-day reflection ritual. Closes the day's loop in one shot:
1. Take your voice dump on the day.
2. Light-clean it and append to today's `daily/YYYY-MM-DD.md` under `## Reflection`.
3. Run compile silently to keep CLAUDE.md in sync (no report).
4. Lock tomorrow's One Thing through one short drill against `me/priorities.md`, then break it into committed sub-steps.
5. Write tomorrow's `daily/YYYY-MM-DD.md` with a `## Plan` section so you can open Obsidian in the morning and just execute.

What `/reflect` does NOT surface: wiki consolidation, CLAUDE.md rule-sync, priority/comp proposals. Compile still runs (step 3) to keep CLAUDE.md current, but its output is never shown. The local wiki compiler (`scripts/maybe_wiki.py`, run on a schedule) folds the day into the wiki by itself. Priorities adapt live in-session via `.claude/rules/priorities-auto-update.md` and nowhere else, so nothing catches a missed shift later. `/reflect` stays a simple closing rite.

## When to use

Run `/reflect` once at end of day. Idempotent within a day: re-running regenerates tomorrow's Plan with the latest context.

---

---

## HARD RULE: the after-midnight date (never get this wrong again)

`/reflect` runs on the **lived day**, not on the system date. you often closes the day after midnight.

Always run `date "+%Y-%m-%d %H:%M %Z"` as the very first command of the skill. Then:

- If local time is **00:00 to 04:59**, the lived day is **yesterday** (system date minus 1 day).
  - Reflection goes in `daily/<system-date minus 1>.md`
  - Tomorrow's Plan goes in `daily/<system-date>.md` (the day the owner wakes into after sleeping)
- If local time is **05:00 or later**, the lived day is the system date.
  - Reflection goes in `daily/<system-date>.md`
  - Tomorrow's Plan goes in `daily/<system-date plus 1>.md`

The reflection day and the plan day are **always consecutive**. Never leave a gap and never skip a file.

Sanity check before writing: the reflection file should already contain a `## Plan` block with checkboxes that were worked through. If the file you are about to write the reflection into has no lived-in Plan, you have the wrong day. Stop and check.

If you name dates that are not consecutive, ask one short question before writing rather than creating a gap.

---

## Process - Phase A: Take the dump

### Step 1: Read context for the close

In parallel:
- `me/me.md`, `me/work.md`, `me/priorities.md`, `me/goals.md` - voice and mission anchors
- `.claude/rules/communication-style.md` - voice rules (no emojis, no em dashes, no AI-tells)
- Today's `daily/YYYY-MM-DD.md` if it exists (the human file: Plan plus anything you added by hand)
- Today's `daily/sessions/YYYY-MM-DD-sessions.md` if it exists (the machine file: session captures agents wrote during the day)

### Step 2: Prompt for the dump

If the user hasn't already pasted a voice dump in their invocation, ask:

```
Drop the voice dump. Ramble freely - what happened today, what landed, what flopped, what's stuck, what's next. I'll clean it up and close the day.
```

Wait for paste.

If they invoked `/reflect <text>` with content, skip the prompt and use that text.

---

## Process - Phase B: Clean the dump

Apply **light structure** only. Same fidelity as `/writing` grammar pass.

**Do:**
- Fix transcription errors (mishearings, dropped words, broken homophones).
- Fix typos, grammar, punctuation.
- Group related thoughts into paragraphs. A wall of text becomes 3-7 paragraphs.
- Drop pure repetition (you said the same sentence twice mid-thought).

**Don't:**
- Change word choice, phrasing, or sentence structure.
- Bullet-distill or summarize. The reflection stays prose.
- Add headings or structure beyond paragraph breaks.
- "Improve" the voice. Future you should hear *himself* on the page.

Hard bans: no emojis, no em dashes (use a hyphen, comma, or new sentence). No filler openers. No AI-tells.

---

## Process - Phase C: Insert reflection into today's daily

Reflection date: the lived day resolved by the after-midnight rule above.

If `daily/YYYY-MM-DD.md` does not exist, create it with `# YYYY-MM-DD` as the H1.

**Placement:** The daily file is the human file (Plan + Reflection only - session captures live in `daily/sessions/`). The reflection goes after the `---` that closes the `## Plan` block, and before the `## Sessions` embed heading if one exists. The resulting structure should be:

```
## Plan
...
---

## Reflection

[cleaned dump as paragraphs]

## Sessions

![[YYYY-MM-DD-sessions]]
```

If there is no `## Plan` block, insert at the top of the file after the H1. If the file already contains inline `## Session` captures, insert the reflection before the first one.

If a `## Reflection` section already exists (re-running same day), append a new `### YYYY-MM-DDTHH:MM` sub-heading under it with the new dump. Never edit the existing one.

---

## Process - Phase D: Sync CLAUDE.md (silent)

Run compile so the CLAUDE.md / AGENTS.md Learned Rules + efficiency sections stay in sync with the feedback memories. Do this quietly:

```bash
python3 scripts/compile.py 2>&1
```

Do NOT report wiki edits, CLAUDE.md changes, or anything else from this step. Say a word about it only if it exits non-zero with a hard error that needs attention. Otherwise it is invisible. Wiki folding belongs to the scheduled `maybe_wiki.py` job, not to this skill. Nothing catches a missed priority shift later, so surface one now if you see it.

---

## Process - Phase E: Lock tomorrow's plan (cash-filtered)

This phase is no longer silent auto-synthesis. It runs a short interview, filters tomorrow's One Thing against `me/priorities.md`, and breaks it into committed sub-steps. The voice dump from Phase A already holds most of the signal, so this is one drill plus a breakdown, not a full morning-style interview.

### Step 1: Read planning inputs

In parallel:
- Today's `daily/YYYY-MM-DD.md` (now includes the freshly-written reflection) - already in context from Phase A, no re-read needed
- `me/priorities.md` - already in context from Phase A, no re-read needed
- Open Threads from last 7 days via Bash (not full file reads):
  ```bash
  ls daily/*.md daily/sessions/*-sessions.md 2>/dev/null | awk -F/ '{print $NF "\t" $0}' | sort | tail -16 | cut -f2 | xargs grep -l "Open Threads" 2>/dev/null | xargs grep -A 30 "### Open Threads" 2>/dev/null
  ```
  One command, extracts only the Open Threads block from each recent file.

### Step 2: Pick the One Thing and drill it

Derive a candidate One Thing from today's dump, priorities, and open threads. Then check it against the top of `me/priorities.md`: does it serve the current stated focus?

Ask you exactly one forcing question, naming the candidate:

```
Tomorrow's One Thing looks like [candidate]. Is that the right call, or is there something that matters more right now?
```

Wait for the reply. Loop at most once. If the candidate is maintenance past its cap, or building something new, or low-leverage tinkering, push back in one line per the drift flags. If they hold, it is their call, write what they say. Priorities are the lens, not a veto.

### Step 3: Break the One Thing into sub-steps

Split the locked One Thing into 2-5 atomic sub-steps. Each must be:
- shippable in one sitting,
- a real-work artifact, not prep theater (kill "map / draft / outline / think about" unless the artifact itself is the deliverable, e.g. "the actual email to the client"),
- concrete enough that you can just do it tomorrow.

These sub-steps are the checkboxes. This is the "scheduled so I actually do them" part: the One Thing arrives already broken down, not as a vague heading.

### Step 4: (removed)

Do not interrogate the owner for metrics they did not volunteer. If a number is not in the dump and not in a system you can read, leave it out rather than asking.

### Step 5: Write tomorrow's daily file

Tomorrow's date: `YYYY-MM-DD` of the day after today.

Write `daily/YYYY-MM-DD.md` (overwrite if it exists - Plan regenerates each `/reflect` run):

```
# YYYY-MM-DD

## Plan

**One Thing:** [the locked One Thing]

- [ ] [sub-step]
- [ ] [sub-step]
- [ ] [sub-step]

---

## Sessions

![[YYYY-MM-DD-sessions]]
```

This file stays human-owned: `flush.py` writes session captures to `daily/sessions/YYYY-MM-DD-sessions.md`, and the `![[...]]` embed transcludes them into this file when viewed in Obsidian. you can edit the Plan in Obsidian or VS Code all day without any automated write touching the file.

### Step 6: Final report

Print to user:

```
Day closed.

Reflection: daily/YYYY-MM-DD.md (today)
Plan: daily/YYYY-MM-DD.md (tomorrow)
  One Thing: [the One Thing]
  [N] sub-steps set
[Optional: link any external capture note for the day, e.g. a screen-activity digest. Omit this line if you have none.]

Edit in Obsidian before bed if you want to add or reword anything.
```

No further commentary. The day is closed.

---

## Constraints

- Voice-cleaning is light structure only. Never bullet-distill, never rewrite.
- Tomorrow's file is overwriteable; today's reflection is append-only.
- No emojis, no em dashes, no filler openers, no AI-tells. Match `.claude/rules/communication-style.md`.
- Checkboxes are atomic and concrete. Vagueness is the failure mode.
- The morning ritual is "open Obsidian, see the plan." `/reflect` materializes that plan with full day-end context, then steps back.
