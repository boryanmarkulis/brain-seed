# Getting your stuff in

A Brain with no sources has nothing to think with. This is the least glamorous
step and the one that decides whether the whole thing is useful.

## The order that matters

Do these in order. The order is not arbitrary.

1. **Your own writing.** Anything you have published, drafted, or journalled.
   This is the highest-value material in the system, because it is the only
   source written in your actual voice. It teaches the compiler how you think
   and gives every future piece of writing something real to draw on.
2. **Your notes.** Notion, Obsidian, Apple Notes, Google Docs, that one file
   called `ideas.txt`.
3. **Transcripts.** Calls, meetings, voice memos, YouTube videos you learned
   from. Transcripts are dense with exact language and objections, which is
   exactly what synthesis needs.
4. **Reference material.** Articles, docs, book notes, course material.
5. **Structured data.** CRM exports, analytics, financials. Usually better read
   live through `/connect` than dumped in as a file.

## One thing at a time

```bash
python3 scripts/pull.py https://example.com/some-article
```

`pull.py` detects the source type from the URL and routes it to the right
fetcher and the right folder under `sources/`. In a session, `/pull <url>` does
the same thing.

For anything without a URL:

```bash
python3 scripts/ingest.py --type notes --slug meeting-with-jane --file ./notes.txt
cat notes.txt | python3 scripts/ingest.py --type inbox --slug raw-dump
```

## Bulk backfills

**Always dry-run first.** A Notion workspace can be thousands of pages.

```bash
python3 scripts/pull.py <notion-db-url> --dry-run
python3 scripts/pull.py <notion-db-url> --limit 50
```

Then repeat with a higher limit once you have seen what lands. Staged runs beat
one enormous run: if something is misconfigured you find out after 50 files, not
after 5000.

**Do not run `compile.py` immediately after a big backfill.** Let the scheduled
catch-up absorb it, or run it with `--dry-run` first to see the scale of what it
wants to change.

## What each fetcher needs

| Source | Fetcher | Auth |
|---|---|---|
| Any web page | `fetchers/web.py` | none |
| YouTube | `fetchers/youtube.py` | none for public captions |
| Loom | `fetchers/loom.py` | optional cookie for private videos |
| Notion page or database | `fetchers/notion.py` | integration token, shared with the pages |
| Google Docs | `fetchers/gdoc.py` | OAuth token |
| Google Drive folder | `fetchers/gdrive.py` | OAuth token |
| Google Sheets | `fetchers/gsheet.py` | OAuth token |
| Substack | `fetchers/substack.py` | none for public posts |
| Fathom calls | `fetchers/fathom.py` | API key |

Setup for each is handled by the `/connect` skill. Run `/connect notion` and it
walks you through creating the token, tests it against live data, and writes the
`connections.md` row for you.

## Link following

For Google Docs and Notion parents, `/pull` extracts hyperlinks and
automatically ingests any Loom, YouTube, or Doc links it finds, each tagged with
`<!-- Linked from: <parent-slug> -->`. The parent gets a `## Linked sources`
section listing its children.

This is how one meeting-notes doc pulls in the three recordings it references.
Disable with `--no-follow`.

## Rules that are not negotiable

- **`sources/` is immutable.** Never edit an ingested file. Never let an agent
  "clean it up". Ingestion refuses on a slug collision rather than overwriting.
- **Keep the frontmatter.** Every ingested file records where it came from and
  when. `brain_audit.py` uses it to tell you which sources have never been
  folded into the wiki.
- **One type, one folder.** Provenance should be obvious from the path alone.

## Checking coverage

```bash
python3 scripts/brain_audit.py | python3 -m json.tool | head -40
```

Look at `sources_uncited`: sources that no wiki page cites. A high number means
material is sitting there unused, which usually means either the compiler has
not caught up, or your `domains` list in `brain.config.json` is too narrow and
the compiler is dropping a whole subject.

**That second one is the common mistake.** People list only their current
field. A past career is not off-topic. Widen `domains` and re-run.

## Writing your own fetcher

Copy `scripts/fetchers/web.py`. It is 40 lines. Then register the URL pattern in
`scripts/fetchers/__init__.py` so `/pull` dispatches to it automatically.
