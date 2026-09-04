---
name: journal
description: Capture a dated journal entry into the Brain from any device. Records the day's highlight plus anything else worth keeping, and flags voice notes or handwritten pages to reconcile later. Use for "/journal", "journal this", or any time the owner wants to log a thought against today.
argument-hint: "[YYYY-MM-DD] [the entry text]"
allowed-tools: Read Write Edit Bash Glob
---

# /journal - Capture a day

Journal entries are **private raw capture, not synthesis**. They live under
`journal/` and are immutable once written, the same as `sources/`. The wiki
compiler deliberately excludes them because they are the most personal writing
in the vault and should not be synthesized by default.

Idempotent within a day: firing it twice appends, and never clobbers the day's
existing headline.

## Step 1: Get the input

If the owner already passed text with the command, use it. Otherwise ask one
question and stop:

```
What's the highlight, and anything else worth keeping?
```

Parse the answer into:

- **Highlight** - the one-line headline of the day. Usually the first strong
  line, or whatever they flag as the highlight.
- **Body** - everything else worth keeping.
- **Pending originals** - if they mention a voice note or a handwritten page
  that lives somewhere else, note it as pending rather than inventing content.

## Step 2: Write it

Write to `journal/<YYYY>/<YYYY-MM-DD>.md`. Create the year folder if needed.

**Read the file first if it exists.** Append under a new timestamped heading.
Never overwrite an existing highlight.

```markdown
---
date: 2026-09-04
highlight: the one-line headline
pending: [voice]          # omit the key entirely when nothing is pending
---

# 2026-09-04

## 14:32

The body text, in their own words.

## Pending
- [ ] voice note to transcribe
```

## Rules that matter here

- **Keep their words.** Do not rewrite, tidy, or improve their journal voice.
  This is the one place in the Brain where the raw phrasing is the point.
- **Write names exactly as dictated.** Never auto-correct a name to the
  spelling you assume is right; transcription mangles names constantly and a
  silent "fix" makes the record wrong. If you spot a recurring quirk, record it
  in `me/team.md` instead.
- Follow `.claude/rules/communication-style.md` when you speak, not when you
  transcribe.

## Step 3: Commit

```bash
git add journal/ && git commit -m "journal: <date> entry"
```

The `SessionEnd` sync hook pushes. In a remote or phone session, that is the
whole flow: the text rides git and you reconcile any pending originals when you
are back at your main machine.

## Step 4: Confirm

One line: the entry path, the highlight, and anything still pending.

## Reconciling voice and handwriting

The Brain deliberately does not move your audio or scans around; the originals
stay in whatever app already holds them. When you are back at your main machine
and want them in:

- **Voice** - transcribe locally and append the text under a new dated
  `## Voice note (transcribed YYYY-MM-DDTHH:MM)` heading in that day's entry.
- **Handwriting** - Read the image or PDF directly (the Read tool renders both),
  then append a faithful transcription under a new dated
  `## Handwritten (transcribed YYYY-MM-DDTHH:MM)` heading in that day's entry.

Never tick an earlier pending checkbox or edit existing entry content. The new
dated section records that reconciliation happened while preserving the raw
capture as written.

If you wire up a transcription tool, add it to `connections.md` and build a
small script for it. See `/connect`.
