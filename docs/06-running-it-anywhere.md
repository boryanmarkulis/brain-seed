# Running it anywhere

Everything here is markdown and standard-library Python. There is no lock-in,
and switching tools costs you nothing.

## Claude Code

The fullest experience, because the hooks in `.claude/settings.json` run the
loop for you: sync on start, health check, compile heartbeat, error capture,
skill evolution, sync on end.

```bash
cd my-brain && claude
```

Skills are auto-discovered from `.claude/skills/`.

## Codex

Reads `AGENTS.md`, which is byte-identical to `CLAUDE.md`. Skills are plain
markdown, so point at the one you want:

```
read .claude/skills/reflect/SKILL.md and run it
```

No hooks, so run the loop yourself or from cron:

```bash
python3 scripts/sync.py pull      # at the start
python3 scripts/compile.py        # when due
python3 scripts/sync.py push      # at the end
```

`flush.py` reads Codex JSONL transcripts natively, so session capture works
either way.

## Cursor and other IDE agents

Point the agent at `AGENTS.md`. Many editors also read a rules file: symlink or
copy `AGENTS.md` into whatever path yours expects. Run scripts from the
integrated terminal.

## Claude Desktop, claude.ai, ChatGPT

No filesystem access, so use it for thinking rather than for the loop. Two
options:

- Keep the repo in a synced folder and use a filesystem MCP or connector.
- Paste the relevant files in. `me/priorities.md` plus a couple of
  `wiki_search.py` hits is usually enough context for a good conversation.

Anything worth keeping from those chats goes back in via
`python3 scripts/flush.py --inbox transcript.txt`, which takes any pasted
transcript and files it into today's daily note.

## Obsidian

The vault is standard markdown with `[[wikilinks]]`. Open the folder. Graph view
works out of the box, and it is genuinely the nicest way to see the wiki's shape
and find orphan clusters.

Set Obsidian's "new note" folder to `sources/inbox/` so quick captures land in
the right place.

## Your phone

Two workable routes:

- **Git.** Working Copy on iOS, or any git client on Android. Edit markdown
  directly. `sync.py` reconciles when you get back to a machine, and the union
  merge drivers on append-only files mean edits from two places combine rather
  than conflict.
- **A remote agent session.** Claude Code's remote control keeps a session on
  your Mac reachable from the phone app. Then `/journal` and `/update` work from
  anywhere.

## Cron and schedulers

Nothing depends on a specific scheduler. `maybe_compile.py` and `maybe_wiki.py`
are **catch-up gates**, not clocks: fire them often and they decide whether work
is due.

```cron
0 * * * * cd ~/my-brain && python3 scripts/maybe_wiki.py
*/30 * * * * cd ~/my-brain && python3 scripts/maybe_compile.py
```

On macOS use launchd with `RunAtLoad` plus `StartInterval` rather than fixed
times, so a run missed while the laptop was shut is picked up on wake instead of
skipped until tomorrow.

**Two macOS gotchas that cost real time:**

- launchd jobs die with exit 78 on iCloud-backed paths. Keep logs and
  `WorkingDirectory` outside iCloud.
- launchd runs jobs with `TZ` unset, so a naive `datetime.now()` there is UTC
  while the same line in your shell is local. Always stamp timezone-aware.

## No agent at all

It is still a well-organised folder of markdown with a search script. That is
the floor, and it is not a bad floor.
