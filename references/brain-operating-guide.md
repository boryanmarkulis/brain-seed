# Brain Operating Guide

This is the agent-readable guide for using your Brain. Read this when working on Brain structure, knowledge organization, project context, compile behavior, area reviews, or any task where you need to decide where information belongs.

The Brain is a Tiago-aligned PARA overlay, not a strict PARA clone. Keep the existing protected vault shape. Add clarity around action horizons.

## Core Model

Use CODE:

- Capture: preserve raw truth and session history.
- Organize: put material near the action horizon it supports.
- Distill: compress only when useful signal emerges.
- Express: turn knowledge into shipped work, decisions, tools, writing, prompts, and client assets.

The Brain should answer four questions fast:

- What are we trying to do now?
- What ongoing responsibility does this affect?
- What reusable knowledge already exists?
- What should the next human or agent read first?

## Where Things Go

Use this routing table before creating or moving anything:

| Destination | Use for | Agent rule |
|---|---|---|
| `sources/` | Raw external truth, imports, transcripts, exports, source documents | Immutable. Never edit existing files. Add only through ingestion paths. |
| `daily/` | Chronological session captures and working traces | Append-only. Use as memory, not polished truth. |
| `projects/` | Active outcomes with a finish line | Read the project README first. Put deliverables and working packets beside the active project. |
| `areas/` | Ongoing responsibilities without a finish line | Use for standards, current state, review cadence, and open loops. |
| `wiki/` | Distilled concepts, lessons, people, and playbooks | Use for reusable synthesis. Link to sources where possible. |
| `references/` | Stable operating docs, SOPs, maps, examples, API notes | Use for durable instructions that agents should follow. |
| `outputs/` | Expressed artifacts, exports, reports, generated deliverables | Use for finished or packaged work products. |
| `archives/` | Inactive projects, retired resources, old versions | Preserve context without keeping it active. |
| `me/` | Human-owned identity, goals, priorities, work context | Propose changes. Do not silently rewrite. |
| `decisions/log.md` | Durable decisions | Append only, using the decision format. |
| `log.md` | Structural events and system activity | Append only. |

If unsure, prefer linking over moving.

## PARA In This Brain

Projects are active efforts with a concrete outcome. They should have a README that makes the current state obvious to an agent.

Areas are responsibilities to maintain. They should stay short, current, and operational.

Resources are reusable knowledge. In this Brain, resources live mostly in `wiki/` and `references/`.

Archives are inactive context. Archive to reduce active noise, not to delete memory.

`sources/` and `daily/` are protected capture layers. They are adjacent to PARA, but not normal PARA folders.

## Progressive Summarization

Do not summarize everything. Summarize when something is being reused, repeated, or turned into action.

Layer map:

- Layer 0: original source in `sources/`.
- Layer 1: raw capture in `daily/`, project notes, source markdown, or logs.
- Layer 2: resonant excerpts, exact language, objections, proof, mistakes, patterns.
- Layer 3: "use this" material ready for copy, prompts, decisions, workflows, or playbooks.
- Layer 4: synthesis in `wiki/`, area files, project README summaries, or operating docs.
- Layer 5: expression in `outputs/`, scripts, skills, prompts, docs, client assets, or published work.

Use `templates/progressive-note.md` for new high-value notes. Do not retrofit every old file.

## Favorite Problems

`areas/favorite-problems.md` is the filter for what the Brain should notice.

Use it when:

- deciding whether a source is worth ingesting
- routing captured material during compile
- choosing what a session learning means
- finding connections between old knowledge and current work
- planning new skills or agents

If new material does not advance a favorite problem, it can still be captured, but it should not automatically become central context.

## Intermediate Packets

Preserve useful work-in-progress chunks. A packet is any reusable piece of work that makes future work easier.

Examples:

- research brief
- prompt
- outline
- checklist
- test case
- sales script
- customer language bank
- project plan
- decision memo
- working prototype
- agent review notes

Keep packets in the active project if they serve a current outcome. Move or copy stable instructions into `references/`. Distill repeatable patterns into `wiki/playbooks/`.

## Agent Workflow

When starting work:

1. Read `AGENTS.md` for core invariants.
2. If deciding where knowledge belongs, read this guide and `references/para-map.md`.
3. If working on an active effort, read the project README first.
4. If maintaining an ongoing responsibility, read the relevant `areas/` file.
5. If writing or deciding, pull exact source language from `sources/` only when needed.
6. If creating a durable decision, append to `decisions/log.md`.
7. If changing structure, append to `log.md`.

Before ending work:

- Update the relevant project README if the current focus, next action, or open loops changed.
- Add or update area state only when the responsibility changed.
- Keep raw sources immutable.
- Prefer concise links over duplicated summaries.

## Anti-Patterns

- Do not move raw source files to make the structure look clean.
- Do not rewrite `me/` without explicit permission.
- Do not turn every interesting note into a wiki page.
- Do not let `AGENTS.md` become the whole Brain.
- Do not keep paused projects in active attention without an archive trigger or clear reason.
- Do not bury a next action in a long historical note when it belongs in the project README.
