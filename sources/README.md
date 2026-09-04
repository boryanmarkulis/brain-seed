# Sources

Raw external truth. **Immutable.** Never LLM-edited, never rewritten, never
tidied. Append only.

This is the layer that makes the rest of the Brain trustworthy. Everything in
`wiki/` claims to be derived from something in here, and every wiki page cites
the source paths it came from. If you let an agent "clean up" a source file,
that chain breaks silently and you will never know which pages went wrong.

## Layout

One subfolder per source type, so provenance is obvious from the path alone:

```
sources/
  inbox/      dropped in, not yet filed
  journal/    your own writing
  web/        saved articles and pages
  youtube/    video transcripts
  notion/     exported Notion pages
  gdocs/      exported Google Docs
  call/       meeting and call transcripts
  book/       book notes and highlights
  course/     course material
```

Add your own folders. The only rule is that a type maps to exactly one folder.

## Getting things in

```bash
python3 scripts/pull.py <url>            # fetch a URL, file it automatically
python3 scripts/ingest.py --type web --slug my-article --url <url>
cat notes.txt | python3 scripts/ingest.py --type inbox --slug some-notes
```

Or in an agent session: `/pull <url>` and `/ingest`.

## Frontmatter

Every ingested file gets a header recording where it came from and when. Do not
strip it. `scripts/brain_audit.py` uses it to tell you which sources have never
been folded into the wiki.
