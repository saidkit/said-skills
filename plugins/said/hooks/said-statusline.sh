#!/usr/bin/env bash
# Version-stable statusline entry point: runs the statusline script of the newest installed said version,
# so a settings.json "statusLine" pointing here survives plugin updates. stdin is passed through.
# Newest = highest version directory (cache layout <cache>/<marketplace>/said/<version>/hooks/), compared by
# version, never by whole path; a release ranks above its own pre-release. No installed script -> prints the model name (or a fallback) and exits 0,
# so the statusline never breaks.
# Env: SAID_PLUGIN_CACHE  plugin cache root (default: ~/.claude/plugins/cache)
cache="${SAID_PLUGIN_CACHE:-$HOME/.claude/plugins/cache}"
best=""
if [ -d "$cache" ]; then
  best=$(for f in "$cache"/*/said/*/hooks/statusline-context.sh; do
           [ -f "$f" ] || continue
           v="${f%/hooks/statusline-context.sh}"; v="${v##*/}"
           base="${v%%-*}"; rel=1; pre=""
           [ "$base" != "$v" ] && { rel=0; pre="${v#*-}"; }   # a release outranks its own pre-release
           printf '%s\t%s\t%s\t%s\n' "$base" "$rel" "$pre" "$f"
         done | sort -t "$(printf '\t')" -k1,1V -k2,2n -k3,3V | tail -1 | cut -f4)
fi
if [ -n "$best" ]; then
  exec bash "$best"
fi
input=$(cat)
model=$(printf '%s' "$input" | python3 -c 'import json,sys
try: print((json.load(sys.stdin).get("model") or {}).get("display_name") or "")
except Exception: print("")' 2>/dev/null)
printf '%s\n' "${model:-statusline: said plugin not found}"
exit 0
