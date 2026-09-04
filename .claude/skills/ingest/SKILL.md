---
name: ingest
description: Pull an external source (Notion page, URL, local file, pasted text) into the Brain as an immutable raw file in sources/. Use when the owner says "ingest X", "pull this into the Brain", or "/ingest <url>".
argument-hint: "<url|path|notion-page-id> [--type journal|ecom|loom|gdocs|web|inbox]"
---

# /ingest - External Source to Brain

> **Prefer `/pull <url>` for anything with a URL.** It runs as a direct Python script (no MCP, no token burn) and dispatches to the right fetcher. Reach for `/ingest` when the source is pasted text, a local file, or you need the `--stdin` path.

Manual, one-shot ingest. Fetches a source and saves raw content to `sources/<type>/<slug>.md` (immutable). No wiki draft - `scripts/compile.py` owns the wiki layer and updates concept pages over time as sources accumulate.

Distinct from `notion-sync`: notion-sync pulls a Notion page for direct use (e.g. into `me/`). `ingest` is about adding a raw artifact to the Brain's long-term memory so compile can later synthesize from it.

## When to run

- the owner says "/ingest <url>" or "ingest this into the Brain"
- A Notion journal entry, Google Doc, article, or tweet contains durable signal worth preserving
- Bulk backfill of a single source during Phase 4

## What it does

1. Fetches the source (method depends on input type).
2. Writes raw content to `sources/<type>/<slug>.md` with a sync header (immutable).
3. Appends an `INGEST OK` line to `log.md`.
4. Reports the file path to you.

Wiki pages are produced separately by `scripts/compile.py` (Phase 5), which reads all sources + daily captures and maintains long-lived concept pages in `wiki/`.

## Execution steps

1. **Identify source type and fetch.**
   - **Notion URL / page ID** → use the Notion MCP (`notion-search` then `notion-fetch`). Convert to clean markdown. Default type: `journal` (ask if unclear).
   - **Generic URL** → use `WebFetch`. Default type: `web`.
   - **Google Doc URL** → use whichever Google integration is listed in `connections.md`. Default type: `gdocs`.
   - **Local path** → read directly. Type based on contents (ask if unclear).
   - **Pasted text** (via `sources/inbox/` drop) → read the inbox file. Type: `inbox` unless the owner says otherwise.

2. **Pick a slug.** Kebab-case, short. For journal entries, prefer `YYYY-MM-DD-<topic>`. For people, use the person's name. For concepts, the concept noun. Confirm with you if ambiguous.

3. **Call the ingest script.** Write the fetched content to a temp file (or pipe via stdin), then run:

   ```bash
   python3 scripts/ingest.py \\
     --type <journal|ecom|loom|gdocs|web|inbox> \\
     --slug <kebab-slug> \\
     --raw /tmp/ingest-<slug>.md \\
     --source-url "<original URL if any>"
   ```

   The script writes `sources/<type>/<slug>.md` with `<!-- Ingested YYYY-MM-DD -->` + `<!-- Source: <url> -->` header, logs `INGEST OK` to `log.md`.

4. **Report back.** Show the path to you. Don't pretend it's been synthesized - it's raw, waiting for compile.

## Flags & options

- `--force` → overwrite existing files. Default is to bail if the slug collides.
- `--stdin` → pipe content in instead of using `--raw <path>`.

## Target path conventions

- `sources/journal/<slug>.md` - Notion journal entries, daily action log items
- `sources/ecom/<slug>.md` - e-commerce lessons, product test logs
- `sources/loom/<slug>.md` - Loom transcripts (from Whisper, not LLM)
- `sources/gdocs/<slug>.md` - Google Docs exports
- `sources/web/<slug>.md` - articles, tweets, blog posts
- `sources/inbox/<slug>.md` - anything pasted for later processing

## Guardrails

- **`sources/` is immutable.** If the slug exists, bail. Never overwrite silently.
- **Never ingest sensitive material** (credentials, legal drafts) without flagging first.
- **Watch the content length.** Script caps at 100k chars; longer sources should be chunked before ingest.
- **Notion MCP first, WebFetch second.** If a URL is a Notion URL, always go through the Notion MCP - cleaner markdown.

## Related

- `.claude/skills/notion-sync/SKILL.md` - pull a Notion page directly into `me/` or anywhere (no `sources/`)
- `scripts/ingest.py` - the script this skill drives
- `scripts/compile.py` - owns the wiki layer; reads sources/ + daily/, maintains concept pages
- `scripts/flush.py` - session counterpart (auto-captures from sessions into `daily/`)
- `log.md` - check here for INGEST OK/ERROR lines
