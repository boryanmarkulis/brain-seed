---
name: grill-me
description: Use when the user wants to stress-test a plan, get grilled on a design, run a brainstorm or discovery session, extract what's in their head into a doc, or says "grill me".
---

# Grill Me

Relentlessly interview the user about every aspect of the topic until you reach shared understanding. Walk down each branch of the decision tree, resolving dependencies one by one. The goal is to extract what's in their head into a durable, organized markdown file so nothing is lost as context fills up.

## The Capture File Is The Point

Long interviews fill up context. If you hold answers only in your head, you will eventually misremember, conflate, or drop something. Checkpoint to disk after every single answer. The file, not your context, is the source of truth. Never make the user ask you to save progress.

## Setup

Before the first question:

1. Create the capture file at `brainstorms/{YYYY-MM-DD}-{topic-slug}.md`. Create `brainstorms/` if needed. Raw captures always live there; polished artifacts can move into `projects/` later.
2. Create the file immediately with a header: title, date, goal, empty summary, Q&A log, and open flags.
3. Tell the user where you're saving, then ask Q1.

## Checkpoint Rule

After every user answer, before asking the next question:

- Append a structured entry to the capture file: question topic, key facts and decisions from the answer, exact wording where it matters, and any flags.
- Update or correct earlier entries if a later answer changes them.
- Only then ask the next question.

Never batch multiple answers into one write.

## Interview Method

- Ask one question at a time.
- For each question, provide your recommended answer so the user can confirm, correct, or redirect.
- Resolve upstream decisions before dependent decisions.
- If a question can be answered by exploring the Brain, codebase, docs, or live systems, do that instead of asking.
- When the user cannot answer something, capture it as a flag with the right owner and move on.
- Keep going until the user says done, or every branch is covered.

## Capture File Structure

```markdown
# {Topic}: Brainstorm / Discovery Notes
Date: {date}
Goal: {one line}

## Summary / Key Decisions

## Q&A Log

### Q1 - {topic}
- Asked: {question}
- Captured: {facts, decisions, wording where it matters}
- Flags: {open item -> owner}

## Open Flags
- {item} -> {owner}
```

## At The End

Read the capture file for contradictions or gaps and reconcile them. Give the user a short recap: what is captured, what is still flagged, and the suggested next step.

**Hand off to the council:** if the session was about a new idea (business, product, offer) rather than a plan, design, or extraction, don't stop at the recap. Distill the capture file into a one-paragraph brief and proceed straight into the `roast` skill's council step so the idea gets a GO / RESHAPE / KILL verdict. Skip the handoff only if the user says they just wanted the discovery.
