---
name: review
description: Opus review pass on the work just completed in this session. Scopes to files touched during this conversation, not the full uncommitted diff. Run /review at the end of a work session before committing.
triggers:
  - /review
  - "opus review"
  - "review my work"
  - "review what we just did"
---

# /review - Opus Review Pass

Sonnet executes. Opus thinks. This skill is the handoff between them.

Run it after completing a piece of work to catch mistakes, drift, and shallow design before committing. Scope is **this session only** - not everything that happens to be uncommitted.

---

## Step 1 - Identify Session Scope

Look at the conversation so far and list the files that were created or modified **in this session**. Be specific - file paths only, no guessing.

If you specified what to review (e.g. `/review the skill` or `/review the whatsapp templates`), use that to narrow scope further.

If you genuinely can't tell which files were touched (e.g. called with no prior work in the session), ask: "What did we just work on?"

Once you have the file list, run:

```bash
git diff -- <file1> <file2> ...
git diff --staged -- <file1> <file2> ...
git status --short -- <file1> <file2> ...
```

For any session files that are untracked (new, not yet staged), `Read` them directly.

If the scoped diff is empty or trivially small (under 10 lines, one file), tell you there's nothing worth a review pass and stop. Don't burn Opus on a typo fix.

---

## Step 2 - Enter Plan Mode

Call `EnterPlanMode`. This is what routes thinking through Opus. Everything from here runs in plan mode.

---

## Step 3 - Gather Context

Read in parallel:

- `CLAUDE.md`
- Any `me/` or `references/` files that are relevant to what was changed
- Any files touched by the diff that need more context to evaluate

---

## Step 4 - Review the Diff

Walk the diff against this checklist. Tag each finding: `[BLOCKER]`, `[FIX]`, `[NIT]`, or `[OK]`.

### Correctness
- Does the code do what was asked? Edge cases handled?
- Any logic errors, off-by-ones, wrong conditions?

### Intent drift
- Did Sonnet add unrequested features, abstractions, or scope? (Rule: don't add anything beyond what was asked.)
- Apply the **deletion test**: if you deleted this new thing, would it concentrate complexity - or just move it? If it just moves it, it shouldn't exist.

### Module depth
- Are new interfaces **deep** - simple contract on the outside, complexity hidden inside?
- Or **shallow** - leaky, thin wrappers that force the caller to know too much?
- Does a change here require understanding or changing many other places? (**locality** failure.)

### Brain conventions
- `sources/` - not edited (immutable truth)
- `daily/`, `decisions/log.md`, `log.md`, `network/log.md` - no past entries modified (append-only)
- `me/` - not edited without explicit approval
- No em dashes or double hyphens in any copy or templates
- No emojis
- No corporate jargon, AI-sounding language, or filler openers in any text written for you

### Code hygiene
- Comments that explain WHAT instead of WHY - delete them
- Dead branches, unreachable code, unused imports
- Unnecessary error handling or validation for things that can't fail
- Premature abstractions - three similar lines beats a bad helper

### Security
- No secrets hardcoded
- No command injection, SQL injection, XSS vectors
- User input validated at system boundaries only

### Consistency
- Does it match patterns in nearby files?

---

## Step 5 - Write the Fix-Plan

Write to the plan file that plan mode provides. Structure:

**Reviewed:** (1-2 lines - what changed and where)

**Findings:**
- `[BLOCKER]` ... (must fix before commit)
- `[FIX]` ... (should fix)
- `[NIT]` ... (optional; list but don't include in fix steps unless asked)
- `[OK]` ... (things explicitly checked and clean)

**Fix plan:** (concrete, file-and-line steps for Sonnet - only BLOCKERs and FIXes)

**Verification:** (how to confirm the fixes worked)

If nothing is wrong, write one line: `Clean. Nothing to fix.` and exit.

---

## Step 6 - Exit Plan Mode

Call `ExitPlanMode`. you approves the fix-plan. Sonnet implements it.
