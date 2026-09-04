---
name: update
description: Voice-dump processor. You dump what happened (text or transcribed voice), and the skill parses it into structured updates, applies PARA classification to new items, and updates the right context files, decision log, project READMEs, and connection files. Triage first, then execute after approval.
triggers:
  - /update
---

# /update - System Update from Voice Dump

you will paste a voice dump (transcribed or raw). You will:

1. **Read and parse** the dump to extract:
   - Business updates (deals closed, deals opened, progress on existing projects)
   - New contacts or notable interactions
   - Priority shifts
   - Decisions made
   - New projects, ventures, or ideas
   - Things to remember
   - Anything that might need reorganizing

2. **Apply PARA classification** to every new item and any existing items that might need reshuffling. Evaluate in this order: Project → Area → Resource → Archive (most to least actionable). When in doubt between two, default to the more actionable one.

   **Project** - active work with a defined goal and a finish line. Must have forward momentum *this week*. 5–10 items per folder, 10–15 active projects total.
   - Key test: "Is this truly actionable right now, with a clear next step and a finish line?"
   - Edge case: tax docs, legal agreements, financial statements with deadlines → Project (e.g. `projects/2025-tax-filing/`), not Area/Finances
   - Edge case: any file clearly part of an active named project belongs in that project folder even if the filename doesn't make it obvious
   - A "future project" is NOT a project - put it in Resources until it has real momentum

   **Area** - ongoing responsibility with a standard to maintain, no end date.
   - Key test: "Is this something I maintain indefinitely, not something I finish?"
   - Never use an Area as a catch-all for things that are actually active Projects
   - If something in an Area suddenly has a deadline, promote it to a Project

   **Resource** - reference material organized by interest or topic, no current action needed.
   - Key test: "Is this useful for future reference but requires no action right now?"
   - Ideas, future plans, research, templates, notes on topics of interest all live here
   - Resources can become Projects later when they activate

   **Archive** - inactive items from Projects, Areas, or Resources.
   - Key test: "Is this truly no longer active, complete, or needed right now?"
   - Do NOT auto-archive screenshots or images - ask if the purpose is unclear
   - Completed projects move here; so do ended relationships, outdated configs, ephemeral files

3. **Show a triage summary** - before touching anything:
   ```
   Here's what I caught and where it goes:

   SELF UPDATES:
   - me/priorities.md: [what changes]
   - me/work.md: [what changes]

   PROJECT UPDATES:
   - projects/[name]/README.md: [what changes]

   NEW FILES:
   - projects/[name]/README.md: [new project, brief]
   - network/connections/[slug].md: [new person]

   DECISION LOG:
   - [YYYY-MM-DD] DECISION: ... | REASONING: ... | CONTEXT: ...

   NETWORK UPDATES:
   - connections/[slug].md: [what changes]

   PARA MOVES:
   - [item] → [Projects/Areas/Resources/Archives] as [folder/file name] - [one-line reason]
   - [item that should be archived] → Archives - [reason]
   - (none if nothing needs reshuffling)

   QUESTIONS FOR YOU:
   - [anything ambiguous that needs clarification]
   ```

4. **Ask clarifying questions** if anything is ambiguous - especially PARA placement that could go either way. One or two questions max, only if genuinely needed.

5. **Wait for approval.** Don't touch files until the owner says go.

6. **Execute all updates** in parallel once approved:
   - Update self files (me/)
   - Update / create project READMEs
   - Append to decisions/log.md (append-only, never edit old entries)
   - Update / create connection files in network/connections/
   - Update network/index.json if new connections are added
   - Move or create files per PARA MOVES
   - Save any memories that should persist across conversations

7. **Confirm done.** Brief summary of what got updated.

## Rules

- Append-only on decisions/log.md. Never edit existing entries.
- When adding to decisions/log.md, format is: `[YYYY-MM-DD] DECISION: ... | REASONING: ... | CONTEXT: ...`
- New connections need a full frontmatter block (see network/connections/ for examples)
- Update network/index.json and last_touched / next_touch_due when touching connection files
- When in doubt about PARA placement, ask rather than guess
- If a priority shifts, update me/priorities.md and bump the last updated date
- Don't overwrite project status unless explicitly stated - use judgment about whether it's a real status change
- A future idea with no active work is a Resource, not a Project - don't promote it until it has momentum
