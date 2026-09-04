---
name: skill-builder
description: Turn a repeated workflow into a proper skill. Use when the same sequence of steps has happened two or three times, when learnings/SKILL-CANDIDATES.md proposes one, or when the owner says "make this a skill" or "/skill-builder".
argument-hint: "<what the skill should do>"
---

# /skill-builder - Make the repeated thing repeatable

## When a skill is warranted

Build one when **all three** are true:

1. The workflow has happened at least twice, for real, not hypothetically.
2. It has steps that are easy to get wrong or easy to skip.
3. Doing it right requires context that is not obvious from the repo.

If it is a one-off, do not build a skill. If it is a single command, put the
command in a `references/` doc. A skill that is really a bookmark is noise, and
noise in the skill list costs a little context on every single session.

`scripts/evolve.py` writes candidates into `learnings/SKILL-CANDIDATES.md` when
it detects a repeated tool pattern across sessions. That file is a good place to
look for what actually repeats, as opposed to what feels like it repeats.

## Anatomy

```
.claude/skills/<name>/
  SKILL.md          the instructions (required)
  references/       long detail loaded only when needed (optional)
  scripts/          helpers the skill shells out to (optional)
```

Frontmatter:

```yaml
---
name: kebab-case-name
description: What it does AND when to use it. The trigger sentence matters more than the description; it is how the agent decides to fire.
argument-hint: "<arg> [--flag]"
---
```

## Writing the body

- **Write the steps, not the theory.** The agent already knows how to think. It
  does not know that step 4 has to happen before step 3 on this particular tool.
- **Put the failure modes in.** Every "we got this wrong once" belongs in the
  skill as a warning with the concrete consequence. That is most of the value.
- **State the output shape** if the skill produces a report or artifact. Show a
  literal template.
- **Name the exact files and commands.** `python3 scripts/foo.py --bar`, not
  "run the foo script".
- **Keep it under about 200 lines.** Push detail into `references/` and load it
  only when needed.

## Testing before you ship

Run the skill once, end to end, on a real case. Not a hypothetical one. Then ask:

- Did the agent skip a step? The step was written ambiguously.
- Did it ask a question the skill should have answered? Add the answer.
- Did it produce a different output shape than intended? Add the template.

Fix and rerun. Two passes is normal.

## Register it

1. Append to `log.md`: `[YYYY-MM-DD] SKILL: created /<name> for <workflow>`
2. If it exposes a new system, add the row to `connections.md`.
3. Mention it in `index.md` if it is a ritual the owner will run regularly.

## Skills that evolve themselves

A mature skill can carry its own changelog. Add an `evolution.md` next to
`SKILL.md`, and end the skill body with a step telling the agent to append what
it learned this run. Over time the skill improves from use rather than from
someone remembering to maintain it. Use this sparingly: it works for rituals
run daily, and it is overhead for anything run monthly.
