---
name: level-up
description: Weekly automation-finding ritual using the Three Ms framework. One run = one shipped artifact. Walks you through Mindset → Method → Machine to scope and build one new automation.
triggers:
  - /level-up
  - "let's level up"
  - "what should I automate next"
  - "find me leverage this week"
  - "Friday automation ritual"
attribution: Adapted from The Three Ms of AI (tm), (c) 2026 Nate Herk
---

# /level-up - Weekly Automation Ritual

One interview. One shipped artifact. No exceptions.

After 4–6 runs, you should start spotting automation opportunities mid-week without prompting. That's the actual goal.

---

## Phase 1: Mindset - Find the Candidate

Ask these five questions. Listen for friction, repetition, and leverage.

1. What did you do 3+ times this week (even small things)?
2. Anything manual, boring, or copy-paste?
3. Anything a smart intern could handle with a checklist?
4. What would break first if 500 new leads landed tomorrow?
5. What's one thing that, if it ran automatically, would actively GET you those 500 leads?

**Output:** 1–3 ranked automation candidates. Present them with a one-line description each. Ask you to pick one.

---

## Phase 2: Method - Scope It

Five steps for the chosen candidate.

### Step 1: Find the Constraint
Which bottleneck does this solve? Revenue, capacity, quality, or speed?

### Step 2: EAD - Eliminate, Automate, Delegate (in that order)

**Eliminate first.** Ask: "What happens if we just stop doing this?" If nothing breaks, log it in `decisions/log.md` as a deliberate stop, declare it a win, and exit the skill. The best automation is no automation.

**Automate second.** Use this framing:
- 60%: Boring-is-beautiful (template, script, no AI)
- 30%: AI-assisted (one LLM call in the loop)
- 10%: Agentic (multi-step, last resort)

**Delegate third.** If it needs a human, who? Document the handoff, don't skip this step.

### Step 3: Map the Process

Five elements to identify:
- **Trigger** - what starts this?
- **Data sources** - what inputs does it need?
- **Transformations** - what happens to the data?
- **Decision points** - where does it branch?
- **Destination** - where does output go?

### Step 4: Pick Autonomy Level

| Level | Description | Default? |
|---|---|---|
| L0 | Manual - the owner does it with a reference doc | |
| L1 | Assisted - Claude helps, you approve every step | |
| L2 | Supervised - runs autonomously, you review output | Default |
| L3 | Monitored - runs and acts, alerts on anomalies | |
| L4 | Autonomous - fully self-directed | Requires explicit override |

Push back hard on anything above L2 unless the owner has seen this automation run correctly 5+ times.

### Step 5: Tie to a KPI - Mandatory

Must name one of three buckets + a specific metric:
- More customers (e.g., leads per week, proposals sent)
- More value per customer (e.g., LTV, upsell rate, time-to-proposal)
- Less cost (e.g., hours saved per week, error rate)

**If you can't name a specific metric, stop here.** Don't build something that can't be measured.

---

## Phase 3: Machine - Build It

Pick the lowest-complexity option that works. Boring is beautiful.

**Decision order:**

1. **Prompt-only template** - a reusable prompt you paste in
2. **Deterministic skill** - a Claude Code skill with no AI step (just logic + tool calls)
3. **AI-assisted skill** - a skill with one LLM call in the loop
4. **Sub-agent** - multi-step autonomous agent (last resort, requires KPI + L2+ sign-off)

**Every artifact shipped must include** `bike-method-phase: 1` in its frontmatter. This forces manual validation before the automation runs live. It cannot be skipped.

**Where artifacts live:**
- Skills → `.claude/skills/{name}/SKILL.md`
- Scripts → `scripts/{name}.py`
- Agents → `agents/{name}/`
- Decision logged → `decisions/log.md`

---

## Critical Rules

1. **One run = one artifact.** Don't scope two things. Pick one, ship one.
2. **EAD is mandatory.** Eliminate before automating. Always ask "what if we just stop?"
3. **L4 requires explicit override.** If the owner says L4, ask "why not L3?" and document the answer.
4. **KPI is mandatory.** No metric, no build.
5. **bike-method-phase: 1 on every artifact.** No exceptions. This is the safety net.
6. **Trademark attribution on every output.** Include "Three Ms of AI (tm), (c) 2026 Nate Herk" in the decision log entry.
