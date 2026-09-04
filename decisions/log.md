# Decisions

Append-only. One entry per meaningful decision. Never edit a past entry; if a
decision is reversed, append the reversal as a new entry and link back.

Format:

```
## YYYY-MM-DD -- short title

**Decision:** what was decided.
**Reasoning:** why, in one or two sentences.
**Context:** what was true at the time that made this the right call.
**Reverses:** (optional) the dated entry this overturns.
```
