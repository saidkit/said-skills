#!/usr/bin/env python3
"""The feature-reviewer's read of one feature: the code `/said:review-feature` runs in the session and
board/inspect_run.py runs outside it, so the two forms build one brief and file one way.

  review_feature.py prepare <feature-id> --root <lane-root> [--base <rev>] [--capture-ref <file>] [--ledger <file>]...
  review_feature.py file <feature-id> --root <lane-root> --reply <file> [--ledger <file>]...

prepare reads the record (`gate_record.py check --reads feature-review`) and prints one first line:
  review-feature: current                  the record holds the read's rows at this store; nothing to read
  review-feature: FAIL recorded            the recorded verdict is FAIL; it is not read again
  review-feature: owed (no read: <why>)    the read is owed and cannot run (no --base, no HEAD, no capture file)
  review-feature: ready                    then `out: <verdict file>`, `estimate: ...` and the brief between the
                                           lines `--- brief` and `--- end`
Exit 0 ready, 1 any other state, 2 an input error (`error: <why>`). The capture reference is a non-empty file in the
working dir, named relative to it; the decision records are the working dir's rulings.md and scope.md when they exist,
then each --ledger (a file inside the lane root).

file runs gate_record_row.py --kind feature-review with the same decision records over a reply that carries a
`verdict: PASS` or `verdict: FAIL` line, and files it only when the writer accepts it, as
<working>/review-feature-<id>.md (review-doc-editorial-<id>.md on a lane whose SAID.surface: is doc, never both); it
prints the writer's lines. A reply with no verdict line is not filed. Exit 0 the rows are written, 1 owed (no verdict line, or the writer refused
and wrote nothing), 2 an error. Pass file the --ledger files prepare was given.
"""
import os
import re
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = os.path.join(HERE, "..", "board")
sys.path.insert(0, BOARD)
import gate_record  # noqa: E402  the one reader and writer of the record

AGENT = "said:feature-reviewer"
VERDICT = re.compile(r"^verdict: (PASS|FAIL)\s*$", re.M)


class Error(Exception):
    pass


def feature_id(text):
    """The feature id with its prefix uppercased and a slug kept as given; an Error when it is not one."""
    m = re.fullmatch(r"([A-Za-z]+-[0-9]+)((?:-[A-Za-z0-9]+)*)", text or "")
    if not m:
        raise Error("not a feature id: %s" % text)
    return m.group(1).upper() + m.group(2)


def lane_root(path):
    if not path or not os.path.isdir(path):
        raise Error("--root names no directory")
    return os.path.realpath(os.path.abspath(path))


def inside(root, path, what):
    """The path, normalized; an Error when it is outside the lane root."""
    full = os.path.normpath(path)
    if full != root and not full.startswith(root.rstrip(os.sep) + os.sep):
        raise Error("%s is outside the lane root" % what)
    return full


def lane_path(root, key, fid):
    value = (gate_record.lane_key(root, key) or "").strip().strip("`'\"")
    if not value:
        raise Error("the lane declares no SAID.%s: key" % key)
    return inside(root, os.path.join(root, value.replace("<id>", fid)), "SAID.%s: %s" % (key, value))


def ledgers(root, given):
    """Each --ledger as a full path inside the lane root; an Error on one outside it or not a file."""
    out = [inside(root, os.path.join(root, p), "--ledger " + p) for p in given]
    for p, g in zip(out, given):
        if not os.path.isfile(p):
            raise Error("--ledger %s is not a file" % g)
    return out


def git(root, *args):
    r = subprocess.run(["git", "-C", root] + list(args), capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def size(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return len(fh.read())
    except OSError:
        return 0


def decisions(working, spec_ledgers):
    out = [os.path.join(working, "rulings.md"), os.path.join(working, "scope.md")]
    return [p for p in out if os.path.isfile(p)] + list(spec_ledgers)


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


def out_path(root, working, fid):
    doc = gate_record.fr_doc_lane(root)
    return os.path.join(working, "review-%s-%s.md" % ("doc-editorial" if doc else "feature", fid)), doc


def prepare(fid, root, base, ref, spec_ledgers):
    """{state: current | FAIL | owed | ready, why, ...}; on ready also base, head, records, out, doc, brief, chars,
    tokens. An Error when the lane's keys, the spec or the task log are missing."""
    working = lane_path(root, "working", fid)
    record = os.path.join(working, "gate-%s.md" % fid)
    code, line = gate_record.check(root, record, ["feature-review"])
    if line == "current":
        return {"state": "current", "why": "current"}
    if line == "Inspect owed: feature-review FAIL":
        return {"state": "FAIL", "why": "verdict FAIL, not read again"}
    if not base:
        return {"state": "owed", "why": "no read: --base <rev> names the feature's base commit"}
    head = (git(root, "rev-parse", "HEAD") or "").strip()
    base_sha = (git(root, "rev-parse", "--verify", base + "^{commit}") or "").strip()
    if not head or not base_sha:
        return {"state": "owed", "why": "no read: the lane has no HEAD or --base %s is no commit" % base}
    full_ref = os.path.realpath(os.path.join(working, ref)) if ref else ""
    if not ref or not full_ref.startswith(os.path.realpath(working) + os.sep) or size(full_ref) == 0:
        return {"state": "owed", "why": "no read: --capture-ref names no non-empty file in the working dir"}
    records = decisions(working, spec_ledgers)
    spec = lane_path(root, "feature-spec", fid)
    if not os.path.isfile(spec) or not os.path.isfile(lane_path(root, "task-log", fid)):
        raise Error("the feature has no spec or no task log (%s)" % os.path.relpath(spec, root))
    chars, tokens = estimate(root, base_sha, head, records, spec)
    out, doc = out_path(root, working, fid)
    return {"state": "ready", "why": "ready", "base": base_sha, "head": head, "records": records, "out": out,
            "doc": doc, "chars": chars, "tokens": tokens,
            "brief": brief(fid, root, working, base_sha, head, ref, records, doc)}


def file_reply(fid, root, reply, spec_ledgers):
    """(code, lines): file the reply when it carries a verdict line and the row writer accepts it, then its rows are
    written through gate_record_row.py. Code 0 written, 1 owed (nothing filed, or the writer refused), 2 a writer
    error. The writer reads the reply at the verdict path, so it is put there for the writer's run only: on a refusal
    or an error it is taken away and an earlier file at that path is put back."""
    working = lane_path(root, "working", fid)
    if not VERDICT.search(reply or ""):
        return 1, ["owed (the read returned no verdict line; nothing filed)"]
    out, _ = out_path(root, working, fid)
    os.makedirs(working, exist_ok=True)
    prev = None
    if os.path.lexists(out):
        prev = "%s.%d.prev" % (out, os.getpid())  # beside it: one rename back, the working dir is not dirt to the writer
        os.replace(out, prev)
    rc = 2
    try:
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(reply)
        records = decisions(working, spec_ledgers)
        row = subprocess.run([sys.executable, os.path.join(BOARD, "gate_record_row.py"), "--kind", "feature-review",
                              "--root", root, "--out", os.path.join(working, "gate-%s.md" % fid), "--workdir", working,
                              "--feature", fid] + (["--decisions"] + records if records else []),
                             capture_output=True, text=True)
        rc = row.returncode
    finally:
        if rc != 0 and prev:
            os.replace(prev, out)  # the earlier file back over the refused reply, in one step
        elif rc != 0:
            try:
                os.remove(out)
            except FileNotFoundError:
                pass
        elif prev:
            os.remove(prev)
    rc = 0 if rc == 0 else 1 if rc == 1 else 2
    err = [ln for ln in row.stderr.strip().split("\n") if ln][-1:] if rc else []
    lines = [ln for ln in row.stdout.strip().split("\n") if ln] or ["exit %d" % row.returncode]
    lines += ["writer stderr: %s" % e[:200] for e in err]
    head = ("filed %s" % os.path.relpath(out, root) if rc == 0 else
            "not filed (the writer refused the reply)" if rc == 1 else "not filed (the writer failed)")
    return rc, [head] + lines


def keep_refused(fid, reply):
    """The path of a new temp file outside the lane holding a refused reply (the headless read has no scratchpad)."""
    fd, kept = tempfile.mkstemp(prefix="review-feature-refused-%s-" % fid, suffix=".md")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(reply)
    return kept


def parse(argv):
    if len(argv) < 2 or argv[0] not in ("prepare", "file") or argv[1].startswith("-"):
        raise Error("usage: review_feature.py prepare|file <feature-id> --root <lane-root> [--base <rev>]"
                    " [--capture-ref <file>] [--reply <file>] [--ledger <file>]...")
    form, fid, opts, given, i = argv[0], feature_id(argv[1]), {}, [], 2
    allowed = ("--root", "--base", "--capture-ref", "--ledger") if form == "prepare" else ("--root", "--reply", "--ledger")
    while i < len(argv):
        k = argv[i]
        if i + 1 >= len(argv) or k not in allowed:
            raise Error("unknown or incomplete option %s" % k)
        if k == "--ledger":
            given.append(argv[i + 1])
        else:
            opts[k[2:]] = argv[i + 1]
        i += 2
    root = lane_root(opts.get("root"))
    if form == "file" and not os.path.isfile(opts.get("reply") or ""):
        raise Error("--reply names no file")
    return form, fid, root, opts, ledgers(root, given)


def main(argv):
    try:
        form, fid, root, opts, spec_ledgers = parse(argv)
        if form == "prepare":
            p = prepare(fid, root, opts.get("base"), opts.get("capture-ref"), spec_ledgers)
            if p["state"] != "ready":
                print("review-feature: %s" % {"current": "current", "FAIL": "FAIL recorded (not read again)"}.get(
                    p["state"], "owed (%s)" % p["why"]))
                return 1
            print("review-feature: ready\nout: %s" % p["out"])
            print("estimate: at least %d input tokens (%d characters read once, divided by 4)" % (p["tokens"], p["chars"]))
            print("--- brief\n%s--- end" % p["brief"])
            return 0
        with open(opts["reply"], encoding="utf-8", errors="replace") as fh:
            code, lines = file_reply(fid, root, fh.read(), spec_ledgers)
        print("review-feature: %s" % lines[0])
        for ln in lines[1:]:
            print(ln)
        return code
    except (Error, gate_record.Error, OSError) as e:
        print("error: %s" % e)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
