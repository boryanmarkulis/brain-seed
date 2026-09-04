---
name: pull
description: Universal ingestion. Pull any external source (Notion page or DB, Google Doc, Drive folder, Loom, YouTube, Fathom call, Substack, URL) into sources/ via direct Python fetchers - near-zero token burn. Auto-follows Loom/YouTube/gdoc links inside parent documents. Use when the owner says "/pull <url>" or wants to bulk-ingest anything.
argument-hint: "<url> [--type <type>] [--slug <slug>] [--no-follow] [--limit N] [--dry-run]"
---

# /pull - Universal Ingestion

One command to pull anything external into `sources/`. Runs as a Python script (`scripts/pull.py`), not through MCP - so bulk ingests don't route content through the LLM context.

## When to run

- The owner says `/pull <url>` or "pull this into the Brain".
- Bulk backfills (Notion database, Drive folder, Substack archive).
- Single items (one gdoc, one Loom, one article).
- Any URL where you'd otherwise reach for `/ingest` or `/backfill-notion`.

## What it handles

Auto-detected from the URL:

| URL pattern | Fetcher | Lands in |
|---|---|---|
| `notion.so` / `notion.site` database | `fetchers/notion.py` | `sources/notion/<db-title-slug>/` (e.g. `sources/notion/action-log/`) |
| `notion.so` / `notion.site` single page | `fetchers/notion.py` | `sources/notion/pages/` |
| `docs.google.com/document/...` | `fetchers/gdoc.py` | `sources/gdocs/` |
| `drive.google.com/drive/folders/...` | `fetchers/gdrive.py` | `sources/gdocs/` (one file per doc) |
| `loom.com/share/...` | `fetchers/loom.py` | `sources/loom/` |
| `youtube.com/watch?v=...` / `youtu.be/...` | `fetchers/youtube.py` | `sources/youtube/` |
| `fathom.video/...` (call recording) | `fetchers/fathom.py` | `sources/fathom/` |
| `*.substack.com` (root or `/p/slug`) | `fetchers/substack.py` | `sources/substack/` |
| any other URL | `fetchers/web.py` (trafilatura) | `sources/web/` |

Override the target subdir with `--type notion/<custom-name>` if needed.

## How to run

Invoke `scripts/pull.py`:

```bash
python3 scripts/pull.py <url> [flags]
```

Flags:
- `--type <type>` - override the auto-detected type. Any folder name under `sources/` works; see `VALID_TYPES` in `scripts/ingest.py`.
- `--slug <slug>` - override the auto-derived slug.
- `--no-follow` - disable link following (default: on for gdoc/notion).
- `--limit N` - cap batch size (Notion DBs, Drive folders, Substack archives).
- `--dry-run` - print what would be ingested, write nothing.

Always dry-run first for anything batch-shaped (DB, folder, publication archive). Confirm the count with the owner, then run for real.

## Link following

For gdoc and Notion parents, `/pull` extracts hyperlinks and auto-ingests any Loom, YouTube, or other gdoc links - each with a `<!-- Linked from: <parent-slug> -->` header. The parent doc gets a trailing `## Linked sources` section listing the children. Disable with `--no-follow`.

Other source types (web, substack) do not auto-follow.

## Output

Emits one JSON summary to stdout:

```json
{
  "ingested": 5,
  "skipped": 1,
  "errors": 0,
  "paths": ["sources/gdocs/my-doc.md", "sources/loom/intro-call.md", ...],
  "error_details": []
}
```

Underlying `scripts/ingest.py` logs one `INGEST OK` line per file to `log.md`.

## Auth

- **Google** - OAuth token at `~/.config/brain/google_token.json`. See `docs/04-connections.md` for the one-time setup.
- **Notion** - needs an internal integration token. Create at notion.so/my-integrations, share the target pages/DBs with it, save the token to `~/.config/brain/notion_token` or set `NOTION_TOKEN` env var.
- **Loom / YouTube / web** - no auth needed for public content.
- **Fathom** - needs `FATHOM_API_KEY` in the Brain root `.env`. Create one at fathom.video (Settings > API).
- **Substack** - public posts work without auth. Email analytics (`subs_at_send`, `opens`, `open_rate`) get merged into each post when `~/.substackrc` is present (`SUBSTACK_SID` / `SUBSTACK_PUBLICATION`). Point it at your own publication.

## Guardrails

- `sources/` is immutable - `ingest.py` bails on slug collision. `/pull` catches that and reports it as "skipped", not an error.
- Always `--dry-run` before a bulk run to confirm the count.
- For very large Notion DBs, use `--limit` for staged runs.
- Don't run `compile.py` inline after a large backfill. Let the scheduled catch-up job absorb it.

## Deprecates

- `/backfill-notion` - use `/pull <notion-db-url>` instead.
- `/ingest` for URL input - use `/pull`. Keep `/ingest` for raw-text / local-file / `--stdin` cases.

Keep separate:
- `/notion-sync` - different purpose (pulls into `me/`, not `sources/`).

## Related

- `scripts/pull.py` - the dispatcher
- `scripts/fetchers/` - one module per source type
- `scripts/ingest.py` - storage layer; `/pull` shells out to this per result
- `log.md` - `INGEST OK` / `INGEST ERROR` lines
