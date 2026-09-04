---
name: doctor
description: Show how far along this Brain is and what the single next move should be. Runs a local completeness scan across identity, capture, connections, synthesis, and the learning loop. Use for "how is my brain doing", "am I set up", "what should I do next", "/doctor", or on any fresh clone.
argument-hint: "[--verbose]"
---

# /doctor - How far along am I?

Run it:

```bash
python3 scripts/brain_doctor.py            # the report
python3 scripts/brain_doctor.py --verbose  # show passing checks too
python3 scripts/brain_doctor.py --json     # machine-readable
```

No model call, no network. It reads the repo and scores five stages.

## What the stages mean

The stages are **dependency-ordered**, and that ordering is the whole point.

1. **Identity** - does the Brain know whose it is? Every LLM prompt in
   `scripts/` interpolates the owner's name, mission, and voice. Until this is
   filled in, the compiler is writing a wiki about nobody.
2. **Capture** - is real material coming in? Sources and daily files.
3. **Connections** - can it reach the systems where the work already lives?
4. **Synthesis** - is raw capture turning into queryable knowledge?
5. **The loop** - is it learning from corrections without being maintained?

Because they are ordered, the `NEXT:` line always names an action from the
earliest incomplete stage. Do not chase a low score in stage 4 while stage 1 is
empty. That produces a large, confident, useless wiki.

## How to report it

Give the owner three things and stop:

1. The overall score and the weakest stage.
2. The `NEXT:` action, in your own words, with the exact command.
3. Any `ENVIRONMENT` warning, because those are hard blockers rather than
   incompleteness. A missing `numpy` or a missing git remote is not "40% done",
   it is broken.

Do not read the whole report aloud. Do not offer to fix everything at once.
One next action.

## Then offer to do it

If the next action is something you can do in-session (run `/onboard`, run
`compile.py`, build the embedding index), offer to run it now. If it needs the
owner (create an API token, decide a mission), say exactly what you need from
them.

## Sibling skills

- `/audit` scores the **knowledge** inside a Brain that is already running:
  coverage, link density, orphan pages, stale material. Use it once `/doctor`
  is above roughly 70.
- `python3 scripts/brain_audit.py` is the raw data behind `/audit`: link graph,
  broken links, orphans, source coverage, near-duplicate slugs.
