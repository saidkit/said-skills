#!/usr/bin/env bash
# SessionStart hook (matcher: clear|compact): re-anchor the session from disk after a /clear or a compaction.
# Prints the status reconstruction, the open run-protocol files left in this project's session scratchpads,
# and a re-issue instruction; stdout is injected into the new context. Silent on every other source, and
# silent outside a SAID lane (the hook is active wherever the plugin is enabled).
# Env: SAID_STATUS  path to said_status.py (default: the one bundled with this plugin)
#      SCRATCH_ROOT root of the per-session scratchpads (default: /private/tmp/claude-<uid>, else /tmp/claude-<uid>)
input=$(cat)
here="$(cd "$(dirname "$0")" && pwd)"   # before any cd: $0 may be relative
field() { printf '%s' "$input" | python3 -c "import json,sys; d=json.load(sys.stdin); v=$1; print('' if v is None else v)" 2>/dev/null; }

src=$(field 'd.get("source") or d.get("session_source") or ""')
case "$src" in clear|compact) ;; *) exit 0 ;; esac

cwd=$(field 'd.get("cwd","")')
# Only a SAID lane (a CLAUDE.md with a "## Lane" heading at column 0, outside code fences) is re-anchored;
# anywhere else stay silent.
[ -n "$cwd" ] && awk '/^(```|~~~)/ { f = !f; next } !f && /^## Lane/ { found = 1; exit } END { exit !found }' \
  "$cwd/CLAUDE.md" 2>/dev/null || exit 0
cd "$cwd" 2>/dev/null

status="${SAID_STATUS:-$here/../skills/status/said_status.py}"
if [ -z "${SCRATCH_ROOT:-}" ]; then
  if [ -d /private/tmp ]; then SCRATCH_ROOT="/private/tmp/claude-$(id -u)"; else SCRATCH_ROOT="/tmp/claude-$(id -u)"; fi
fi
slug=$(printf '%s' "$cwd" | sed 's#/#-#g')

echo "RE-ANCHOR after \`$src\` -- state below is read from disk, not from the conversation summary."
feature=$(git branch --show-current 2>/dev/null | sed -n 's#^[a-z]*/\([A-Za-z]*-[0-9][0-9]*\).*#\1#p' | tr '[:lower:]' '[:upper:]')
if [ -f "$status" ]; then
  if [ -n "$feature" ]; then python3 "$status" "$feature" 2>/dev/null | head -60
  else python3 "$status" --stale 2>/dev/null | head -40; fi
else
  echo "(status script not found; set SAID_STATUS) -- run /said:status to reconstruct."
fi

# Open run protocols: live leaves only -- a think-<id>.md whose Closed: header is "no", whose Gate log carries
# no final verdict, and which no other open run names as its Parent. Newest first, capped at 20.
open_runs=$(python3 - "$SCRATCH_ROOT/$slug" <<'PY' 2>/dev/null
import glob, os, re, sys
runs = {}
for f in sorted(glob.glob(os.path.join(sys.argv[1], "*", "scratchpad", "think-*.md"))):
    t = open(f, errors="replace").read()
    m = re.search(r"Closed:\s*([^\s|]*)", t)
    closed = bool(m) and m.group(1).lower() not in ("", "no")
    gate = t.split("## Gate log", 1)[1] if "## Gate log" in t else ""
    if closed or re.search(r"all PASS|escalated", gate):
        continue
    p = re.search(r"Parent:\s*([^\s|]+)", t)
    runs[f] = (os.path.basename(f)[len("think-"):-len(".md")], p.group(1) if p else "none")
parents = {par for _, par in runs.values()}
leaves = sorted((f for f, (rid, _) in runs.items() if rid not in parents), key=os.path.getmtime, reverse=True)
for f in leaves[:20]:
    print(f)
if len(leaves) > 20:
    print("+%d more (older; list them with the run manager)" % (len(leaves) - 20))
PY
)
if [ -n "$open_runs" ]; then
  echo "Open run protocols (continue one with its path):"
  printf '%s\n' "$open_runs" | sed 's/^/  /'
fi
echo "Next: re-issue the same directive; the skill re-derives its phase by inspection."
