---
name: audit
description: Weekly health check on your second brain. Scores the Four Cs (Context, Connections, Capabilities, Cadence) out of 100 and surfaces the top-3 leverage-weighted gaps with concrete next steps.
triggers:
  - /audit
  - "is my brain working"
  - "audit my setup"
  - "find gaps"
  - "score my brain"
---

# /audit - Brain Health Check

Read-only diagnostic. Never edit files. The only writable side-effect is the optional audit report.

## What to Read

Scan these before scoring. Never write to them.

- `CLAUDE.md` - operating manual
- `me/` - identity, priorities, context files
- `references/` - reference docs
- `decisions/log.md` - decision history
- `~/.claude/projects/.../memory/MEMORY.md` - working memory index
- `.claude/skills/` - installed skills
- `agents/` - defined agents
- `connections.md` - live-system registry
- `.mcp.json` - active MCP connections
- `daily/` - recent entries incl. `daily/sessions/` capture files (last 7 days)
- `log.md` - activity signal
- `scripts/` - automation scripts

---

## Scoring - 100 Points Total, Four Cs (25 each)

### C1: Context (25 pts)

How well does the Brain describe you and your mission?

| Check | Points |
|---|---|
| CLAUDE.md exists and is substantive (not just skeleton) | 5 |
| Identity captured: name, role, mission, location | 5 |
| `me/` has 2+ files with real content | 5 |
| Working memory has 3+ entries | 5 |
| `references/` has at least one reference doc | 5 |

### C2: Connections (25 pts)

How well-wired is the Brain to live systems?

**Tier-1 domains** (1.4 pts each, cap 10 pts - check `connections.md`, `.mcp.json`, and `scripts/`):
- Revenue / CRM
- Customer comms (Gmail, WhatsApp)
- Calendar (Google Calendar)
- Files / Knowledge (Google Drive, Notion)
- Project tracking (Notion, tasks)
- Spreadsheets / data (Google Sheets)
- Meeting intelligence

**Remaining 15 pts:**
| Check | Points |
|---|---|
| `references/` contains a connection/API reference doc | 5 |
| At least one connection has both read AND write capability | 5 |
| Active scripts in `scripts/` that hit live systems | 5 |

### C3: Capabilities (25 pts)

What can the Brain do autonomously?

| Check | Points |
|---|---|
| 3+ skills installed in `.claude/skills/` | 10 |
| At least 1 custom Brain-specific skill (not a template) | 10 |
| At least 1 agent defined in `agents/` | 5 |

### C4: Cadence (25 pts)

Is the Brain actually being used?

| Check | Points |
|---|---|
| At least 1 recurring trigger defined (cron, schedule, hook) | 10 |
| `daily/` has an entry in the last 7 days | 10 |
| `decisions/log.md` has an entry in the last 30 days | 5 |

---

## Gap Ranking - Leverage Multipliers

After scoring, rank gaps by: **points_lost × leverage_multiplier**

| Gap | Multiplier |
|---|---|
| 0 Tier-1 domains reachable | 4x |
| No identity / thin CLAUDE.md | 3x |
| 0 custom skills | 2x |
| No recurring trigger | 2x |
| No agents defined | 1.5x |
| No decisions logged | 1x |

Surface the **top 3** by weighted impact with a concrete next-step command for each.

---

## Output Format

```
## Brain Audit - {date}

**Score: {X}/100 - Stage {N}: {Stage Name}**

Stage thresholds:
- 0–39: Stage 0 Foundation
- 40–69: Stage 1 Built
- 70–89: Stage 2 Compounding
- 90–100: Stage 3 Autonomous

### Four Cs Breakdown
- Context:     {X}/25
- Connections: {X}/25
- Capabilities:{X}/25
- Cadence:     {X}/25

### Strengths
[2-3 bullets on what's working]

### Top 3 Gaps (by leverage)
1. **{Gap}** - {points lost} pts × {multiplier}x = {weighted score}
   Next step: `{concrete command or action}`
2. ...
3. ...
```

---

## Save Report (optional)

If you asks to save it, write to `audits/audit-{YYYY-MM-DD}.md`. Create the `audits/` folder if it doesn't exist. Never save unless asked.
