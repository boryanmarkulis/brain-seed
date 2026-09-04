---
name: action
description: Morning ritual. Interview-first. One Thing + up to 2 supporting actions, mission-filtered, real-work-only.
allowed-tools: Read Write Edit Bash Glob Grep
---

Morning sibling to `/reflect`. Opens the day by helping you think better, never thinking for you.

The skill is **interview-first**. Files exist as a critique lens, not a synthesis source. your head is the highest-signal input; the agent's job is to sharpen what's already there, not invent priorities from open-thread soup.

## Core rules

- **AI does not think for you.** It interviews, critiques, sharpens.
- **One Thing per day.** Single, shippable today, single sitting if possible.
- **Hard cap at 3 items total** (One Thing + up to 2 supporting). Plans with 5+ items are wishlists.
- **Source = your interview.** The agent adds nothing except carryover from the most recent Plan (if within 3 days and you didn't mention it).
- **Three critique filters:** mission alignment, atomicity (shippable today), real-work-not-prep.
- **Plan-only.** No compile run. If wiki is stale, surface a one-liner; don't fix it.

## Critique lens

Every proposed item passes through:

1. **Mission filter.** Does this ladder up to the mission in `CLAUDE.md` and the top of `me/priorities.md`? If no, flag it.
2. **Atomicity filter.** Is this shippable today, in one sitting if possible? If it's a week-level objective ("finalize the CRM"), drill: what's the next concrete step today?
3. **Real-work filter.** Kill items that start with "map", "draft", "outline", "write down", "think about", "plan out" - unless the artifact itself is the deliverable (e.g. "draft the email to the client" is fine because the email is the output). Mapping and drafting are prep theater, not work.

When an item fails a filter, push back. Don't transcribe - sharpen.

---

## Process - Phase A: Detect state

Today's date: `YYYY-MM-DD` (system date, not memory).

Check `daily/YYYY-MM-DD.md`:
- File missing → fresh path (Phase B).
- File present, no `^## Plan` heading → fresh path (Phase B).
- File present, has `^## Plan` heading → check-in path (Phase C).

---

## Process - Phase B: Fresh path (interview-first)

### Step 1: Read context (parallel, in background)

Read these to build the critique lens - do NOT pre-synthesize a Plan from them:

- `me/priorities.md`, `me/goals.md`, `me/work.md` - mission and current priorities
- `.claude/rules/communication-style.md` - voice rules
- Today's `daily/YYYY-MM-DD.md` if present, plus today's `daily/sessions/YYYY-MM-DD-sessions.md` (morning session captures)
- Most recent `## Plan` block across `daily/*.md` - for carryover, only if within last 3 days
- Most recent `## Reflection` block across `daily/*.md` - context for what you were thinking last
- `.state/last-compile.txt` - if older than 24h, hold a one-liner for the final report

### Step 2: Open the interview

Lead with the forcing question:

```
Morning. What's the one thing that, if it shipped today, makes today a win?
```

That's the entry point. Wait for your reply.

### Step 3: Drill on the One Thing

Apply the three filters live:

- **Mission?** If the answer drifts ("I want to refactor X just because"), ask how it ladders up. Don't lecture - one question.
- **Atomic?** If the answer is week-level ("finalize the CRM"), drill: "what's the concrete step today - the thing you can finish in one sitting?"
- **Real work?** If the answer is "map out the plan for Y", drill: "what's the doing-step that produces Y?"

Loop until the One Thing is a single, mission-aligned, shippable atom.

**Fuzzy escape hatch.** If after one hard drill the owner is still fuzzy ("ugh, I don't know, lots of things"), do not pretend a Plan will fix it. Say:

```
This isn't a Plan problem. Recommend running grill-me on what you're actually working on this week. Want me to bail and you run that?
```

If yes, exit without writing. If no (you pick one), continue.

### Step 4: Capture supporting items (up to 2)

Once the One Thing is locked, ask:

```
What else is actively in flight today?
```

You dump. Apply the same three filters to each item. Cap at 2 - if you name 5, push back: "which two are real today? The rest are backlog." If you name 0, fine - Plan can be just the One Thing.

### Step 5: Surface carryover (only if the agent has something to add)

Check the most recent `## Plan` block (within last 3 days). If it exists and has unchecked items you did not mention in the interview:

```
Heads up: from [date]'s Plan you didn't mention - [item]. Still real, or kill it?
```

One pass. If the answer is "still real", it joins the supporting items (subject to the cap of 2 total). If the answer is "kill", it does not. Do not argue.

If the most recent Plan is older than 3 days, skip carryover entirely.

### Step 6: Write the Plan

Plan block format:

```
## Plan

**One Thing:** [single line, single sitting, mission-aligned]

- [ ] [supporting action]
- [ ] [supporting action]

---
```

If the One Thing is the only item, omit the checkbox list.

**Preview gate.** If the agent added a carryover item that you didn't originally say, show the final Plan block and ask:

```
Writing this - anything to fix?
```

Otherwise (100% your words), write directly.

Placement:
- New file → create with `# YYYY-MM-DD` H1, blank line, Plan block.
- Existing file with captures → prepend the Plan block under the H1, before the first `---` or `## Session` heading.

### Step 7: Final report

```
Day opened.

Plan: daily/YYYY-MM-DD.md
  One Thing: [the One Thing]
  [N] supporting
[fyi: last compile was [date]]   ← only if stale
```

No further commentary.

---

## Process - Phase C: Check-in path (existing Plan)

### Step 1: Read inputs

Same parallel read as Phase B Step 1, plus extract the existing `## Plan` block verbatim.

### Step 2: Quick read-back

```
Plan from earlier today. Slept on it.

[the existing Plan block]

Still the priority, or has the day shifted?
```

### Step 3: Branch on reply

- **"Still the priority"** (or any approval) - quick check-in mode. Ask:
  ```
  Anything to mark done, drop, or add?
  ```
  Surgical edits only. Preserve checkbox state for items not mentioned. Apply the three filters to anything new.

- **"Day shifted" / "Scrap it" / "Regen"** - fall through to Phase B Step 2 (fresh interview), then write a new Plan block (overwriting the old one).

- **Mixed** ("X is still right but Y is dead, swap in Z") - surgical edits with filters.

### Step 4: Final report

```
Plan reconciled.
  One Thing: [current]
  [N] open · [M] done · [K] dropped
```

---

## Voice rules

Follow `.claude/rules/communication-style.md`:
- No emojis, no em dashes, no filler openers, no AI-tells.
- Casual, direct, brother-tone. Match your energy.
- Cut to the chase. Drill questions are short. Pushback is one sentence, not a paragraph.

## Mission anchor

Read the mission from `CLAUDE.md` and its current expression from the top of `me/priorities.md`. When in doubt, mission wins over convenience.

## What `/action` is not

- Not a backlog grooming tool. Open threads from past dailies belong in a backlog, not today's Plan.
- Not a daily standup form. The interview is conversational, not a checklist.
- Not a compile trigger. `/reflect` runs compile.
- Not a deeper-strategy session. If the interview reveals they don't know what they're working on, bail to `grill-me`. Don't fake a Plan.
