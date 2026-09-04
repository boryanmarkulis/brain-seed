#!/bin/bash
# Claude Code statusline: context bar + session/weekly usage with reset times.

input=$(cat)
now=$(date +%s)

model_display=$(echo "$input" | jq -r '
  (.model | if type == "object" then .display_name elif type == "string" then . else "" end) as $raw
  | $raw
  | gsub("^[^/]+/"; "")
  | gsub("-[0-9]{8}$"; "")
  | if startswith("claude-") then
      gsub("^claude-";"") | gsub("-(?<a>[0-9])-(?<b>[0-9])(-[0-9]+)?$"; " \(.a).\(.b)")
    else . end
')

effort=$(echo "$input" | jq -r '.effort.level // empty')
used=$(echo "$input" | jq -r '.context_window.used_percentage // empty')
ctx_input=$(echo "$input" | jq -r '.context_window.current_usage.input_tokens // empty')
ctx_total=$(echo "$input" | jq -r '.context_window.context_window_size // empty')
fh=$(echo "$input" | jq -r '.rate_limits.five_hour.used_percentage // empty')
sd=$(echo "$input" | jq -r '.rate_limits.seven_day.used_percentage // empty')
fh_reset=$(echo "$input" | jq -r '.rate_limits.five_hour.resets_at // empty')
sd_reset=$(echo "$input" | jq -r '.rate_limits.seven_day.resets_at // empty')

# Context bar
if [ -n "$used" ]; then
  filled=$(echo "$used" | awk '{n=int($1/10+0.5); print (n>10?10:(n<0?0:n))}')
  empty=$((10 - filled))
  bar=""
  i=0; while [ $i -lt $filled ]; do bar="${bar}█"; i=$((i+1)); done
  i=0; while [ $i -lt $empty  ]; do bar="${bar}░"; i=$((i+1)); done
  tok_display=""
  if [ -n "$ctx_total" ]; then
    # Derive used tokens from percentage (input_tokens field is often 0)
    derived_input=$(echo "$used $ctx_total" | awk '{printf "%.0f", $1/100*$2}')
    used_k=$(echo "$derived_input" | awk '{printf "%.0fk", $1/1000}')
    total_k=$(echo "$ctx_total" | awk '{printf "%.0fk", $1/1000}')
    tok_display=" ${used_k}/${total_k}"
  fi
  ctx="context [${bar}] $(printf '%.0f' "$used")%${tok_display}"
else
  ctx="context [░░░░░░░░░░] --"
fi

fmt_short() {
  # seconds -> "3h20m" / "45m" / "2d4h"
  local s=$1
  [ -z "$s" ] || [ "$s" -le 0 ] && { echo "now"; return; }
  local d=$((s/86400)) h=$(((s%86400)/3600)) m=$(((s%3600)/60))
  if [ $d -gt 0 ]; then echo "${d}d${h}h"
  elif [ $h -gt 0 ]; then echo "${h}h${m}m"
  else echo "${m}m"
  fi
}

sess=$([ -n "$fh" ] && printf '%.0f' "$fh" || echo "--")
week=$([ -n "$sd" ] && printf '%.0f' "$sd" || echo "--")

sess_reset=""
[ -n "$fh_reset" ] && sess_reset=" \033[90mresets in $(fmt_short $((fh_reset - now)))\033[0m"
week_reset=""
[ -n "$sd_reset" ] && week_reset=" \033[90mresets in $(fmt_short $((sd_reset - now)))\033[0m"

prefix=""
if [ -n "$model_display" ]; then
  model_label="$model_display"
  [ -n "$effort" ] && model_label="${model_display} \033[2;36m·\033[0m \033[2;37m${effort}\033[0m"
  prefix="\033[2;37m${model_label}\033[0m   "
fi

# Sync conflict flag (set by scripts/sync.py when an auto-merge couldn't resolve).
# Surfaces a persistent warning until the divergence is reconciled by a human.
script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
if [ -f "${script_dir}/../.state/SYNC_CONFLICT" ]; then
  prefix="\033[1;31m⚠ SYNC CONFLICT (run: git merge origin/main)\033[0m   ${prefix}"
fi

printf "${prefix}%s   \033[36msession %s%%\033[0m%b   \033[33mweekly %s%%\033[0m%b" \
  "$ctx" "$sess" "$sess_reset" "$week" "$week_reset"
