# Learn From Corrections

This is the rule that makes the Brain get smarter instead of repeating itself.

When the owner corrects a mistake you made:

1. **Apply the correction immediately.**
2. **Save a feedback memory** to the memory directory (run
   `python3 scripts/brain_config.py` to see its path) as
   `feedback_<short_slug>.md`, capturing three things:
   - the rule, stated as an instruction
   - why it matters (the concrete thing that went wrong)
   - how to apply it next time
3. **Show the owner the new rule** before continuing. One line, plainly stated.

`scripts/compile.py` reads every `feedback_*.md` in that directory, clusters
them, and rewrites the `## Learned Rules` section of `CLAUDE.md` and `AGENTS.md`
between the `<!-- compile:rules -->` markers. That is the loop: a correction in
one session becomes standing context in every future session, with no human
maintaining a rules list.

**The test:** if the same situation comes up next session, you should handle it
correctly without being told again.

## Memory file shape

```markdown
---
name: feedback-short-slug
description: one line, used to decide relevance during recall
metadata:
  type: feedback
---

The rule, as an instruction.

**Why:** the specific failure this prevents.
**How to apply:** what to do differently, concretely.
```

Link related memories with `[[their-name]]`. A link to a memory that does not
exist yet is fine; it marks something worth writing later.
