# The Brain

<!-- compile:locked start -->
**Mission:** {{MISSION}}

Hard invariants (never edited by compile):
- `sources/` is immutable truth. Never LLM-edit. Append-only.
- `journal/` is immutable raw capture. Never LLM-edit an existing entry.
- `daily/`, `log.md`, `network/log.md` are append-only system logs. LLM may append; never rewrite.
- Everything else (`me/`, `decisions/log.md`, `wiki/`, `projects/`, `areas/`) is LLM-editable.
- `CLAUDE.md` and `AGENTS.md` mirror each other byte-identical below this block.
<!-- compile:locked end -->
## Who

{{OWNER_PARAGRAPH}}

## Priorities

{{PRIORITIES_SUMMARY}}

- **Full ranked list and active threads:** `me/priorities.md` and `me/work.md`. Read recent daily notes and the relevant project README for newer execution context.

## How the Brain works

- **Live systems:** `connections.md`.
- **Structure:** `references/brain-schema.md`, `references/brain-operating-guide.md`, `references/para-map.md`, and `areas/favorite-problems.md`.
- **Memory:** durable truth lives in `me/`, `decisions/`, `wiki/`, `projects/`, and `areas/`; short-term agent memory lives in the memory directory reported by `python3 scripts/brain_config.py`.
- **Decisions:** append one dated decision, reasoning, and context entry to `decisions/log.md`; safeguards live in `.claude/rules/`.
- **Skills:** use the smallest relevant skill in `.claude/skills/`; build one when a workflow repeats.
- **Wiki:** query with `python3 scripts/wiki_search.py --pages -k 6 "<the real question>"`; read only the hits, check `updated:` against `me/priorities.md`, and pass `--stop` on the last query.
<!-- compile:efficiency start -->
## Token Efficiency
- Read on-demand; never load the full vault into context. CLAUDE.md is the index.
- Prefer one Write call over many sequential Edits when making widespread changes.
- Consult `references/`, primary docs, and accessible source threads before trial-and-error or asking the owner to relay recorded information.
- Keep responses dense; no preamble, no recap of what just happened.
- Batch updates into single writes; use index files to avoid bulk reads.
<!-- compile:efficiency end -->
<!-- compile:rules start -->
## Learned Rules

This section is written by `scripts/compile.py`, not by hand. It clusters the
feedback memories the agent has saved and points at the rule files that hold the
detail. It starts empty. It fills itself as you correct the agent.
<!-- compile:rules end -->
