#!/usr/bin/env bash
# Statusline command: renders "<model>, ctx <n>%" and writes the session's context usage to
# <SCRATCH_ROOT>/<cwd-slug>/<session_id>/scratchpad/context.json (valid JSON, null for a missing value),
# the only place a skill can read context size from. Optional install: point settings.json "statusLine" here.
# Env: SCRATCH_ROOT root of the per-session scratchpads (default: /private/tmp/claude-<uid>, else /tmp/claude-<uid>)
input=$(cat)
if [ -z "${SCRATCH_ROOT:-}" ]; then
  if [ -d /private/tmp ]; then SCRATCH_ROOT="/private/tmp/claude-$(id -u)"; else SCRATCH_ROOT="/tmp/claude-$(id -u)"; fi
fi
printf '%s' "$input" | SCRATCH_ROOT="$SCRATCH_ROOT" python3 -c '
import datetime, json, os, re, sys
try:
    d = json.load(sys.stdin)
except Exception:
    d = {}
cw = d.get("context_window") or {}
sid = d.get("session_id") or ""
cwd = d.get("cwd") or (d.get("workspace") or {}).get("current_dir") or ""
used = cw.get("used_percentage")
root = os.path.realpath(os.environ["SCRATCH_ROOT"])
path = os.path.realpath(os.path.join(root, cwd.replace("/", "-"), sid, "scratchpad")) if sid and cwd else ""
# Write only for a plain session id and only inside the scratchpad root.
if path and re.fullmatch(r"[A-Za-z0-9_-]+", sid) and os.path.commonpath([root, path]) == root:
    try:
        os.makedirs(path, exist_ok=True)
        tmp = os.path.join(path, ".context.json.%d" % os.getpid())
        with open(tmp, "w") as f:
            json.dump({"session_id": sid, "used_percentage": used,
                       "total_input_tokens": cw.get("total_input_tokens"),
                       "updated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}, f)
            f.write("\n")
        os.replace(tmp, os.path.join(path, "context.json"))  # atomic: a reader never sees a partial file
    except OSError:
        pass
model = (d.get("model") or {}).get("display_name") or ""
pct = "?" if used is None else ("%g" % used)
sys.stdout.write("%s, ctx %s%%" % (model, pct))
' 2>/dev/null
