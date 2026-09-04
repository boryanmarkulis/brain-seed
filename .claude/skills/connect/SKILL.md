---
name: connect
description: Wire an external system into the Brain, end to end. Picks the right mechanism (direct API script, CLI, or MCP), walks the owner through auth, writes a working fetcher or helper, verifies it against live data, and records the row in connections.md. Use for "connect my CRM", "wire up Notion", "/connect <tool>", or any time the Brain needs to reach something it cannot reach yet.
argument-hint: "<tool or system name>"
---

# /connect - Wire a system in, properly

A Brain that can only read its own folders is a notebook. The value shows up
when it can read the systems where your real work already lives.

This skill ends with a **verified live call**, not a config file. A connection
that has never returned real data is not connected.

## Step 1 - Decide the mechanism

Read the doctrine section of `connections.md`, then pick one. Do not default to
MCP because it is fashionable.

| Situation | Use |
|---|---|
| The service has a plain REST API and you hold a token | **direct API script** in `scripts/` |
| There is already a good CLI, logged in on this machine | **CLI**, shelled out from a script |
| OAuth dance, persistent session, or the vendor only ships an MCP server | **MCP** in `.mcp.json` |

Direct scripts win by default. They are token-light, pipeable, testable, and
they do not load a tool schema into every single session. MCP earns its place
for stateful remote things you do not control.

**Trust rule:** an MCP server runs code on the owner's machine. Only wire up
servers you would trust with a shell.

## Step 2 - Get auth, without ever seeing the secret

1. Tell the owner exactly where to create the credential. Give the real URL and
   the exact menu path, not "go to settings".
2. Tell them exactly which scopes or permissions to grant, and no more.
3. Have them put the value in `.env` themselves. **You never read `.env` back
   and never echo a token.** If you need to check it exists, test for the
   variable being non-empty, not for its value.
4. If the flow is interactive (a browser login), tell them to run it themselves
   with `! <command>` so the output lands in the session.

## Step 3 - Build the smallest thing that works

Write one helper in `scripts/`, following the shape of `scripts/fetchers/web.py`:

- reads its token from the environment, never a hardcoded string
- one function per real operation, not a generic passthrough
- prints JSON on stdout so other scripts can pipe it
- fails loudly with the actual API error, never a swallowed exception

If the system will feed `sources/`, make it a fetcher under `scripts/fetchers/`
and register the URL pattern in `scripts/fetchers/__init__.py` so `/pull` picks
it up automatically.

## Step 4 - Verify against live data

Run a real read. Show the owner actual records that came back. Ask them to
confirm the data is what they expected, because an API that returns the wrong
account's data returns it with a 200.

**For anything with write access, stop here and read this twice.** Before any
write that touches more than one record:

- Say exactly what the payload is and exactly how many records it hits.
- Name every downstream automation the write could trigger. A data write can be
  an outbound message campaign in a CRM. This has happened, it hurt, and it is
  why this paragraph exists.
- Test on one record. Look at the real result. Then ask for confirmation.
- Only then release the rest, and throttle it.

If the system has automations that fire on tags, field changes, or record
creation, write them down in `references/<tool>-triggers.json` first. If you
cannot enumerate them, you are not ready to write.

## Step 5 - Record it

Add one row to `connections.md`:

| Domain | Tool | Mechanism | Auth Location | Read/Write | Last checked | Reference |

Name the env var. **Never the value.** Then, if the API was non-obvious, write
`references/<tool>-api.md` with the endpoints, the gotchas, and the exact shape
of a working request. Future you will need it.

Append to `log.md`:

```
[YYYY-MM-DD] CONNECT: <tool> wired via <mechanism>, read verified
```

## Step 6 - Tell them what it unlocked

Close with the concrete thing they can now do that they could not before. Not
"Notion is connected" but "you can now say `/pull <any notion url>` and it lands
in `sources/notion/`."

## Common first connections

Most people want these, roughly in this order:

1. **Their own writing** - wherever it lives. This is the highest-value source
   in the whole Brain because it is the only one written in their voice.
2. **Notes app or wiki** - Notion, Obsidian, Apple Notes, Google Docs.
3. **Calendar and email** - for the daily loop.
4. **Whatever holds the money** - CRM, invoicing, ad accounts, analytics.
5. **Messages** - the hardest and the most valuable, because it is where
   relationships actually live.
