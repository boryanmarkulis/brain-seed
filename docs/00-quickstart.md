# Quickstart: the first hour

## 0. Check you have the pieces (2 min)

```bash
python3 --version      # need 3.10 or newer
git --version
which claude || which codex   # need at least one agent CLI, logged in
```

Optional but recommended:

```bash
pip3 install numpy     # semantic search over the wiki
```

## 1. Clone and make it yours (2 min)

```bash
git clone https://github.com/boryanmarkulis/brain-seed.git my-brain
cd my-brain
rm -rf .git
git init -b main
git add -A && git commit -m "brain: seed"
```

Dropping the original `.git` matters. This becomes *your* repo with *your*
history, and none of your private notes ever share a remote with the template.

Then give it somewhere to live, so you get backup and multi-device sync free:

```bash
gh repo create my-brain --private --source=. --push
```

Make it **private**. This will end up holding your notes, your income, and your
unfiltered thinking about people you work with.

## 2. See where you stand (1 min)

```bash
python3 scripts/brain_doctor.py
```

It will say roughly 22/100. That is correct for an empty clone. It also names
your single next action, which right now is `/onboard`.

## 3. Onboard (40 min)

Open the folder in your agent and say:

```
/onboard
```

This is a real interview. It asks who you are, what your mission is, how you
get paid, what you have decided to stop doing, what your open problems are, and
then it asks you to paste three things you actually wrote so it can learn your
voice from evidence rather than from your description of it.

Answer properly. Every one of those answers becomes standing context in every
future session. Vague now is vague forever.

It writes: `me/*.md`, the mission in `CLAUDE.md` and `AGENTS.md`,
`brain.config.json`, `areas/favorite-problems.md`, and
`.claude/rules/communication-style.md`.

## 4. Wire up one system (10 min)

```
/connect <the tool where your own writing lives>
```

Start there, not with your CRM. Your own writing is the highest-value source in
the whole Brain, because it is the only material in your actual voice.

## 5. Feed it (15 min, then ongoing)

```
/pull <url>
```

Point it at things you wrote. Then things you read. See
[`03-getting-your-stuff-in.md`](03-getting-your-stuff-in.md) for bulk backfills
of a Notion workspace, a Drive folder, or a whole publication archive.

## 6. Start the daily loop

Tomorrow morning:

```
/action
```

Tomorrow night:

```
/reflect
```

That is it. `/action` opens the day by helping you pick one real thing.
`/reflect` closes it, writes the daily file, and triggers the compile.

## What happens next, without you

Once there are daily files and sources:

- `SessionStart` pulls from origin, kicks off a compile if one is due, and warns
  you about any background job that has been silently failing.
- `SessionEnd` marks a compile as needed, looks for repeated workflows worth
  turning into skills, and pushes to origin.
- The compiler routes new material into wiki pages and rewrites the Learned
  Rules section of `CLAUDE.md` from your corrections.

Check in with `/doctor` every week or so. It always names one next thing.

## Realistic expectations

- **Day 1:** an organised empty folder that knows who you are.
- **Week 1:** daily capture is running, a handful of wiki pages exist, most are thin.
- **Month 1:** the wiki starts answering questions you would otherwise re-research.
  `CLAUDE.md` has learned rules you never wrote by hand.
- **Month 3:** you stop re-explaining yourself to your agent, and that is the
  whole point of the thing.

It compounds. It does not impress on day one.
