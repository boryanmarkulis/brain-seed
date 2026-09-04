# PARA Map

The Brain uses PARA as an operating overlay. It keeps the existing vault structure but makes each folder's action horizon explicit.

## Local PARA Dialect

| PARA role | Brain location | Meaning |
|---|---|---|
| Projects | `projects/` | Active outcomes with a finish line. |
| Areas | `areas/` | Ongoing responsibilities to maintain. |
| Resources | `wiki/`, `references/` | Reusable knowledge, playbooks, SOPs, examples, maps, API notes. |
| Archives | `archives/` | Inactive context from projects, areas, and resources. |

## Protected Capture Layers

These folders support PARA but should not be treated as normal moveable PARA material:

| Folder | Role | Rule |
|---|---|---|
| `sources/` | Raw external truth | Immutable. Append-only. Never LLM-edit existing files. |
| `daily/` | Chronological session memory | Append-only. Use for recall and compile input. |
| `decisions/log.md` | Durable decisions | Append-only. One line per decision. |
| `log.md` | Structural/system events | Append-only. |
| `me/` | Human-owned identity context | Propose changes, do not silently rewrite. |

## Express Layer

`outputs/` is the Express layer: generated artifacts, exports, client deliverables, reports, packaged work, and other finished work products.

Keep active work-in-progress in `projects/`. Move or copy finished artifacts to `outputs/` when they become deliverables or reusable packages.

## Routing Rules

- Has a concrete outcome and deadline? Use `projects/`.
- Needs ongoing maintenance? Use `areas/`.
- Is reusable knowledge? Use `wiki/` or `references/`.
- Is raw truth? Use `sources/`.
- Is session history? Use `daily/`.
- Is finished output? Use `outputs/`.
- Is inactive? Use `archives/`.

When a file could fit multiple places, choose the folder that matches the next action. Link to the rest.
