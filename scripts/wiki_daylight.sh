#!/usr/bin/env bash
# Daytime wiki compiler. Same two stages as the overnight scripts, but built to
# run while you are using the Mac.
#
#   scripts/wiki_daylight.sh [STAGE] [BATCH] [MODEL]
#
#     STAGE  2 (default) | 1 | both     2 = consolidate staged records into pages
#     BATCH  concepts per checkpointed slice (default 15)
#     MODEL  default qwen3-30b-a3b
#
# Differences from the overnight scripts, all deliberate:
#
#   - No AC-power abort. It runs on battery and stops cleanly at the floor
#     below instead of refusing to start.
#   - No caffeinate. The Mac is allowed to sleep. Both stages checkpoint, so a
#     lid close costs at most the batch in flight.
#   - nice'd. The GPU still gets saturated by llama-server (that is where the
#     work happens), but the driver stops competing for CPU with the editor.
#   - Stop flag. `touch .state/wiki-stop` and it halts after the current batch,
#     shuts the server down and frees the ~19GB back.
#   - Yields on its own. Between batches it also halts if you touched the
#     keyboard in the last IDLE_FLOOR seconds, or if macOS reports memory
#     pressure above normal. Nothing is lost; the next hourly fire resumes.
#
# Progress:  scripts/wiki_progress.sh -w   or   tail -f .state/wiki-daylight.log
# Stop:      touch .state/wiki-stop

set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAGE="${1:-2}"
BATCH="${2:-15}"
MODEL="${3:-qwen3-30b-a3b}"
LOG="$REPO/.state/wiki-daylight.log"
STOP="$REPO/.state/wiki-stop"

# Below this the run parks itself rather than draining the machine flat. The
# work is resumable, so stopping early costs nothing but the batch in flight.
BATTERY_FLOOR=35

# Yield the machine back the moment you are at it. The run holds ~19GB for
# llama-server, so "he touched the keyboard" is enough reason to stop: both
# stages checkpoint, and maybe_wiki.py retries on the next hourly fire.
# 0 disables the check (set WIKI_IDLE_FLOOR=0 for a deliberate hand-run).
IDLE_FLOOR="${WIKI_IDLE_FLOOR:-300}"   # seconds since last keyboard/mouse event

hid_idle_seconds() {
  ioreg -c IOHIDSystem 2>/dev/null \
    | awk '/HIDIdleTime/ {print int($NF/1000000000); exit}'
}

say() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }

rm -f "$STOP"

should_stop() {
  if [ -f "$STOP" ]; then
    say "stop flag set, halting"
    return 0
  fi
  if [ "$IDLE_FLOOR" -gt 0 ] 2>/dev/null; then
    idle=$(hid_idle_seconds)
    # Empty means the sensor failed to read. Treat that as idle and carry on;
    # the clock window in maybe_wiki.py is still the outer guard.
    if [ -n "$idle" ] && [ "$idle" -lt "$IDLE_FLOOR" ] 2>/dev/null; then
      say "You are active (idle ${idle}s < ${IDLE_FLOOR}s floor), halting and freeing RAM"
      return 0
    fi
  fi

  # macOS's own verdict, not a free-byte guess: llama-server legitimately eats
  # most of RAM, so only warn (2) or critical (4) means we are hurting anyone.
  pressure=$(sysctl -n kern.memorystatus_vm_pressure_level 2>/dev/null)
  if [ -n "$pressure" ] && [ "$pressure" -gt 1 ] 2>/dev/null; then
    say "memory pressure level $pressure (not normal), halting and freeing RAM"
    return 0
  fi

  if ! pmset -g batt | grep -q "AC Power"; then
    pct=$(pmset -g batt | grep -oE '[0-9]+%' | tr -d '%' | head -1)
    if [ -n "$pct" ] && [ "$pct" -lt "$BATTERY_FLOOR" ] 2>/dev/null; then
      say "battery at ${pct}% (floor ${BATTERY_FLOOR}%), halting. Plug in and rerun."
      return 0
    fi
  fi
  return 1
}

shutdown_server() {
  say "stopping llama-server"
  python3 -c "
import sys; sys.path.insert(0, '$REPO/scripts')
import llm_local; llm_local.stop_server()
" 2>&1 | tee -a "$LOG"
}

run_extract() {
  say "stage 1 (extract) starting with $MODEL"
  # --limit slices so the stop flag and battery floor get checked between
  # groups of chunks instead of only at the end of a multi-hour run.
  while true; do
    should_stop && return 0
    pending=$(python3 -u "$REPO/scripts/wiki_extract.py" --status 2>/dev/null \
              | awk '/chunks:/{for(i=1;i<=NF;i++) if($i=="pending"){print $(i-1); exit}}' | tr -d ',')
    if [ -z "$pending" ] || [ "$pending" -eq 0 ] 2>/dev/null; then
      say "stage 1: no chunks pending"
      return 0
    fi
    say "stage 1: $pending chunks pending"
    nice -n 10 python3 -u "$REPO/scripts/wiki_extract.py" \
      --model "$MODEL" --limit 10 2>&1 | tee -a "$LOG"
    rc=$?
    if [ "$rc" -ne 0 ]; then
      say "stage 1 slice exited $rc, stopping"
      return "$rc"
    fi
  done
}

run_consolidate() {
  say "stage 2 (consolidate) starting (batch=$BATCH model=$MODEL)"
  round=0
  strikes=0
  MAX_STRIKES=2
  while true; do
    should_stop && return 0
    round=$((round + 1))

    pending=$(python3 -u "$REPO/scripts/wiki_consolidate.py" --status 2>/dev/null \
              | awk '/^\[.*\] pending:/{print $3; exit}')
    if [ -z "$pending" ] || [ "$pending" -eq 0 ] 2>/dev/null; then
      say "stage 2: no concepts pending, stopping after $((round - 1)) batches"
      return 0
    fi
    say "stage 2 batch $round: $pending concepts pending"

    out=$(nice -n 10 python3 -u "$REPO/scripts/wiki_consolidate.py" \
            --limit "$BATCH" --backend local --model "$MODEL" 2>&1 | tee -a "$LOG")
    rc=$?

    wrote=$(printf '%s\n' "$out" | awk '/done: [0-9]+ pages written/{for(i=1;i<=NF;i++) if($i=="done:"){print $(i+1); exit}}')
    wrote=${wrote:-0}

    if [ "$wrote" -gt 0 ] 2>/dev/null; then
      strikes=0
    else
      strikes=$((strikes + 1))
      say "stage 2 batch $round wrote 0 pages (strike $strikes/$MAX_STRIKES, exit $rc)"
      if [ "$strikes" -ge "$MAX_STRIKES" ]; then
        say "STOPPING: $MAX_STRIKES consecutive batches wrote nothing. The backend is broken, not busy."
        say "Check: python3 scripts/llm_local.py  and  tail ~/Library/Logs/brain/llama-server.log"
        return 1
      fi
    fi

    if [ "$rc" -ne 0 ] && [ "$rc" -ne 2 ]; then
      say "stage 2 batch $round crashed (exit $rc), stopping"
      return "$rc"
    fi
  done
}

# The embedding index is what makes the wiki searchable by meaning instead of
# keyword, so it has to be refreshed in the same pass that writes pages or it
# silently drifts behind them. It runs AFTER the chat model is shut down: it
# loads its own 0.6B model on :8081 and there is no reason to hold ~19GB while
# it does. Incremental and hash-keyed, so a no-op costs seconds.
run_embed() {
  say "stage: embeddings"
  nice -n 10 python3 -u "$REPO/scripts/wiki_embed.py" 2>&1 | tee -a "$LOG"
  erc=${PIPESTATUS[0]}
  [ "$erc" -ne 0 ] && say "embedding refresh exited $erc (pages are still written)"
  return 0
}

say "daylight run: stage=$STAGE batch=$BATCH model=$MODEL"

case "$STAGE" in
  1)    run_extract ;;
  2)    run_consolidate ;;
  both) run_extract && run_consolidate ;;
  *)    say "unknown stage '$STAGE' (use 1, 2, or both)"; exit 1 ;;
esac
FINAL=$?

shutdown_server
run_embed
say "daylight run done (exit $FINAL). wiki pages: $(find "$REPO/wiki" -name '*.md' | wc -l | tr -d ' ')"
rm -f "$STOP"
exit "$FINAL"
