# Connections

Registry of every live system this Brain can reach. This is the map;
implementation details live in `.mcp.json`, `scripts/`, `.claude/skills/`, and
`references/`.

Update this file the same day a new system becomes reachable, an auth route
changes, or a connection is intentionally retired.

**Never store secrets here.** Name the env var, token file, or auth mechanism
only. The values live in `.env`, which is gitignored.

| Domain | Tool / System | Mechanism | Auth Location | Read / Write | Last checked | Reference |
|---|---|---|---|---|---|---|
| _example_ | _Notion_ | _script `scripts/fetchers/notion.py`_ | _`.env`: `NOTION_TOKEN`_ | _Read_ | _YYYY-MM-DD_ | _`references/notion-api.md`_ |

## Mechanism Key

- `mcp`: MCP server configured in `.mcp.json`.
- `script`: Python or Bash in `scripts/` that reaches an API directly.
- `skill`: A workflow in `.claude/skills/` that exposes the connection.
- `export`: Manual CSV/JSON export imported into `sources/`.
- `key+ref`: Credentials plus a reference doc, but no active script or MCP yet.
- `not connected`: Known system, not yet reachable.

## Doctrine: when MCP, when CLI or script

- **CLI or direct API is the default** for anything local, or where you control
  the integration. Token-light, scriptable, pipeable, and it does not load a
  schema into every session.
- **MCP earns its place for server-side or stateful things you do not control**:
  remote services needing OAuth flows, persistent sessions, or that only ship an
  MCP server.
- Trust rule either way: an MCP server is a shell on your machine. Only wire up
  servers you would trust with one.

## Maintenance

- Add a row the same day a system becomes reachable.
- Add `references/<tool>-api.md` when you research an API properly.
- Refresh `Last checked` when a connection is actually used or verified.
