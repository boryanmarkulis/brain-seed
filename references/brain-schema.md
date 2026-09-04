# Brain Schema

Reference doc for the Brain's folder layout and maintenance rhythm. Not loaded into agent context by default - read on demand.

## Layout

```
Brain/
├── CLAUDE.md          the operating prompt (mission, rules, imports)
├── connections.md     map of live systems the Brain can reach
├── index.md           catalog of everything, by category
├── log.md             append-only event log (ingests, compiles, migrations)
├── me/                who the owner is (priorities, goals, team, work, self)
├── decisions/log.md   append-only decision log
├── network/           Connection Station (contacts, inbox, log)
├── projects/          active workstreams (each has a README.md)
├── areas/             ongoing responsibilities, standards, review state
├── sources/           raw, immutable inputs - never LLM-edited
├── daily/             session captures (YYYY-MM-DD.md), auto-filled by hooks
├── wiki/              LLM-maintained concept pages
├── outputs/           expressed artifacts, exports, reports, deliverables
├── archives/          retired work
├── scripts/           flush / compile / ingest / lint
├── templates/         reusable doc structures
├── references/        SOPs, style guides, examples, this file
├── agents/            future specialized agents
└── .claude/           skills, settings, hooks - the agent layer
```

## Templates

Reusable doc structures in `templates/`. Use:
- `templates/session-summary.md` at the end of a working session.
- `templates/project-readme.md` when creating or normalizing a project.
- `templates/area.md` when creating an ongoing responsibility area.
- `templates/progressive-note.md` when distilling a high-value note through progressive summarization.

## References

SOPs in `references/sops/`. Style guides and examples in `references/examples/`.

Important operating docs:
- `references/brain-operating-guide.md` - how agents should use the Brain.
- `references/para-map.md` - the Brain's local PARA overlay.

Agents working on Brain structure, knowledge organization, project context, compile behavior, or where information belongs should read `references/brain-operating-guide.md` first.

## PARA overlay

The Brain uses PARA as an overlay, not a destructive migration:
- `projects/` = active outcomes with a finish line.
- `areas/` = ongoing responsibilities without a finish line.
- `wiki/` and `references/` = reusable resources.
- `archives/` = inactive context.
- `sources/` and `daily/` = protected capture layers, not normal moveable PARA material.
- `outputs/` = Express layer for finished artifacts and deliverables.

## Archives

Don't delete old stuff - move it to `archives/`. Nothing gets lost, just out of the way.

## Keeping the Brain Sharp

- **When focus shifts:** update `me/priorities.md`.
- **Each quarter:** update `me/goals.md`.
- **When a decision matters:** log it in `decisions/log.md`.
- **When a system gets wired in:** update `connections.md`.
- **When an ongoing responsibility changes:** update the relevant `areas/` file.
- **When a project focus changes:** update that project's `README.md`.
- **When a workflow repeats:** build a skill in `.claude/skills/`.
- **New reference material:** drop it in `references/`.
- **New source to ingest:** run `/pull <url>` (or `/ingest` for raw text, local files, or stdin).
- **New concept worth a page:** add to `wiki/` and register in `index.md`.
- **New finished artifact:** place or reference it in `outputs/`.
- **Anything structural:** append to `log.md`.
