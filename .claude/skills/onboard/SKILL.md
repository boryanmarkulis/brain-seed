---
name: onboard
description: Turn a fresh brain-seed clone into this person's actual second brain. Interviews the owner, writes me/, CLAUDE.md, brain.config.json and the voice rule, then hands off to /connect and the first source ingest. Use on a new clone, when the owner says "/onboard", "set up my brain", "let's start", or when brain.config.json still says "not set yet".
argument-hint: "[--resume] [--section me|mission|priorities|voice|problems]"
---

# /onboard - Build the Brain around the person

This runs once, properly. It takes 30 to 45 minutes of real conversation and it
is the difference between a folder of empty markdown and a system that knows who
it works for.

**You are conducting an interview, not filling a form.** Ask one question at a
time. Listen to the answer. Ask the follow-up that the answer earned. A person
who gives you a thin answer has not been asked a good enough question yet.

## Before you start

Read `brain.config.json`. If `owner` is still `"the owner"`, this is a fresh
clone and you run the whole thing. If it is filled in, ask which section they
want to redo and jump there.

Then say this, in your own words, and wait:

> This is going to feel like a long conversation, because it is one. Everything
> you tell me here becomes the standing context for every future session, so
> vague answers now cost you forever. About 40 minutes. Ready?

## Rules for the whole interview

- **One question per message.** Never batch. Never dump a numbered list of
  questions and ask them to fill it in. That produces resume language.
- **Never accept the first abstraction.** "I help businesses grow" is not an
  answer. Ask what they did last Tuesday. Ask who paid them last. Concrete
  beats aspirational every time.
- **Reflect back before writing.** "So the real thing is X, and Y is just how
  you fund it. Right?" Let them correct you. The correction is the gold.
- **Write nothing until a section is done.** Then write the whole file at once
  and show it. Ask "does this sound like you?" and fix what does not.
- **Steal their words.** The files should read in their voice, not yours. If
  they said "I'm sick of doing this by hand", that line goes in the file.

## Section 1 - Who they are (`me/me.md`)

Open with the easy one and get specific fast.

1. What do you actually do all day? Not your title, the hours.
2. Where do you live, and what timezone should I assume when you say "tomorrow"?
3. What are you genuinely good at, that you have proof of?
4. What are you bad at, that keeps costing you? (Push here. This is the field
   that makes the agent useful, because it tells you when to push back.)
5. How do you want to be talked to? Blunt or gentle? Long or short? Do you want
   to be argued with?

Write `me/me.md`. Show it. Fix it.

## Section 2 - The mission (`CLAUDE.md`)

This is the hardest question and it deserves its own section.

Ask: **if everything went right, what would be different about the world?**

Then keep going until it is one sentence they would actually say out loud. Test
it: "Would you say that to a friend at a bar, or is that a LinkedIn sentence?"

A good mission is specific enough to reject things. "Help people" rejects
nothing. For example, "Make essential information easier to understand"
rejects unrelated work, which is the whole point.

Write it into the `{{MISSION}}` slot in `CLAUDE.md` and mirror it to `AGENTS.md`
byte-identical.

## Section 3 - Work and money (`me/work.md`)

The Brain is useless if it does not know how the rent gets paid.

1. Who pays you right now? Name each one.
2. How much, and what triggers the payment? (Retainer? Per deal? Per hour?)
3. Which of those terms are written down, and which are just verbal?
4. What is the single biggest thing that is not working?

The verbal-versus-written question matters. Record it in the file. It is the
kind of thing that quietly becomes a problem, and having it stated means the
agent can raise it later.

## Section 4 - Priorities (`me/priorities.md`)

1. If you could only move one thing forward this quarter, what is it?
2. What is second? Third?
3. **What have you decided to stop doing?** (This list is as important as the
   first. Without it the agent keeps reviving dead work.)

Stamp today's date as `Last reviewed`.

## Section 5 - Favorite problems (`areas/favorite-problems.md`)

Explain the idea first: Feynman kept a dozen open problems in his head and
tested everything new against all twelve. Most of the time nothing happened.
Occasionally something clicked and it looked like genius.

Then get 8 to 12 out of them. Prompt with: what do you keep googling? What
argument do you keep having? What would you read a whole book about right now?

Each one has to be phrased as a question they cannot yet answer.

## Section 6 - Voice (`.claude/rules/communication-style.md`)

Do not ask them to describe their voice. People describe the voice they wish
they had.

Instead: **ask them to paste three things they actually wrote.** A message to a
friend, a message to a client, and something they published. Read those, then
write the voice rule from evidence and show your reasoning:

> You use short sentences when you are serious and long ones when you are
> excited. You never use exclamation marks. You swear about twice a page. You
> open with the point, not a greeting.

Let them correct it. Then write the file.

## Section 7 - Config

Write `brain.config.json` from everything above:

```json
{
  "owner": "their name",
  "mission": "the one sentence from Section 2",
  "work": "one line: what they do and who pays them",
  "voice": "one line summary from Section 6",
  "timezone": "their IANA zone, e.g. Europe/Lisbon",
  "domains": ["the 3-6 subjects their knowledge actually covers"],
  "wiki_scope": "one line on what the wiki should and should not absorb"
}
```

Then run `python3 scripts/brain_config.py` and show them the output. Every LLM
prompt in `scripts/` now speaks about them, by name, with their mission.

**On `domains`:** ask what subjects their knowledge covers, and include the
ones from a past life. A former career is not off-topic just because it is not
the current mission. The wiki compiler uses this list, and a narrow list means
years of hard-won experience get silently dropped.

## Section 8 - Hand off

Do not stop here. The Brain is configured but empty. Say so, and give them the
next three moves in order:

1. **`/connect`** - wire up the systems that hold their real data.
2. **`/pull <url>`** - feed it. Their own writing first, then everything else.
   Point at `docs/03-getting-your-stuff-in.md`.
3. **`/action`** tomorrow morning, **`/reflect`** tomorrow night. The loop only
   starts producing once there are daily files to compile.

Then append to `log.md`:

```
[YYYY-MM-DD] ONBOARD: brain configured for <name>
```

And append the mission decision to `decisions/log.md`, because choosing a
mission is the first real decision this Brain records.

## When they resist

Some people stall on the mission question. That is normal and it is not a
failure of the interview. Two ways through:

- **Go backwards.** "Forget the future. What is the best thing you have ever
  built or done?" The mission is usually hiding in the answer.
- **Write a bad one on purpose.** "Here is a deliberately mediocre version.
  Tell me what is wrong with it." People find it much easier to correct a wrong
  answer than to produce a right one from nothing.

Never let them off with a placeholder. A Brain with no mission cannot filter
anything, and an unfiltered Brain is just a folder.
