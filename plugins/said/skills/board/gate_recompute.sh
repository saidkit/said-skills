#!/usr/bin/env bash
# Deterministic recompute for a lane's cli gate: the lane's own command line, then every evaluation harness.
# Lane root = $SAID_ROOT (default: the current dir); docs root = the lane's SAID.docs-root: key.
# Runs the SAID.commands: line from the lane root ("none" = a declared skip), then every
# <docs-root>/evaluation/**/harness.sh (symlinks inside the tree are not followed) from its own directory,
# reached through the logical lane path, each under a timeout (a timeout is an undeclared failure).
# A failing harness counts as EXPECTED only when every line-leading FAIL names an id declared for that unit
# in <docs-root>/evaluation/EXPECTED-FAIL -- one "<unit-path> <id> <reason> [until <version>]" per line,
# exact token match, a line past its version counts as undeclared. Nothing is inferred from wording.
# Prints one "gate-recompute: <unit-path> exit=<n> <PASS|EXPECTED|FAIL> [ids]" row per harness.
# Exit 0 iff the command line passes and no harness fails undeclared; 2 = a missing lane key; 3 = a nested run
# of the same lane (a harness that recomputes another lane, e.g. a fixture, is allowed).
# "until" compares with the lane's own plugin version (its validate target, else <lane>/.claude-plugin).
# Env: SAID_ROOT (lane root), SAID_PLUGIN_ROOT (this plugin),
#      SAID_RECOMPUTE_TIMEOUT (seconds per harness, default 120)
lane_root="$(cd "${SAID_ROOT:-$PWD}" 2>/dev/null && pwd -P)"
case ":${SAID_GATE_RECOMPUTE_ACTIVE:-}:" in
  *":$lane_root:"*)
    echo "gate-recompute: refused -- nested run (a harness re-entered the recompute of the same lane)"
    exit 3 ;;
esac
export SAID_GATE_RECOMPUTE_ACTIVE="${SAID_GATE_RECOMPUTE_ACTIVE:+$SAID_GATE_RECOMPUTE_ACTIVE:}$lane_root"
here="$(cd "$(dirname "$0")" && pwd)"
exec python3 - "${SAID_ROOT:-$PWD}" "${SAID_PLUGIN_ROOT:-$here/../..}" "${SAID_RECOMPUTE_TIMEOUT:-120}" <<'PY'
import json, os, re, signal, subprocess, sys

root, plugin_root, timeout = sys.argv[1], sys.argv[2], int(sys.argv[3])
ID = re.compile(r"^[A-Za-z][A-Za-z0-9._-]*$")


def key(text, name):
    m = re.search(r"^[-*\s]*SAID\.%s:[ \t]*(\S.*?)\s*$" % re.escape(name), text, re.M)
    return m.group(1) if m else None


def vtuple(v):
    return tuple(int(x) for x in re.findall(r"\d+", v.split("-")[0])[:3])


try:
    lane = open(os.path.join(root, "CLAUDE.md")).read()
except OSError:
    print("gate-recompute: halt -- no CLAUDE.md at the lane root %s" % root)
    sys.exit(2)
docs_root, commands = key(lane, "docs-root"), key(lane, "commands")
for name, val in (("SAID.docs-root:", docs_root), ("SAID.commands:", commands)):
    if val is None:
        print("gate-recompute: halt -- the lane declares no %s key (declare it in the ## Lane block)" % name)
        sys.exit(2)
def version_of(d):
    try:
        return json.load(open(os.path.join(d, ".claude-plugin", "plugin.json")))["version"]
    except (OSError, ValueError, KeyError, TypeError):
        return None


# "until" compares with the LANE's own plugin version: each plugin its SAID.commands validates, else the
# lane root's own .claude-plugin/plugin.json; a unit nested under a plugin's name uses that plugin's version.
lane_versions = {}
for target in re.findall(r"claude plugin validate\s+(\S+)", commands):
    v = version_of(os.path.join(root, target))
    if v:
        lane_versions[os.path.basename(os.path.normpath(target))] = v
root_version = version_of(root)


def lane_version(unit):
    for seg in unit.split("/")[1:-1]:  # a unit nested under a validated plugin's name (any depth)
        if seg in lane_versions:
            return lane_versions[seg]
    if len(set(lane_versions.values())) == 1:
        return next(iter(lane_versions.values()))
    return root_version  # None when unknown: an "until" then cannot expire (stated in EXPECTED-FAIL's grammar)

fail = 0
if commands.strip() == "none":
    print("gate-recompute: commands skip (SAID.commands: none)")
else:
    rc = subprocess.run(commands, shell=True, cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode
    print("gate-recompute: commands exit=%d %s" % (rc, "PASS" if rc == 0 else "FAIL"))
    fail |= rc != 0

docs = os.path.join(root, docs_root.strip("/"))
evaluation = os.path.join(docs, "evaluation")
declared = {}  # unit -> {id: until}
try:
    for line in open(os.path.join(evaluation, "EXPECTED-FAIL")):
        parts = line.split()
        if len(parts) < 3 or line.lstrip().startswith("#") or "/" not in parts[0]:
            continue  # a bare id with no unit path is not a declaration
        until = None
        if parts[-1] == "until":
            until = "0"  # a dangling "until" with no version: malformed -> treated as expired (undeclared)
        elif len(parts) >= 5 and parts[-2] == "until":
            until = parts[-1]  # only the trailing "until <version>" pair counts; "until" in the reason is prose
        declared.setdefault(parts[0].rstrip("/"), {})[parts[1]] = until
except OSError:
    pass

units = []
for d, dirs, files in os.walk(evaluation, followlinks=False):
    dirs.sort()
    if "harness.sh" in files:
        units.append(d)
for d in sorted(units):
    unit = os.path.relpath(d, docs)
    env = dict(os.environ, PWD=d)  # keep the logical path: harnesses resolve their root from it
    try:
        p = subprocess.Popen(["bash", "./harness.sh"], cwd=d, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, start_new_session=True)
        out, _ = p.communicate(timeout=timeout)
        rc = p.returncode
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGKILL)
        p.communicate()
        print("gate-recompute: %s exit=124 FAIL timeout-%ds" % (unit, timeout))
        fail = 1
        continue
    text = out.decode("utf-8", "replace")
    ids = [m.group(1) for m in re.finditer(r"^\s*FAIL\s+(\S+)", text, re.M)]
    ver = lane_version(unit)
    ok_decl = {i: u for i, u in declared.get(unit, {}).items() if u is None or ver is None or vtuple(ver) < vtuple(u)}
    if rc == 0:
        print("gate-recompute: %s exit=0 PASS" % unit)
        for i in sorted(declared.get(unit, {})):
            print("gate-recompute: %s exit=0 PASS stale-declaration %s" % (unit, i))
        continue
    if ids and all(ID.match(i) and i in ok_decl for i in ids):
        print("gate-recompute: %s exit=%d EXPECTED %s" % (unit, rc, " ".join(ids)))
    else:
        print("gate-recompute: %s exit=%d FAIL %s" % (unit, rc, " ".join(ids) or "no-fail-id"))
        fail = 1
sys.exit(1 if fail else 0)
PY
