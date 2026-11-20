#!/usr/bin/env python3
"""The feature-level Inspect in one command, outside the driving session: the cold read, the gate recompute, the
Covers read, the round and the sign-off, every write through the bundled scripts.

  inspect_run.py <feature-id> --root <lane-root> [--base <rev>] [--capture-ref <file>] [--ledger <file>]...
                 [--yes <token>]

Steps, in order, one run per lane at a time (a second run while one holds the lane is refused; the lock is a file in
the lane's git dir, never in the tree). A --ledger, a SAID path key outside the lane root, a missing ledger, spec or
task log is an error before any estimate:
  1. The feature-review read, when the record reads it owed: the feature-reviewer agent runs headless (`claude -p`,
     or $SAID_CLAUDE_BIN), its reply is filed as <working>/review-feature-<id>.md (review-doc-editorial-<id>.md on a
     doc lane) and gate_record_row.py --kind feature-review validates it and writes its rows. A read spends model
     tokens: without --yes the runner prints the estimate and its yes token and runs no read; --yes runs it only when
     the token is the one the current estimate prints (it covers HEAD, the base and the uncommitted changes). --base (the feature's base commit) and --capture-ref (a
     non-empty capture file in the working dir) are needed for the read. A reply with no verdict line is not filed.
  2. gate_recompute.sh over every unit (SAID_GATE_UNITS is never passed), writing the record.
  3. covers-read.py over the task log, its output in <working>/covers-<id>.txt (--ledger names the decision ledgers).
  4. gate_record.py round from that output, then check over every read; the report of the record is printed.
Exit 0 the record is current on every read, 1 something is owed, 2 an input or step error (`error: <why>`),
3 refused: another run holds the lane.
"""
import fcntl
import hashlib
import os
import re
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gate_record  # noqa: E402  the one reader and writer of the record

AGENT = "said:feature-reviewer"
TOOLS = "Read,Grep,Glob,Bash(git diff:*),Bash(git log:*),Bash(git show:*),Bash(git status:*)"


class Halt(Exception):
    pass


def parse(argv):
    if not argv or argv[0].startswith("-"):
        raise Halt("usage: inspect_run.py <feature-id> --root <lane-root> [--base <rev>] [--capture-ref <file>]"
                   " [--ledger <file>]... [--yes <token>]")
    m = re.fullmatch(r"([A-Za-z]+-[0-9]+)((?:-[A-Za-z0-9]+)*)", argv[0])
    if not m:
        raise Halt("not a feature id: %s" % argv[0])
    fid, opts, ledgers, i = m.group(1).upper() + m.group(2), {}, [], 1  # the prefix uppercased, a slug kept as given
    while i < len(argv):
        k = argv[i]
        if i + 1 >= len(argv) or k not in ("--root", "--base", "--capture-ref", "--ledger", "--yes"):
            raise Halt("unknown or incomplete option %s" % k)
        if k == "--ledger":
            ledgers.append(argv[i + 1])
        else:
            opts[k[2:]] = argv[i + 1]
        i += 2
    if "root" not in opts or not os.path.isdir(opts["root"]):
        raise Halt("--root names no directory")
    opts["root"] = os.path.realpath(os.path.abspath(opts["root"]))
    opts["ledgers"] = [inside(opts["root"], os.path.join(opts["root"], p), "--ledger " + p) for p in ledgers]
    for p, given in zip(opts["ledgers"], ledgers):
        if not os.path.isfile(p):
            raise Halt("--ledger %s is not a file" % given)
    return fid, opts


def inside(root, path, what):
    """The path, normalized; a Halt when it is outside the lane root."""
    full = os.path.normpath(path)
    if full != root and not full.startswith(root.rstrip(os.sep) + os.sep):
        raise Halt("%s is outside the lane root" % what)
    return full


def lane_path(root, key, fid):
    value = (gate_record.lane_key(root, key) or "").strip().strip("`'\"")
    if not value:
        raise Halt("the lane declares no SAID.%s: key" % key)
    return inside(root, os.path.join(root, value.replace("<id>", fid)), "SAID.%s: %s" % (key, value))


def lock(root):
    """The lane's run lock, held until this process exits; None when another run holds it. It lives in the lane's git
    dir (never in the tree, so the store is not touched); a lane outside git uses the temp dir."""
    name = "said-inspect-%s.lock" % hashlib.sha256(root.encode("utf-8")).hexdigest()[:16]
    where = (git(root, "rev-parse", "--absolute-git-dir") or "").strip() or tempfile.gettempdir()
    fh = open(os.path.join(where, name), "a")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fh.close()
        return None
    return fh


def git(root, *args):
    r = subprocess.run(["git", "-C", root] + list(args), capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def size(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return len(fh.read())
    except OSError:
        return 0


def decisions(root, working, spec_ledgers):
    out = [os.path.join(working, "rulings.md"), os.path.join(working, "scope.md")]
    return [p for p in out if os.path.isfile(p)] + spec_ledgers


def estimate(root, base, head, records, spec):
    """(characters, tokens) of what the reader reads once: the diff, every file it touches at HEAD, the spec, the
    decision records, the task log and the lane's CLAUDE.md."""
    diff = git(root, "diff", "%s..%s" % (base, head)) or ""
    touched = [p for p in (git(root, "diff", "-z", "--name-only", "%s..%s" % (base, head)) or "").split("\0") if p]
    chars = len(diff) + sum(size(os.path.join(root, p)) for p in touched)
    chars += sum(size(p) for p in [spec, os.path.join(root, "CLAUDE.md")] + records)
    return chars, chars // 4


def brief(fid, root, working, base, head, ref, records, doc):
    lines = ["feature id: %s" % fid, "lane root: %s" % root, "working dir: %s" % working, "base commit: %s" % base,
             "target commit: %s" % head, "capture reference: %s" % ref]
    lines += ["decision record: %s" % p for p in records]
    if doc:
        lines.append("surface: doc")
    lines += ["", "Read the feature's sources against its build as your instructions say and return the verdict only."]
    return "\n".join(lines) + "\n"


def feature_review(fid, opts, root, working, record):
    """Run the read when it is owed and the yes matches; print what was done. Never raises on a reader failure."""
    code, line = gate_record.check(root, record, ["feature-review"])
    if line == "current" or line == "Inspect owed: feature-review FAIL":
        print("feature-review: %s" % ("current" if line == "current" else "verdict FAIL, not read again"))
        return
    base, ref = opts.get("base"), opts.get("capture-ref")
    if not base:
        print("feature-review: owed (no read: --base <rev> names the feature's base commit)")
        return
    head = (git(root, "rev-parse", "HEAD") or "").strip()
    base_sha = (git(root, "rev-parse", "--verify", base + "^{commit}") or "").strip()
    if not head or not base_sha:
        print("feature-review: owed (no read: the lane has no HEAD or --base %s is no commit)" % base)
        return
    full_ref = os.path.realpath(os.path.join(working, ref)) if ref else ""
    if not ref or not full_ref.startswith(os.path.realpath(working) + os.sep) or size(full_ref) == 0:
        print("feature-review: owed (no read: --capture-ref names no non-empty file in the working dir)")
        return
    records = decisions(root, working, opts["ledgers"])
    spec = lane_path(root, "feature-spec", fid)
    if not os.path.isfile(spec) or not os.path.isfile(lane_path(root, "task-log", fid)):
        raise Halt("the feature has no spec or no task log (%s)" % os.path.relpath(spec, root))
    chars, tokens = estimate(root, base_sha, head, records, spec)
    dirty = hashlib.sha256((git(root, "status", "--porcelain", "-z") or "").encode("utf-8")).hexdigest()
    token = hashlib.sha256(("%s|%s|%s|%s|%d" % (root, head, base_sha, dirty, tokens)).encode("utf-8")).hexdigest()[:10]
    print("estimate: at least %d input tokens (%d characters read once, divided by 4); every reader turn re-sends"
          " what it has read, so the spend is several times that" % (tokens, chars))
    print("yes token: %s" % token)
    if "yes" not in opts:
        print("feature-review: owed (no read without a yes: rerun with --yes %s to spend)" % token)
        return
    if opts["yes"] != token:
        print("feature-review: refused, --yes is not the token of this estimate (%s); no read" % token)
        return
    doc = gate_record.fr_doc_lane(root)
    out_name = "review-%s-%s.md" % ("doc-editorial" if doc else "feature", fid)
    cmd = [os.environ.get("SAID_CLAUDE_BIN") or "claude", "-p", "--agent", AGENT, "--allowedTools", TOOLS,
           "--output-format", "text"]
    try:
        r = subprocess.run(cmd, input=brief(fid, root, working, base_sha, head, ref, records, doc), capture_output=True,
                           text=True, cwd=root, timeout=3600)
        reply = r.stdout if r.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired) as e:
        reply = ""
        print("feature-review: the read did not run (%s)" % e.__class__.__name__)
    if not re.search(r"^verdict: (PASS|FAIL)\s*$", reply, re.M):
        print("feature-review: owed (the read returned no verdict line; nothing filed)")
        return
    with open(os.path.join(working, out_name), "w", encoding="utf-8") as fh:
        fh.write(reply)
    row = subprocess.run([sys.executable, os.path.join(HERE, "gate_record_row.py"), "--kind", "feature-review", "--root",
                          root, "--out", record, "--workdir", working, "--feature", fid]
                         + (["--decisions"] + records if records else []), capture_output=True, text=True)
    print("feature-review: %s" % (row.stdout.strip().split("\n")[0] if row.stdout.strip() else "exit %d" % row.returncode))


def main(argv):
    try:
        fid, opts = parse(argv)
        root = opts["root"]
        working = lane_path(root, "working", fid)
        tasks = lane_path(root, "task-log", fid)
        record = os.path.join(working, "gate-%s.md" % fid)
    except (Halt, gate_record.Error) as e:
        print("error: %s" % e)
        return 2
    held = lock(root)
    if held is None:
        print("refused: another inspect run holds this lane; one gate run at a time")
        return 3
    try:
        os.makedirs(working, exist_ok=True)
        feature_review(fid, opts, root, working, record)
        env = {k: v for k, v in os.environ.items() if k not in ("SAID_GATE_UNITS",)}
        env.update(SAID_ROOT=root, SAID_GATE_OUT=record)
        g = subprocess.run(["bash", os.path.join(HERE, "gate_recompute.sh")], capture_output=True, text=True, env=env)
        if g.returncode > 1:
            raise Halt("gate_recompute.sh exit %d: %s" % (g.returncode, (g.stdout.strip().split("\n") or [""])[-1]))
        print("gate-recompute: exit %d, %d row(s)" % (g.returncode, g.stdout.count("gate-recompute: ")))
        covers = [sys.executable, os.path.join(HERE, "..", "review-qa", "covers-read.py"), "--task-file", tasks,
                  "--root", root, "--working", working, "--rulings", os.path.join(working, "rulings.md")]
        docs = (gate_record.lane_key(root, "docs-root") or "docs/").strip().strip("`'\"")
        for flag, name in (("--todo", "todo.md"), ("--backlog", "backlog.md")):
            if os.path.isfile(os.path.join(root, docs, name)):
                covers += [flag, os.path.join(root, docs, name)]
        for p in opts["ledgers"]:
            covers += ["--ledger", p]
        c = subprocess.run(covers, capture_output=True, text=True)
        if c.returncode == 2:
            raise Halt("covers-read.py: %s" % c.stdout.strip()[-300:])
        cov = os.path.join(working, "covers-%s.txt" % fid)
        with open(cov, "w", encoding="utf-8") as fh:
            fh.write(c.stdout)
        gate_record.do_round(root, record, cov, [])
        rep = gate_record.report(root, record)
        print("\n".join(gate_record.report_text(rep, root)))
        code, line = gate_record.check(root, record, list(gate_record.READS))
        print(line)
        return 0 if code == 0 and not rep["owed"] else 1
    except gate_record.Refused as e:
        print("error: round refused: %s" % e)
        return 2
    except (Halt, gate_record.Error, OSError) as e:
        print("error: %s" % e)
        return 2
    finally:
        held.close()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
