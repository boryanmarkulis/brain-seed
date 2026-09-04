# The skills

A skill is a workflow written down so the agent runs it the same way every time.
They live in `.claude/skills/<name>/SKILL.md`.

Most agents read them automatically from that folder. If yours does not, the
files are plain markdown; point it at the one you want.

## Start with three

| | |
|---|---|
| **`/onboard`** | Once, at the start. The interview that makes the Brain yours. |
| **`/reflect`** | Every night. Closes the day, writes the daily file, triggers compile. |
| **`/doctor`** | Whenever you are unsure what to do next. Names one action. |

Everything else is optional until you want it.

## Setup and health

| Skill | Does | When |
|---|---|---|
| `/onboard` | Interviews you, writes `me/`, `CLAUDE.md`, `brain.config.json`, your voice rule | Once, on a fresh clone |
| `/connect` | Wires an external system in, end to end, and verifies it live | Each time you add a tool |
| `/doctor` | Scores setup completeness across five stages, names the next action | Weekly |
| `/audit` | Scores the knowledge itself: coverage, connections, capabilities, cadence | Weekly, once `/doctor` is past 70 |
| `/skill-builder` | Turns a repeated workflow into a proper skill | When something has repeated twice |

## The daily loop

| Skill | Does | When |
|---|---|---|
| `/action` | Morning. Interviews you, then sets one main thing plus at most two supports | Start of day |
| `/reflect` | Evening. Captures what happened, closes the loop, plans tomorrow | End of day |
| `/journal` | Captures a dated journal entry from anywhere, including a phone session | Any time |
| `/update` | Processes a voice dump or brain dump into the right files | After a call or a walk |

## Getting material in

| Skill | Does |
|---|---|
| `/pull <url>` | Universal ingestion. Detects the source type, fetches directly, near-zero token cost |
| `/ingest` | Pasted text, local files, stdin. Use when there is no URL |
| `/para-organizer` | Sorts a pile of files into Projects, Areas, Resources, Archives |

## Thinking

| Skill | Does | When |
|---|---|---|
| `/one-thing` | Finds the single highest-leverage move, argues for it, names what it makes unnecessary | When you feel busy but not productive |
| `/align` | Checks whether the last 14 days of actual work match your stated priorities | Fortnightly |
| `/roast` | Six-persona council attacks a new idea, then one verdict: GO, RESHAPE, or KILL | Before building something new |
| `/grill-me` | Stress-tests a plan, or pulls what is in your head into a document | Before committing to a plan |
| `/level-up` | Finds one automation worth building, then builds it | Weekly |

## Working

| Skill | Does |
|---|---|
| `/review` | Reviews what you changed in this session, before committing |
| `/session-handoff` | Structured summary so a fresh session can continue seamlessly |

## Writing your own

Run `/skill-builder`. It covers when a skill is warranted (it usually is not),
the frontmatter shape, and how to test one before shipping it.

The short version: a skill earns its place when the workflow has genuinely
happened twice, it has steps that are easy to get wrong, and doing it right
needs context that is not obvious from the repo. Otherwise it is a bookmark
pretending to be a system, and it costs context on every session.

## Deleting the ones you do not use

Delete them. Every skill in the folder is a small standing cost. This template
ships a broad set so you can see what is possible; a Brain that has been used
for six months usually has fewer skills than it started with, and each one is
sharper.
