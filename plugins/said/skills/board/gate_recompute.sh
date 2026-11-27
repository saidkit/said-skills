#!/usr/bin/env bash
# Deterministic recompute for a lane's cli gate: the lane's own command line, then every evaluation harness.
# Lane root = $SAID_ROOT (default: the current dir); docs root = the lane's SAID.docs-root: key.
# Runs the SAID.commands: line from the lane root ("none" = a declared skip), then every
# <docs-root>/evaluation/**/harness.sh (symlinks inside the tree are not followed; the walk does not descend
# below a folder under evaluation/ that holds a harness.sh: that unit's subtree is its data) from its own directory,
# reached through the logical lane path, each under a timeout (a timeout is an undeclared failure).
# A unittest unit -- a folder with __init__.py and test_*.py files, no harness.sh, not below another unit -- is
# not run alone: every such unit runs in one python3 interpreter (each discovered from its folder with the
# evaluation folder as top level, so its load_tests applies), under REQUIRE_BROWSER=1, with a timeout of the
# per-harness seconds times the number of such units. Its row is PASS, EXPECTED with the ids of its expected
# failures, or FAIL with the ids of its failing tests (an unexpected success fails); an id is the test's
# check_id attribute, else its unittest id (a failing subTest fails its test). Results are kept after each unit:
# the unit that crashes the interpreter is FAIL no-result (timeout-Ns when it hangs), the units after it
# FAIL not-run. EXPECTED-FAIL applies to harness.sh units only.
# A failing harness counts as EXPECTED only when every line-leading FAIL names an id declared for that unit
# in <docs-root>/evaluation/EXPECTED-FAIL -- one "<unit-path> <id> <reason> [until <version>]" per line,
# exact token match, a line past its version counts as undeclared. Nothing is inferred from wording.
# Prints one "gate-recompute: <unit-path> exit=<n> <PASS|EXPECTED|FAIL> [ids]" row per harness.
# Exit 0 iff the command line passes and no harness fails undeclared; 2 = a missing lane key, or the record
# could not be written (`error: <why>`); 3 = a nested run
# of the same lane (a harness that recomputes another lane, e.g. a fixture, is allowed).
# "until" compares with the lane's own plugin version (its validate target, else <lane>/.claude-plugin).
# SAID_GATE_OUT=<file>: also write the run's record there through gate_record.py -- the store identity of the
# physical lane root, then every row above, in print order; written at exit (a halt or a kill leaves no record);
# unset, nothing is written and stdout is unchanged. The other rows of the current store (a reviewer's
# `skill-doctor:` rows from gate_record_row.py, `feature-review:` rows) survive a rerun at the same store and are
# dropped at a moved one; the round and matrix lines are always kept; the gate-recompute rows are replaced whole.
# Env: SAID_ROOT (lane root), SAID_PLUGIN_ROOT (this plugin),
#      SAID_RECOMPUTE_TIMEOUT (seconds per harness, default 120), SAID_GATE_OUT (record file, optional)
#      Every unit run gets LANE_ROOT = the physical lane root, replacing any value the caller held.
#      SAID_GATE_UNITS (optional): the unit paths to run, relative to the lane root, separated by spaces or
#      newlines; every other unit prints `gate-recompute: <unit-path> skipped (not selected)` and is not run.
#      Unset runs every unit; a name that is no unit is a halt (exit 2). A skipped row is not a pass: a record
#      holding one is not a full-run record.
#      An entry may be `<unit-path>:<slice>,<slice>` for a unit that declares SLICES in its __init__.py: only those
#      slices run (a bare entry is the whole unit), the unit's row reads `<unit-path>:<slices> exit=...` and each
#      left-out slice prints `<unit-path>:<slice> skipped (not selected)`. An undeclared slice is a halt (exit 2).
lane_root="$(cd "${SAID_ROOT:-$PWD}" 2>/dev/null && pwd -P)"
case ":${SAID_GATE_RECOMPUTE_ACTIVE:-}:" in
  *":$lane_root:"*)
    echo "gate-recompute: refused -- nested run (a harness re-entered the recompute of the same lane)"
    exit 3 ;;
esac
export SAID_GATE_RECOMPUTE_ACTIVE="${SAID_GATE_RECOMPUTE_ACTIVE:+$SAID_GATE_RECOMPUTE_ACTIVE:}$lane_root"
here="$(cd "$(dirname "$0")" && pwd)"
exec python3 - "${SAID_ROOT:-$PWD}" "${SAID_PLUGIN_ROOT:-$here/../..}" "${SAID_RECOMPUTE_TIMEOUT:-120}" <<'PY'
import ast, json, os, re, signal, subprocess, sys

root, plugin_root, timeout = os.path.abspath(sys.argv[1]), sys.argv[2], int(sys.argv[3])  # relative SAID_ROOT
ID = re.compile(r"^[A-Za-z][A-Za-z0-9._-]*$")
rows = []  # every row printed, for the record


def row(text):
    print(text)
    rows.append(text)


def write_record(path):
    # the record is the script's, never a session's: the store identity of the physical root, then the rows
    board = os.path.join(os.path.realpath(plugin_root), "skills", "board")
    if not os.path.isfile(os.path.join(board, "gate_record.py")):
        print("error: no gate_record.py under %s (SAID_PLUGIN_ROOT names another plugin copy)" % board)
        sys.exit(2)
    sys.path.insert(0, board)
    sys.dont_write_bytecode = True
    import gate_record

    def mutate(store, kept, history):  # another store's rows are already dropped; history always kept
        return rows + [l for l in kept if not l.startswith("gate-recompute: ")], history

    try:
        gate_record.update(path, os.path.realpath(root), mutate)
    except (gate_record.Error, OSError) as e:
        print("error: the record was not written: %s" % e)
        sys.exit(2)


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
    row("gate-recompute: commands skip (SAID.commands: none)")
else:
    rc = subprocess.run(commands, shell=True, cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode
    row("gate-recompute: commands exit=%d %s" % (rc, "PASS" if rc == 0 else "FAIL"))
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

units, test_units = [], []
for d, dirs, files in os.walk(evaluation, followlinks=False):
    dirs.sort()
    if "harness.sh" in files:
        units.append(d)
        if d != evaluation:
            dirs[:] = []  # a unit's subtree is its data, never a unit of its own
    elif d != evaluation and "__init__.py" in files and any(f.startswith("test_") and f.endswith(".py") for f in files):
        test_units.append(d)  # unittest unit, run with the others in one interpreter
        dirs[:] = []

entries = [e.rstrip("/") for e in os.environ.get("SAID_GATE_UNITS", "").split()]  # empty: every unit runs
selected = []  # unit names as typed
wanted = {}  # unit dir -> the slices asked for (None: the whole unit, a bare entry wins over a sliced one)


def spellings(d):
    return (os.path.relpath(d, root), os.path.relpath(d, docs))  # lane-root and docs-root relative


for e in entries:
    name, sep, sl = e.partition(":")
    selected.append(name)
    for d in units + test_units:
        if name in spellings(d):
            if not sep:
                wanted[d] = None
            elif wanted.get(d, []) is not None:
                wanted[d] = wanted.get(d, []) + [x for x in sl.split(",") if x] + ([] if sl else [""])


def chosen(d):
    """True when the unit at d runs: no selection, or its path (lane-root or docs-root relative) is named."""
    return not selected or d in wanted


def declared_slices(d):
    """The slice names a unit declares as SLICES in its __init__.py, in order; [] when it declares none."""
    try:
        with open(os.path.join(d, "__init__.py"), encoding="utf-8") as f:
            tree = ast.parse(f.read())
    except (OSError, SyntaxError, ValueError):
        return []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "SLICES" for t in node.targets):
            try:
                return [str(k) for k in ast.literal_eval(node.value)]
            except (ValueError, TypeError):
                return []
    return []


unknown = [n for n in selected if not any(n in spellings(d) for d in units + test_units)]
if unknown:
    print("gate-recompute: halt -- SAID_GATE_UNITS names no unit: %s" % " ".join(unknown))
    sys.exit(2)
badslice = []
ran_slices = {}  # unit dir -> the slices to run, in the unit's declared order
for d in test_units + units:
    if wanted.get(d) is None:
        continue
    have = declared_slices(d) if d in test_units else []
    miss = [x for x in wanted[d] if x not in have]
    if miss:
        badslice.append("%s:%s" % (os.path.relpath(d, docs), ",".join(x or "(none)" for x in miss)))
    else:
        ran_slices[d] = [x for x in have if x in wanted[d]]
if badslice:
    print("gate-recompute: halt -- SAID_GATE_UNITS names no slice: %s" % " ".join(badslice))
    sys.exit(2)


def label(d):
    """A unit's row name: its docs-relative path, with the slices that ran when it was sliced."""
    return os.path.relpath(d, docs) + (":" + ",".join(ran_slices[d]) if d in ran_slices else "")


run_units = [d for d in test_units if chosen(d)]
RUNNER = r'''
import json, os, sys, unittest
ev, out, units = sys.argv[1], sys.argv[2], sys.argv[3:]


def cid(t):
    m = getattr(t, getattr(t, "_testMethodName", ""), None)
    return getattr(m, "check_id", None) or "".join(str(t.id()).split())  # one token per id on the row


class Result(unittest.TestResult):
    def __init__(self):
        super().__init__()
        self.rows = {}

    def put(self, kind, test):
        self.rows.setdefault(self.unit, {"FAIL": [], "EXPECTED": []})[kind].append(cid(test))

    def addError(self, test, err):
        super().addError(test, err)
        self.put("FAIL", test)

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.put("FAIL", test)

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self.put("FAIL", test)

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err)
        self.put("EXPECTED", test)

    def addSubTest(self, test, subtest, err):  # a failing subTest never reaches addFailure
        super().addSubTest(test, subtest, err)
        if err is not None and cid(test) not in self.rows[self.unit]["FAIL"]:
            self.put("FAIL", test)


def save(running):  # after each unit, so a crash or a kill keeps the finished units' rows
    with open(out + ".tmp", "w") as f:
        json.dump({"rows": r.rows, "running": running}, f)
    os.replace(out + ".tmp", out)


r = Result()
for arg in units:
    u, _, only = arg.partition("\x1f")  # a sliced unit: its path, then the slices to run
    if only:
        os.environ["HARNESS_ONLY"] = only
    else:
        os.environ.pop("HARNESS_ONLY", None)
    save(u)  # u has no row yet: a crash inside it leaves it unfinished
    r.unit = u
    r.rows[u] = {"FAIL": [], "EXPECTED": []}
    try:
        unittest.defaultTestLoader.discover(u, top_level_dir=ev).run(r)
    except BaseException as e:  # a unit that cannot be discovered or run fails as a whole
        r.rows[u]["FAIL"].append("unit:" + type(e).__name__)
save(None)
'''

test_rows = {}
if run_units:
    import tempfile
    fd, res = tempfile.mkstemp(prefix="gate-recompute-")
    os.close(fd)
    env = {k: v for k, v in os.environ.items() if k not in ("SAID_GATE_OUT", "SAID_GATE_UNITS", "HARNESS_ONLY", "UPDATE_GOLDENS")}
    env["REQUIRE_BROWSER"] = "1"  # a gate with no browser fails the browser checks, never skips them
    env["LANE_ROOT"] = os.path.realpath(root)  # the physical lane root, whatever the caller held
    budget = timeout * len(run_units)
    p = subprocess.Popen([sys.executable, "-I", "-B", "-c", RUNNER, evaluation, res] + [d + ("\x1f" + ",".join(ran_slices[d]) if d in ran_slices else "") for d in run_units], cwd=evaluation, env=env,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
    timed_out = False
    try:
        p.wait(timeout=budget)
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGKILL)
        p.wait()
        timed_out = True
    try:
        saved = json.load(open(res))
        got, running = saved["rows"], saved["running"]
    except (OSError, ValueError, KeyError, TypeError):
        got, running = {}, None
    for f in (res, res + ".tmp"):
        if os.path.exists(f):
            os.remove(f)
    for d in run_units:
        unit = label(d)
        if timed_out and (d == running or (running is None and d not in got)):
            test_rows[d] = ("gate-recompute: %s exit=124 FAIL timeout-%ds" % (unit, budget), 1)
        elif d == running or (d not in got and running is None):
            test_rows[d] = ("gate-recompute: %s exit=%d FAIL no-result" % (unit, p.returncode or 1), 1)
        elif d not in got:  # after the unit that crashed or hung
            test_rows[d] = ("gate-recompute: %s exit=1 FAIL not-run" % unit, 1)
        elif got[d]["FAIL"]:
            test_rows[d] = ("gate-recompute: %s exit=1 FAIL %s" % (unit, " ".join(got[d]["FAIL"])), 1)
        elif got[d]["EXPECTED"]:
            test_rows[d] = ("gate-recompute: %s exit=0 EXPECTED %s" % (unit, " ".join(got[d]["EXPECTED"])), 0)
        else:
            test_rows[d] = ("gate-recompute: %s exit=0 PASS" % unit, 0)

for d in sorted(units + test_units):
    unit = label(d)
    if not chosen(d):
        row("gate-recompute: %s skipped (not selected)" % unit)  # neither a pass nor a fail
        continue
    if d in test_rows:
        row(test_rows[d][0])
        fail |= test_rows[d][1]
        for x in declared_slices(d):
            if d in ran_slices and x not in ran_slices[d]:
                row("gate-recompute: %s:%s skipped (not selected)" % (os.path.relpath(d, docs), x))  # a left-out slice
        continue
    env = {k: v for k, v in os.environ.items() if k not in ("SAID_GATE_OUT", "SAID_GATE_UNITS")}  # the record is this run's, never a child's
    env["PWD"] = d  # keep the logical path: harnesses resolve their root from it
    env["LANE_ROOT"] = os.path.realpath(root)  # the physical lane root, whatever the caller held
    try:
        p = subprocess.Popen(["bash", "./harness.sh"], cwd=d, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, start_new_session=True)
        out, _ = p.communicate(timeout=timeout)
        rc = p.returncode
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGKILL)
        p.communicate()
        row("gate-recompute: %s exit=124 FAIL timeout-%ds" % (unit, timeout))
        fail = 1
        continue
    text = out.decode("utf-8", "replace")
    ids = [m.group(1) for m in re.finditer(r"^\s*FAIL\s+(\S+)", text, re.M)]
    ver = lane_version(unit)
    ok_decl = {i: u for i, u in declared.get(unit, {}).items() if u is None or ver is None or vtuple(ver) < vtuple(u)}
    if rc == 0:
        row("gate-recompute: %s exit=0 PASS" % unit)
        for i in sorted(declared.get(unit, {})):
            row("gate-recompute: %s exit=0 PASS stale-declaration %s" % (unit, i))
        continue
    if ids and all(ID.match(i) and i in ok_decl for i in ids):
        row("gate-recompute: %s exit=%d EXPECTED %s" % (unit, rc, " ".join(ids)))
    else:
        row("gate-recompute: %s exit=%d FAIL %s" % (unit, rc, " ".join(ids) or "no-fail-id"))
        fail = 1
gate_out = os.environ.get("SAID_GATE_OUT")
if gate_out:
    write_record(gate_out)
sys.exit(1 if fail else 0)
PY
