# Running the wiki compiler locally, for free

The default compiler shells out to whichever agent CLI you are logged into,
which costs nothing extra beyond your existing plan but does send content to a
provider. The local pipeline does the whole thing on your own machine: free,
offline, private, and it can run overnight on years of material without you
watching a token counter.

## What you need

- Apple Silicon Mac with 32GB+ (a 64GB machine runs the 30B comfortably), or a
  Linux box with a decent GPU
- [llama.cpp](https://github.com/ggerganov/llama.cpp): `brew install llama.cpp`
- 20 to 40GB of disk for model weights

```bash
python3 -c "import sys; sys.path.insert(0,'scripts'); import llm_local; print(llm_local.available())"
```

That prints which registered models are present on disk. Download a missing one
from Hugging Face into `~/.cache/llama-models/` or let the standard HF cache
hold it; `llm_local.py` looks in both.

## The two stages, and why there are two

A single "read everything and write the wiki" pass hallucinates. Not
occasionally, structurally: the model is asked to both find facts and phrase
them well in one breath, and phrasing wins.

So the work is split.

**Stage 1: extract.** `wiki_extract.py` reads raw sources in chunks and emits
records constrained by a GBNF grammar, so the output is machine-parseable by
construction rather than by hope. Each record is a claim plus a **verbatim
evidence quote**. The quote is then checked against the source document. If it
does not appear literally, the record is thrown away.

That check is the entire trick. A model cannot invent a fact if the fact must
come with a quote that has to exist.

**Stage 2: consolidate.** `wiki_consolidate.py` groups verified records by
concept and merges them into pages, preserving what is still true, deduplicating
restatements, and stating both sides when a new record contradicts the page.

There is a second guard here. Daily and journal files cover a whole day and can
hold three unrelated subjects, but stage 1 labels each chunk with one concept.
So a rarity-weighted vocabulary overlap check rejects records that do not
actually belong to the page they were routed to. Rejects go to
`.state/wiki-offtopic.jsonl` rather than being deleted, so you can read what the
guard caught and retune the threshold for your own vault.

## Running it

```bash
python3 scripts/wiki_extract.py --limit 20      # try a small batch first
python3 scripts/wiki_consolidate.py --dry-run   # see what it would write
python3 scripts/wiki_consolidate.py
```

One concept at a time:

```bash
python3 scripts/wiki_consolidate.py --slug pricing-anchor
```

## Letting it run itself

`maybe_wiki.py` is a catch-up gate, not a clock. Point a scheduler at it hourly
(launchd on macOS, cron or a systemd timer on Linux) and it decides whether to
run:

- a lock file holds the live pid, and a stale lock is cleared
- `.state/wiki-stop` present means you halted it deliberately, so it stays out
- the machine must have been idle for 15 minutes
- it must be in the overnight window, on AC power and Wi-Fi, **or** the last
  clean run must be older than 60 hours

`wiki_daylight.sh` is the version that can run while you are using the machine.
It yields the moment you touch the keyboard and frees the ~19GB the model holds.

**The timezone trap, because it costs a day to find.** Schedulers often run jobs
with `TZ` unset, so a naive `datetime.now()` there is UTC while the same code in
your shell is local. In a zone ahead of UTC the stamp reads as the future, the
threshold never elapses, and the wiki silently stops compiling with no error
anywhere. Every timestamp written by these scripts is timezone-aware. Keep it
that way.

## Semantic search

Separate, smaller model. Worth setting up even if you use the cloud compiler.

```bash
pip3 install numpy
python3 scripts/wiki_embed.py            # build the index
python3 scripts/wiki_search.py --pages -k 6 "your real question"
```

Embeddings are section-level, so a skill loads the relevant paragraph rather
than a whole page. The index is fingerprinted against the wiki; if it drifts,
`wiki_search.py` refuses to answer and tells you to rebuild instead of quietly
returning stale hits.

## Which model

Defaults live in `brain.config.json`:

```json
"local_model": "qwen3-30b-a3b",
"embed_model": "qwen3-embed-4b"
```

The 30B MoE is the sweet spot on a 64GB Mac: strong extraction, tolerable speed.
On 32GB drop to `qwen3-8b`. Quality falls off but the pipeline still works, and
the evidence-quote check means the failure mode is fewer records rather than
wrong ones.

**One gotcha with Qwen3 hybrid-reasoning models:** they need an empty
`<think></think>` block injected after the assistant turn to switch reasoning
off, so the GBNF grammar applies from the first token. The `*-Instruct-2507`
models are non-thinking by design and must not get that block. `llm_local.py`
handles this per model in its registry. If you add a model, set `think`
correctly or the grammar silently stops constraining output.
