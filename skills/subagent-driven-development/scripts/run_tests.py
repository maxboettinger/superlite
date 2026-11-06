#!/usr/bin/env python3
"""Run pytest, parse the junit XML, print one summary line.

    run_tests.py [--fast PATHS... | --full] [--log PATH] [--ledger PATH]
                 [--summary PATH] [--background]
    run_tests.py --record --passed N [--failed N] [--skipped N] [--seconds S] --command CMD   (a full result run outside run_tests; report only, closes no incidents)
    run_tests.py [--timeout S] [--summary PATH] --wait [PATH]

Prints `passed failed skipped seconds` (errors count as failed). Each failing
test becomes a `test-failure` incident; on a --full run each test file whose
tests all pass becomes a `verified` incident (once per distinct entry). With `--task Tn` each
`test-failure` incident carries `task`, and a later run closes that task's open ones whose test
now passes (`resolution` `fixed`, as `sl incident resolve` writes it); a pytest run that produces
no results logs one `no-result` incident (so does a non-Python run that prints no test count: `no tests ran:`). A `--fast` path that does not exist (node suffix `::` ignored) is a usage error: exit 2, `test path not found`, no incident. Appends
a `tests` line to the progress ledger. On every run it also writes
`.superlite/test-summary.json` (--summary), the file `pt_review packet` reads:
`{"passed": N, "failed": N, "skipped": N, "seconds": S, "mode": "fast|full",
"failures": ["file::test: message", ...], "skipped_tests": ["file::test", ...],
"files": {"file": [passed, failed], ...}, "started": EPOCH}` (the background pointer also records `"mode"`)
(a run where pytest produced nothing records failed=1 and the reason, also as `"error"`). Exit 0 when nothing failed, 1 when a
test failed or none ran, 2 when pytest could not run.

--background starts a detached run of the same command, prints `summary: <path>` and exits 0
at once. Each background run gets its own summary file (`test-summary-<id>.json` next to
--summary) and the pointer `test-summary.latest` (atomic) names the newest run; when a run
finishes it also publishes its summary to --summary, unless a newer run has started since.
--wait blocks until the pointed run's own summary exists (an older summary never counts),
prints it, and exits 0 green, 1 red, 2 on timeout or when no background run was started.
--wait PATH waits on exactly that run's summary (the `summary:` line; --background also prints
`wait: <abs>/sl run_tests --wait <path>` with the absolute path of the sl launcher, copy it verbatim); bare --wait uses the shared pointer.
Put --wait last or before another flag: argparse takes a following word as its PATH.
A green --full run (not --task, not --fast, not --record) in a git toplevel holding `scripts/test_layers.py` also stamps the
unit layer green (`run_tests: unit layer stamped`), from digests taken before the run, so a file changed during it stays stale; a stamp
error prints `run_tests: unit layer not stamped: <err>` and never changes the exit code. `--record` never stamps.
Stdlib only.
"""
# Complexity notation:
#   T = testcases in the junit XML, X = bytes of the XML, F = distinct test files, k = failing tests,
#   sk = skipped tests, I = lines in the incident log (B = its bytes), d = depth of a dotted classname,
#   p = pytest path args, O = bytes of pytest output, c = length of an incident context, w = width of one line
import argparse  # O(1)
import importlib.util  # O(1)
import json  # O(1)
import os  # O(1)
import re  # O(1)
import shlex  # O(1)
import subprocess  # O(1)
import sys  # O(1)
import tempfile  # O(1)
import time  # O(1)
import xml.etree.ElementTree as ET  # O(1)
from pathlib import Path  # O(1)

sys.path.insert(0, str(Path(__file__).resolve().parent))  # O(path list)
import _pyrun as pyrun  # noqa: E402  # O(1) module load
import testcmd  # noqa: E402  # O(1) module load
import commit_task as ct  # noqa: E402  # O(1) module load
import next_tasks as nt  # noqa: E402  # O(1) module load
import trees  # noqa: E402  # O(1) module load


DEFAULT_SUMMARY = ".superlite/test-summary.json"  # O(1)
POLL_SECONDS = 0.5  # O(1)
DEFAULT_WAIT = 600.0  # O(1)


def project_root(start):  # O(d) stats, d = depth of start
    """Nearest ancestor-or-self of start holding a `.superlite/` directory, else None.

    The walk stops at the first directory holding `.git` (file or directory): a nested
    worktree without its own `.superlite/` does not adopt the enclosing checkout's."""
    p = Path(start).resolve()  # O(d)
    for d in (p, *p.parents):  # O(d) iterations
        if (d / ".superlite").is_dir():  # O(1)
            return d  # O(1)
        if (d / ".git").exists():  # O(1) git toplevel reached without .superlite
            return None  # O(1)
    return None  # O(1)


def to_root(a, argv, cwd, root):  # O(len argv + p) rewrite --fast paths against cwd, then chdir to root
    """Relative --fast paths are rewritten (in a.fast and in argv) so they stay valid from the root."""
    def fix(chunk):  # O(len chunk)
        parts = [x if os.path.isabs(x) else os.path.relpath(os.path.join(cwd, x), root) for x in chunk.split(",") if x]  # O(len chunk)
        return ",".join(parts)  # O(len chunk)
    eq = [j for j, x in enumerate(argv) if x.startswith("--fast=")]  # --fast=PATH spelling | O(len argv)
    if a.fast and eq:  # O(1)
        j = eq[0]  # O(1)
        argv[j] = "--fast=" + fix(argv[j][7:])  # O(len)
        argv[j + 1:j + len(a.fast)] = [fix(c) for c in argv[j + 1:j + len(a.fast)]]  # O(p)
        a.fast = [argv[j][7:], *argv[j + 1:j + len(a.fast)]]  # O(p)
    elif a.fast and "--fast" in argv:  # O(1)
        i = argv.index("--fast") + 1  # O(len argv)
        argv[i:i + len(a.fast)] = [fix(c) for c in a.fast]  # O(p)
        a.fast = argv[i:i + len(a.fast)]  # O(p)
    os.chdir(root)  # O(1)
    print(f"run_tests: running from {root}", file=sys.stderr)  # O(1)


def pointer_path(summary):  # O(1)
    p = Path(summary)  # O(1)
    return p.with_name(p.stem + ".latest")  # O(1)


def run_summary_path(summary, run_id):  # O(1)
    p = Path(summary)  # O(1)
    return p.with_name(f"{p.stem}-{run_id}{p.suffix}")  # O(1)


def atomic_write(path, text):  # O(len text) + file write
    p = Path(path)  # O(1)
    p.parent.mkdir(parents=True, exist_ok=True)  # O(1)
    tmp = p.with_name(f"{p.name}.{os.getpid()}.tmp")  # O(1) unique per process
    tmp.write_text(text, encoding="utf-8")  # O(len text)
    tmp.replace(p)  # O(1) atomic rename


def read_pointer(summary):  # O(1)
    try:  # O(1)
        d = json.loads(pointer_path(summary).read_text(encoding="utf-8"))  # O(1)
        return d if isinstance(d, dict) and d.get("id") else None  # O(1)
    except (OSError, ValueError):  # O(1)
        return None  # O(1)


def start_background(a, argv):  # O(len argv) + one detached spawn
    run_id = f"{time.strftime('%Y%m%dT%H%M%S')}-{os.getpid()}-{os.urandom(3).hex()}"  # O(1) unique id
    mine = run_summary_path(a.summary, run_id).resolve()  # O(1) absolute: --wait may run from another cwd
    child = [sys.executable, str(Path(__file__).resolve()),  # O(len argv)
             *[x for x in argv if x != "--background"],  # O(len argv)
             "--summary", str(mine), "--publish", str(Path(a.summary).resolve()), "--run-id", run_id]  # O(1) last flag wins
    atomic_write(pointer_path(a.summary), json.dumps({"id": run_id, "summary": str(mine),  # O(1)
                                                      "started": time.time(),  # O(1)
                                                      "mode": "fast" if "--fast" in argv else "full"}) + "\n")  # O(1)
    pyrun.spawn_detached(child, mine.with_suffix(".log"))  # O(1) + process spawn
    print(f"summary: {mine}")  # O(1)
    print(wait_line(mine))  # O(1)
    return 0  # O(1)


def wait_line(path):  # O(1)
    sl = str(Path(__file__).resolve().with_name("sl"))  # O(1) absolute: shell variables do not persist between calls
    return f'wait: {json.dumps(sl) if " " in sl else sl} run_tests --wait {path}'  # O(1)


def wait_target(a):  # O(1)
    if a.wait_path:  # O(1) an explicit run
        return Path(a.wait_path)  # O(1)
    ptr = read_pointer(a.summary)  # O(1) bare --wait: the shared pointer
    return Path(ptr["summary"]) if ptr else None  # O(1)


def wait_background(a):  # O(timeout / POLL_SECONDS) polls
    mine = wait_target(a)  # O(1)
    if mine is None:  # O(1)
        print("run_tests: no background run to wait for", file=sys.stderr)  # O(1)
        return 2  # O(1)
    deadline = time.monotonic() + (a.timeout if a.timeout is not None else DEFAULT_WAIT)  # O(1)
    while True:  # O(timeout / POLL_SECONDS) iterations
        if mine.exists():  # O(1)
            try:  # O(1)
                data = json.loads(mine.read_text(encoding="utf-8"))  # O(summary size)
                break  # O(1)
            except (OSError, ValueError):  # O(1) half-written (non-atomic fs): retry
                pass  # O(1)
        if time.monotonic() >= deadline:  # O(1)
            print(f"run_tests: timed out waiting for {mine}", file=sys.stderr)  # O(1)
            return 2  # O(1)
        time.sleep(POLL_SECONDS)  # O(1)
    print(json.dumps(data, ensure_ascii=False, indent=1))  # O(summary size)
    green = not data.get("failed") and bool(data.get("passed") or data.get("skipped"))  # O(1)
    return 0 if green else 1  # O(1)


def publish_summary(a):  # O(summary size)
    """After a background run: copy its summary to the published path unless a newer run started."""
    if not (a.run_id and a.publish):  # O(1)
        return  # O(1)
    ptr = read_pointer(a.publish)  # O(1)
    if ptr and ptr["id"] != a.run_id:  # O(1) a newer run owns the published file
        return  # O(1)
    atomic_write(a.publish, Path(a.summary).read_text(encoding="utf-8"))  # O(summary size)


def case_file(case):  # O(d) stats, O(d^2) path work (stats are uncached)
    f = case.get("file")  # O(1)
    if f:  # O(1)
        return f.replace("\\", "/")  # O(len(f))
    cn = case.get("classname") or ""  # O(1)
    if re.search(r"[\\/]|\.(?:[jt]sx?|go|rs|cs)$", cn):  # a path-like classname (vitest, jest, go, cargo): use it as the file | O(1)
        return cn.replace("\\", "/")  # O(1)
    parts = [p for p in (cn or case.get("name") or "").split(".") if p]  # an empty classname is a collection error: pytest names the module (#196) | O(d)
    while parts and not Path(*parts).with_suffix(".py").exists():  # O(d) iterations; Path join + stat O(d) each
        parts.pop()  # O(1)
    if parts:  # O(d)
        return Path(*parts).with_suffix(".py").as_posix()  # O(d)
    return case.get("name") or "unknown"  # O(1)


def failure_line(case, text, fallback):  # O(len(text) + d)
    base = re.escape(Path(case_file(case)).name)  # O(d) stats + O(len)
    hits = re.findall(rf"{base}:(\d+)", text or "")  # O(len(text))
    return int(hits[-1]) if hits else fallback  # O(1)


COLLECTION_FAILURE = "collection failure"  # pytest's junit <error> message for a test module that fails to import | O(1)


def raised(text):  # O(len text)
    """The error in a pytest traceback: its last `E ` line, else its last non-blank line."""
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]  # O(len text)
    errs = [ln[1:].strip() for ln in lines if ln.startswith("E ")]  # O(len text)
    return (errs or lines or ["no error text"])[-1]  # O(1)


def collection_report(xml_path):  # O(X + T*(d + len(failure text)))
    """pytest exit 2 from collection errors: the report's parse (the errors are its failures); None for any other interrupt."""
    try:  # O(1)
        root = ET.parse(xml_path).getroot()  # O(X)
    except ET.ParseError:  # O(1)
        return None  # O(1)
    if not any(e.get("message") == COLLECTION_FAILURE for e in root.iter("error")):  # O(T)
        return None  # O(1)
    return parse_junit(xml_path)  # O(X + T*d)


def parse_junit(xml_path):  # O(X + T*(d + len(failure text)))
    """-> (counts dict, failures [(file, line, context)], files {file: [ok, bad]});
    skipped test ids are in counts["skipped_tests"]"""
    root = ET.parse(xml_path).getroot()  # O(X) XML parse
    counts = {"passed": 0, "failed": 0, "skipped": 0, "skipped_tests": []}  # O(1)
    failures, files = [], {}  # O(1)
    for case in root.iter("testcase"):  # O(T) iterations
        f = case_file(case)  # O(d) stats per testcase (uncached; repeated in failure_line)
        ok_bad = files.setdefault(f, [0, 0])  # O(1)
        bad = case.find("failure")  # O(1)
        if bad is None:  # O(1)
            bad = case.find("error")  # O(1)
        if bad is not None:  # O(1)
            counts["failed"] += 1  # O(1)
            ok_bad[1] += 1  # O(1)
            msg = (bad.get("message") or (bad.text or "").strip()).split("\n")[0]  # O(len(failure text))
            if msg == COLLECTION_FAILURE:  # pytest's generic message: add the error it raised (#196) | O(len(failure text))
                msg = f"{msg}: {raised(bad.text)}"  # O(1)
            line = failure_line(case, bad.text, int(case.get("line") or 0) + 1)  # O(len(failure text) + d)
            failures.append((f, line, f"{case.get('name')}: {msg}"))  # O(1)
        elif case.find("skipped") is not None:  # O(1)
            counts["skipped"] += 1  # O(1)
            counts["skipped_tests"].append(f"{f}::{case.get('name')}")  # O(1)
        else:  # O(1)
            counts["passed"] += 1  # O(1)
            ok_bad[0] += 1  # O(1)
    return counts, failures, files  # O(1)


ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")  # CSI and OSC escape sequences | O(1)


def strip_ansi(text):  # O(len text)
    return ANSI_RE.sub("", text)  # O(len text)


def junit_reports(xml_path, literal):  # O(n log n) for n files next to xml_path
    """Every non-empty `<stem>*.xml` beside xml_path (sidecars) plus the literal report, sorted."""
    found = {p for p in Path(xml_path).parent.glob(Path(xml_path).stem + "*.xml")}  # O(n)
    if literal is not None:  # O(1)
        found.add(Path(literal))  # O(1)
    return sorted(p for p in found if p.exists() and p.stat().st_size)  # O(n log n)


def merge_junit(paths):  # O(sum of parse_junit)
    """Sum parse_junit over the reports; a file that is not XML is skipped. -> (counts, failures, files)"""
    counts = {"passed": 0, "failed": 0, "skipped": 0, "skipped_tests": []}  # O(1)
    failures, files = [], {}  # O(1)
    for p in paths:  # O(len paths) iterations
        try:  # O(1)
            c, f, fl = parse_junit(p)  # O(X + T*d)
        except ET.ParseError:  # O(1)
            continue  # O(1)
        for k in ("passed", "failed", "skipped"):  # O(1)
            counts[k] += c[k]  # O(1)
        counts["skipped_tests"] += c["skipped_tests"]  # O(sk)
        failures += f  # O(k)
        for name, (ok, bad) in fl.items():  # O(F) iterations
            cur = files.setdefault(name, [0, 0])  # O(1)
            cur[0] += ok  # O(1)
            cur[1] += bad  # O(1)
    return counts, failures, files  # O(1)


def existing_verified(log):  # O(B)
    seen = set()  # O(1)
    p = Path(log)  # O(1)
    if p.exists():  # O(1)
        for ln in p.read_text(encoding="utf-8").splitlines():  # O(I) iterations; read O(B)
            try:  # O(1)
                e = json.loads(ln)  # O(w)
            except json.JSONDecodeError:  # O(1)
                continue  # O(1)
            if isinstance(e, dict) and e.get("kind") == "verified":  # O(1)
                seen.add((e.get("file"), e.get("context")))  # O(1)
    return seen  # O(1)


def write_summary(path, mode, counts, failures, seconds, error=None, files=None, started=None):  # O(k + sk) + file write
    """Write the test summary `pt_review packet` reads (atomically); `started` is the run's start (epoch)."""  # O(1)
    data = {"passed": counts["passed"], "failed": counts["failed"] + (1 if error else 0),  # O(1)
            "skipped": counts["skipped"], "seconds": round(seconds, 1), "mode": mode,  # O(1)
            "failures": [f"{f}::{ctx}"[:200] for f, _line, ctx in failures]  # O(k)
            + ([error[:200]] if error else []),  # O(k) list concat
            "skipped_tests": counts["skipped_tests"],  # O(1)
            "files": {k: list(v) for k, v in (files or {}).items()}}  # O(F)
    if error:  # a crashed run says so, so the packet never reads it as a test run (#81) | O(1)
        data["error"] = error[:200]  # O(1)
    if started is not None:  # the packet closes only incidents logged before this run started (#101) | O(1)
        data["started"] = started  # O(1)
    p = Path(path)  # O(1)
    p.parent.mkdir(parents=True, exist_ok=True)  # O(1)
    tmp = p.with_name(p.name + ".tmp")  # O(1)
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")  # O(k + sk) dumps + write
    tmp.replace(p)  # O(1) rename


def add_incidents(log, items, task=None):  # O(total c) + one locked append (no spawn in process)
    """items: (file, line, context, kind, resolution). A --task run stamps `task` on each entry; a kind outside
    incident.KINDS (`no-result`) is set after make_entry, as the hooks write theirs. Never spawns `incident add`,
    which takes neither `task` nor `no-result` (SUPERLITE_SL swaps only the launcher)."""
    # always in process, also with SUPERLITE_SL: the spawned `incident add` takes neither task nor `no-result` | O(1)
    inc = nt.sibling("incident")  # O(1)
    entries = []  # O(1)
    for f, line, ctx, kind, res in items:  # O(k); a bad item is skipped, not the batch
        try:  # O(1)
            e = inc.make_entry(str(f), int(line), ctx, agent="run_tests", kind=kind if kind in inc.KINDS else None, resolution=res or None)  # O(c)
        except (ValueError, TypeError) as err:  # O(1)
            print(f"warning: incident not logged ({f}:{line}): {err}", file=sys.stderr)  # O(1)
            continue  # O(1)
        if kind and kind not in inc.KINDS:  # O(1)
            e["kind"] = kind  # O(1)
        if task:  # O(1)
            e["task"] = task  # O(1)
        entries.append(e)  # O(1)
    try:  # O(1)
        inc.append(log, entries)  # O(total c) one locked write
    except OSError as err:  # O(1)
        print(f"warning: incidents not logged: {err}", file=sys.stderr)  # O(1)


def resolve_passed(log, task, failures, files):  # O(B + I + k) read the log once, one append (#180)
    """Close `task`'s open test-failure incidents whose file ran in this run and whose test no longer fails:
    the entry `sl incident resolve` writes (kind of the open entry, resolution `fixed`, ruling as context)."""
    p = Path(log)  # O(1)
    if not task or not files or not p.exists():  # O(1)
        return  # O(1)
    resolved = nt.sibling("pt_review").RESOLVED  # the resolutions the packet counts as closed; lazy | O(module)
    newest = {}  # location -> its newest non-verified entry, as the packet and `finish` count open | O(1)
    for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():  # O(I) iterations; read O(B)
        try:  # O(1)
            e = json.loads(ln)  # O(w)
        except ValueError:  # O(1)
            continue  # O(1)
        if isinstance(e, dict) and "file" in e and "line" in e and e.get("kind") != "verified":  # O(1)
            newest[(e["file"], e["line"])] = e  # O(1)
    norm = lambda x: str(x).replace("\\", "/")  # noqa: E731 | O(len)
    ran = {norm(f) for f, (ok, _bad) in files.items() if ok}  # a file with no passing test (a collection error) closes nothing (#196) | O(F)
    failing = {(norm(f), ctx.split(": ", 1)[0]) for f, _line, ctx in failures}  # (file, test name) still red | O(k)
    items = [(f, line, "fixed: passed on a later run", "test-failure", "fixed")  # O(1) each
             for (f, line), e in newest.items()  # O(I) iterations
             if e.get("kind") == "test-failure" and e.get("task") == task  # O(1)
             and str(e.get("resolution", "")).lower() not in resolved  # O(1)
             and norm(f) in ran and (norm(f), str(e.get("context", "")).split(": ", 1)[0]) not in failing]  # O(len)
    add_incidents(log, items, task)  # O(total c) one append


def missing_fast_paths(paths):  # O(p) the --fast paths that do not exist (a `::node` suffix is dropped)
    return [p for p in paths if not Path(p.split("::", 1)[0]).exists()]  # O(p)


def missing_line(paths, cwd, root):  # O(p) the usage-error text for missing --fast paths, else None
    gone = missing_fast_paths(paths)  # O(p)
    if not gone:  # O(1)
        return None  # O(1)
    return f"test path not found: {', '.join(gone)} (cwd {cwd}, root {root})"  # O(p)


def unit_snapshot(a, label):  # the unit layer's digests before a full run, None when it cannot be stamped | O(n * size) n = repo files
    if label != "full" or a.task:  # O(1)
        return None  # O(1)
    try:  # O(1)
        cwd = Path.cwd().resolve()  # O(1)
        top = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True).stdout.strip()  # O(1)
        script = cwd / "scripts" / "test_layers.py"  # O(1)
        if not top or Path(top).resolve() != cwd or not script.is_file():  # O(1)
            return None  # O(1)
        saved = list(sys.path)  # the layer script inserts its own folder; load it without leaving that behind | O(P)
        try:  # O(1)
            spec = importlib.util.spec_from_file_location("superlite_test_layers", script)  # O(1)
            mod = importlib.util.module_from_spec(spec)  # O(1)
            spec.loader.exec_module(mod)  # O(size)
        finally:  # O(1)
            sys.path[:] = saved  # O(P)
        if "unit" not in mod.LAYERS:  # O(1)
            return None  # O(1)
        return (mod, cwd, mod.layer_store.store_path(cwd), mod.layer_digests("unit", cwd))  # O(n * size)
    except Exception as e:  # O(1)
        print(f"run_tests: unit layer not stamped: {e}", file=sys.stderr)  # O(1)
        return None  # O(1)


def stamp_unit(snap):  # stamp the unit layer green from a snapshot; an error never changes the exit code | O(n)
    if snap is None:  # O(1)
        return  # O(1)
    try:  # O(1)
        mod, root, state, digests = snap  # O(1)
        mod.write_stamp(root, state, "unit", digests)  # O(n)
        print("run_tests: unit layer stamped", file=sys.stderr)  # O(1)
    except Exception as e:  # O(1)
        print(f"run_tests: unit layer not stamped: {e}", file=sys.stderr)  # O(1)


def main(argv=None):  # O(X + T*d + B + F log F) + pytest run + one incident append
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])  # O(1)
    mode = ap.add_mutually_exclusive_group()  # O(1)
    mode.add_argument("--fast", nargs="+", metavar="PATH",  # O(1)
                      help="run only these test paths (comma or space separated)")  # O(1)
    mode.add_argument("--full", action="store_true", help="run everything (default)")  # O(1)
    ap.add_argument("--log", default=ct.DEFAULT_LOG)  # O(1)
    ap.add_argument("--ledger", default=ct.DEFAULT_LEDGER)  # O(1)
    ap.add_argument("--summary", default=DEFAULT_SUMMARY,  # O(1)
                    help="test summary JSON for pt_review packet (default %(default)s)")  # O(1)
    ap.add_argument("--background", action="store_true",  # O(1)
                    help="start a detached run, print `summary: <path>`, exit 0")  # O(1)
    ap.add_argument("--wait", nargs="?", const="", default=None, dest="wait_path", metavar="PATH",  # O(1)
                    help="wait for PATH's run (the `summary:` line); bare: the latest background run")  # O(1)
    ap.add_argument("--timeout", type=float, default=None, help=f"--wait limit in seconds (default {DEFAULT_WAIT:.0f})")  # O(1)
    ap.add_argument("--task", default=None, help="task id: compiled stacks run in .superlite/trees/<task> (own files only); incidents carry it and a green run closes its red ones")  # O(1)
    ap.add_argument("--plan", default=None, help=f"plan for --task Owns (default: the plan in .superlite/stable.json, else {nt.DEFAULT_PLAN})")  # O(1)
    ap.add_argument("--record", action="store_true", help="record a result run outside run_tests (needs --passed and --command), no test run")  # O(1)
    ap.add_argument("--passed", type=int, default=None, help="--record: tests that passed")  # O(1)
    ap.add_argument("--failed", type=int, default=0, help="--record: tests that failed (default 0)")  # O(1)
    ap.add_argument("--skipped", type=int, default=0, help="--record: tests that were skipped (default 0)")  # O(1)
    ap.add_argument("--seconds", type=float, default=0.0, help="--record: run time in seconds (default 0)")  # O(1)
    ap.add_argument("--command", default=None, help="--record: the command that ran them")  # O(1)
    ap.add_argument("--run-id", default=None, help=argparse.SUPPRESS)  # O(1) set by --background
    ap.add_argument("--publish", default=None, help=argparse.SUPPRESS)  # O(1) set by --background
    argv = list(sys.argv[1:] if argv is None else argv)  # O(len argv)
    a = ap.parse_args(argv)  # O(1)
    a.started = time.time()  # before the runner reads any code: the summary's `started` (#101) | O(1)
    cwd = Path.cwd().resolve()  # O(1)
    a.cwd = cwd  # for the missing-path message, before to_root moves us | O(1)
    root = project_root(cwd) if a.wait_path is None else None  # --wait paths are absolute | O(d)
    if root is not None and root != cwd:  # O(1)
        to_root(a, argv, cwd, root)  # O(len argv + p)
    if a.record:  # O(1)
        return record_run(a)  # O(1)
    if a.wait_path is not None:  # O(1)
        return wait_background(a)  # O(timeout / POLL_SECONDS)
    if a.background:  # O(1)
        if a.fast:  # a missing path is refused here, not in the detached child | O(1)
            try:  # O(1)
                fast = expand_fast_paths([p for chunk in a.fast for p in nt.csv(chunk)])  # O(p)
                spec = testcmd.resolve(".", fast)  # O(m + f)
            except FileNotFoundError:  # left to the child | O(1)
                fast, spec = [], None  # O(1)
            gone = missing_line(fast, a.cwd, Path.cwd()) if spec and spec["python"] and fast else None  # O(p)
            if gone:  # O(1)
                print(f"run_tests: {gone}", file=sys.stderr)  # O(1)
                return 2  # O(1)
        return start_background(a, argv)  # O(len argv) + spawn
    if a.run_id:  # O(1) detached child: a crash still leaves a (red) summary for --wait
        try:  # O(1)
            return run(a)  # see run
        except BaseException as e:  # O(1)
            if not Path(a.summary).exists():  # O(1)
                write_summary(a.summary, "full", {"passed": 0, "failed": 0, "skipped": 0,  # O(1)
                                                  "skipped_tests": []}, [], 0.0,  # O(1)
                              error=f"run_tests crashed: {e!r}")  # O(1)
                publish_summary(a)  # O(summary size)
            raise  # O(1)
    return run(a)  # see run


def record_run(a):  # a full result the agent ran outside run_tests: reports only, closes no incidents | O(1)
    for flag, val in (("--passed", a.passed), ("--command", a.command)):  # O(1)
        if val is None or val == "":  # O(1)
            print(f"run_tests: --record needs {flag}", file=sys.stderr)  # O(1)
            return 2  # O(1)
    for flag, val in (("--passed", a.passed), ("--failed", a.failed), ("--skipped", a.skipped), ("--seconds", a.seconds)):  # O(1)
        if val < 0:  # O(1)
            print(f"run_tests: {flag} must be >= 0", file=sys.stderr)  # O(1)
            return 2  # O(1)
    write_summary(a.summary, "full", {"passed": a.passed, "failed": a.failed, "skipped": a.skipped, "skipped_tests": []}, [], a.seconds, started=a.started)  # O(1)
    data = json.loads(Path(a.summary).read_text(encoding="utf-8"))  # O(1)
    data["recorded"] = a.command[:200]  # O(1)
    atomic_write(a.summary, json.dumps(data, ensure_ascii=False, indent=1) + "\n")  # O(1)
    pointer_path(a.summary).unlink(missing_ok=True)  # an older background run must not shadow the recorded result | O(1)
    ct.append_ledger(a.ledger, f"- tests full passed={a.passed} failed={a.failed} skipped={a.skipped} seconds={round(a.seconds, 1):g} recorded")  # O(1)
    print(f"{a.passed} {a.failed} {a.skipped} {a.seconds:.1f}")  # O(1)
    return 0  # O(1)


def root_superlite(s, root, raw=False):  # O(len s) a tree has no .superlite/ (git-ignored): point its word-initial uses at the project root
    def at(m):  # O(1) raw root for env values and inside quotes, shell-quoted otherwise
        quoted = m.start() > 0 and s[m.start() - 1] in "\"'"  # O(1)
        return (str(root) if raw or quoted else shlex.quote(str(root))) + "/.superlite/"  # O(1)
    return re.sub(r"(?<![\w./~-])\.superlite/", at, s)  # O(len s)


def run_other(a, spec, paths, label, cwd=None):  # one runner command (any language) | O(X + o) + the run
    """Run the resolved non-Python command: JUnit when the runner wrote one, else exit code plus output parsing."""
    with tempfile.TemporaryDirectory() as tmp:  # O(1)
        xml_path = Path(tmp) / "junit.xml"  # O(1)
        root = Path.cwd().resolve()  # main chdir'd to the project root | O(1)
        sub = lambda s: root_superlite(s, root) if cwd else s  # noqa: E731 | O(len)
        sub = (lambda f: lambda s: f(s).replace("{junit}", str(xml_path)))(sub)  # noqa: E731 | O(len)
        subenv = lambda s: (root_superlite(s, root, raw=True) if cwd else s).replace("{junit}", str(xml_path))  # noqa: E731 | env is never shell-parsed | O(len)
        env = {**os.environ, **{k: subenv(str(v)) for k, v in (spec.get("env") or {}).items()}}  # O(env)
        literal = Path(spec["junit"]) if spec["junit"] and "{junit}" not in spec["junit"] else None  # a path the runner always writes | O(1)
        alt = None  # the tree copy of a .superlite/ report, used when the root has none | O(1)
        if literal and cwd and not literal.is_absolute():  # the runner writes it inside its tree, .superlite/ at the root | O(1)
            if literal.parts[:1] == (".superlite",):  # O(1)
                literal, alt = root / literal, Path(cwd) / literal  # a runner config may write it relative to the tree | O(1)
            else:  # O(1)
                literal = Path(cwd) / literal  # O(1)
        for stale in (literal, alt):  # a stale report must not count | O(1)
            if stale and stale.exists():  # O(1)
                stale.unlink()  # O(1)
        marker = Path(cwd) / ".superlite-setup.done" if cwd else Path(".superlite") / "setup.done"  # setup runs once per run directory (per tree) | O(1)
        if spec["setup"] and not marker.exists():  # O(1)
            pyrun.run_tree(sub(spec["setup"]), shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, cwd=cwd)  # O(o)
            marker.parent.mkdir(parents=True, exist_ok=True)  # O(1)
            marker.write_text("ok\n", encoding="utf-8")  # O(1)
        t0 = time.monotonic()  # O(1)
        r = pyrun.run_tree(sub(spec["command"]), shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, cwd=cwd)  # O(o) + the run
        seconds = time.monotonic() - t0  # O(1)
        text = (r.stdout or "") + (r.stderr or "")  # O(o)
        if alt and not literal.exists():  # O(1)
            literal = alt  # O(1)
        reports = junit_reports(xml_path, literal)  # the main report plus sidecars | O(n log n)
        report = None  # O(1)
        if reports:  # O(1)
            counts, failures, files = merge_junit(reports)  # O(X + T*d)
            if sum(counts[k] for k in ("passed", "failed", "skipped")):  # nothing parseable: fall back to the exit code | O(1)
                report = reports  # O(1)
        if report is None:  # no JUnit: exit code plus the last 40 lines, failing names best effort | O(o)
            p = testcmd.parse_output(strip_ansi(text), r.returncode)  # O(o)
            counts = {"passed": p["passed"], "failed": p["failed"], "skipped": p["skipped"], "skipped_tests": []}  # O(1)
            last = next((ln for ln in reversed(p["tail"]) if ln.strip()), "no output")  # O(1)
            failures = [("-", 0, f"{n}: failed") for n in p["names"]]  # O(k)
            if r.returncode and not failures:  # a red exit with no names: name the command | O(1)
                failures = [("-", 0, f"exit code {r.returncode} from `{spec['command']}`: {last}"[:200])]  # O(1)
            if r.returncode and p["error"]:  # a compile error leads the failures | O(1)
                failures.insert(0, ("-", 0, f"build error: {p['error']}"[:160]))  # O(1)
            files = {}  # O(1)
            tail_set = {x.strip() for x in p["tail"]}  # O(40)
            kept = [x for x in (p["error"] if r.returncode else "", p["marker"]) if x and x not in tail_set]  # the error and marker may sit above the last 40 lines | O(40)
            atomic_write(Path(a.summary).with_name("test-output.log"), "\n".join([*kept, *p["tail"]]) + "\n")  # O(40)
            if not r.returncode and not (p["passed"] or p["failed"] or p["skipped"] or p["names"]):  # the runner counted zero tests: a stop, not a pass (#240) | O(1)
                reason = f"no tests ran: exit {r.returncode} from `{spec['command']}` with no test count; its filter may select nothing"[:300]  # O(1)
                print(f"run_tests: {reason}", file=sys.stderr)  # O(1)
                write_summary(a.summary, label, {"passed": 0, "failed": 0, "skipped": 0, "skipped_tests": []}, [], seconds, error=reason)  # O(1)
                publish_summary(a)  # O(summary size)
                add_incidents(a.log, [("-", 0, reason, "no-result", "open")], a.task)  # O(c)
                print(f"0 0 0 {seconds:.1f}")  # O(1)
                return 1  # O(1)
    return finish_run(a, label, counts, failures, files, seconds, r.returncode)  # O(k + F)


def expand_fast_paths(paths):  # O(p) source paths -> related tests; test paths kept
    """--fast accepts source or test paths; a source path maps via testcmd.resolve_related."""
    out = []  # O(1)
    spec = testcmd.resolve(".")  # O(m + f)
    py = spec is None or bool(spec["python"])  # .py maps only for a Python runner | O(1)
    for p in paths:  # O(p)
        rel = p.replace("\\", "/")  # O(len)
        mapped = (rel.endswith(".py") and py) or testcmd.has_related(".")  # O(file)
        if not mapped or testcmd.is_test_path(rel) or not Path(rel).is_file():  # tests, packages, dirs, other sources pass through | O(1)
            out.append(rel)  # O(1)
            continue  # O(1)
        out.extend(testcmd.resolve_related(".", rel))  # raises FileNotFoundError | O(1)
    return out  # O(p)


def stable_plan():  # O(S) the plan path `plan_tools lint --stable` recorded, else None
    try:  # O(1)
        return json.loads(Path(".superlite/stable.json").read_text(encoding="utf-8")).get("plan") or None  # O(S)
    except (OSError, ValueError, AttributeError):  # O(1)
        return None  # O(1)


def run(a):  # O(X + T*d + B + F log F) + the runner + one incident append
    paths = [p for chunk in (a.fast or []) for p in nt.csv(chunk)]  # O(p)
    label = "fast" if paths else "full"  # O(1)
    if paths:  # O(1)
        try:  # O(1)
            paths = expand_fast_paths(paths)  # O(p)
        except FileNotFoundError as e:  # O(1)
            reason = str(e)  # O(1)
            print(f"run_tests: {reason}", file=sys.stderr)  # O(1)
            write_summary(a.summary, label, {"passed": 0, "failed": 0, "skipped": 0, "skipped_tests": []}, [], 0.0, error=reason)  # O(1)
            publish_summary(a)  # O(summary size)
            print("0 0 0 0.0")  # O(1)
            return 1  # O(1)
    a.unit_snap = unit_snapshot(a, label)  # before the runner touches anything | O(n * size)
    spec = testcmd.resolve(".", paths)  # .superlite/test-cmd.json, else marker files | O(m + f)
    if spec is None:  # no test command: exit 2 with a clear summary | O(1)
        hint = getattr(testcmd, "missing_reason", None)  # T3's text when present | O(1)
        reason = hint(Path(".")) if hint else ("no test command found: add .superlite/test-cmd.json "  # O(1)
                  '{"language","test","test_file","junit","setup"} or a package.json scripts.test, go.mod, Cargo.toml, *.csproj or pytest project')
        print(f"run_tests: {reason}", file=sys.stderr)  # O(1)
        write_summary(a.summary, label, {"passed": 0, "failed": 0, "skipped": 0, "skipped_tests": []}, [], 0.0, error=reason)  # O(1)
        publish_summary(a)  # O(summary size)
        print("0 0 0 0.0")  # O(1)
        return 2  # O(1)
    if not spec["python"]:  # a configured `test` command may narrow the suite: it never stamps the unit layer | O(1)
        a.unit_snap = None  # O(1)
    if spec["python"] and paths:  # a missing path is a usage error, not a no-result stop (#235) | O(p)
        gone = missing_line(paths, getattr(a, "cwd", Path.cwd()), Path.cwd())  # O(p)
        if gone:  # O(1)
            print(f"run_tests: {gone}", file=sys.stderr)  # O(1)
            write_summary(a.summary, label, {"passed": 0, "failed": 0, "skipped": 0, "skipped_tests": []}, [], 0.0, error=gone)  # O(1)
            publish_summary(a)  # O(summary size)
            print("0 0 0 0.0")  # O(1)
            return 2  # O(1)
    if not spec["python"]:  # O(1)
        tree = None  # O(1)
        if a.task and spec.get("isolate", False):  # compiled stack: test own files only, in an isolated tree | O(1)
            sp = stable_plan()  # O(S)
            plan = a.plan or next((p for p in (sp, nt.DEFAULT_PLAN) if p and Path(p).is_file()), None)  # --plan, else the first existing of stable.json's plan and the default | O(1)
            if not plan or not Path(plan).is_file():  # O(1)
                tried = a.plan or ", ".join(x for x in (sp and f"{sp} (.superlite/stable.json)", nt.DEFAULT_PLAN) if x)  # O(1)
                reason = f"--task {a.task} needs its plan: pass --plan PLAN (tried {tried}, not found)"  # O(1)
                print(f"run_tests: {reason}", file=sys.stderr)  # O(1)
                write_summary(a.summary, label, {"passed": 0, "failed": 0, "skipped": 0, "skipped_tests": []}, [], 0.0, error=reason)  # O(1)
                publish_summary(a)  # O(summary size)
                print("0 0 0 0.0")  # O(1)
                return 2  # O(1)
            info = nt.parse_plan(plan)  # O(L)
            if a.task not in info:  # O(1)
                nt.die(f"unknown task {a.task}")  # O(1)
            ct.add_also_owns(info, a.ledger)  # --also and --claim rulings own their files too (#239) | O(c + o)
            tree = trees.prepare(".", a.task, info[a.task]["owns"])  # O(f * o) + git checkout
        return run_other(a, spec, paths, label, cwd=tree)  # O(X + o)

    with tempfile.TemporaryDirectory() as tmp:  # O(1) mkdtemp
        xml_path = Path(tmp) / "junit.xml"  # O(1)
        try:  # O(1)
            base = pyrun.pytest_cmd()  # O(1) + at most one probe spawn
        except pyrun.PytestUnavailable as e:  # O(1)
            print(f"run_tests: {e}", file=sys.stderr)  # O(1)
            print("0 0 0 0.0")  # O(1)
            return 2  # O(1)
        cmd = [*base, *(paths or testcmd.python_full_args(Path("."))), "-q", "-p", "no:cacheprovider",  # O(p)
               "-o", "junit_family=xunit1", f"--junitxml={xml_path}"]  # O(1)
        t0 = time.monotonic()  # O(1)
        r = pyrun.run_tree(cmd, capture_output=True, text=True, encoding="utf-8",  # O(O) + process spawn (pytest run time dominates)
                           errors="replace")  # O(1)
        seconds = time.monotonic() - t0  # O(1)
        has_xml = xml_path.exists() and xml_path.stat().st_size > 0  # O(1)
        parsed = collection_report(xml_path) if r.returncode == 2 and has_xml else None  # a collection error stops pytest with exit 2 (#196) | O(X + T*d)
        if parsed is None and (r.returncode not in (0, 1) or not has_xml):  # O(1)
            tail = (r.stdout + r.stderr).strip().splitlines()[-5:]  # O(O)
            reason = "pytest produced no results: " + " | ".join(tail)  # O(1)
            print(reason, file=sys.stderr)  # O(1)
            write_summary(a.summary, label, {"passed": 0, "failed": 0, "skipped": 0,  # O(1)
                                             "skipped_tests": []}, [], seconds,  # O(1)
                          error=reason if r.returncode != 5 else None)  # O(1)
            publish_summary(a)  # O(summary size)
            add_incidents(a.log, [("-", 0, reason, "no-result", "open")], a.task)  # a run with nothing to read is a stop, not a pass (#140) | O(c)
            print(f"0 0 0 {seconds:.1f}")  # O(1)
            return 1 if r.returncode == 5 else 2  # O(1)
        counts, failures, files = parsed or parse_junit(xml_path)  # O(X + T*d)
    return finish_run(a, label, counts, failures, files, seconds, r.returncode)  # O(k + F)


def finish_run(a, label, counts, failures, files, seconds, returncode):  # O(k + F + B) one incident append
    write_summary(a.summary, label, counts, failures, seconds, files=files, started=getattr(a, "started", None))  # O(k + sk + F)
    publish_summary(a)  # O(summary size)
    items = [(f, line, ctx, "test-failure", "open") for f, line, ctx in failures]  # O(k)
    if label == "full":  # O(1)
        seen = existing_verified(a.log)  # O(B)
        for f, (ok, bad) in sorted(files.items()):  # O(F log F) sort; O(F) iterations
            ctx = f"run_tests full: {ok} tests pass"  # O(1)
            if ok and not bad and (f, ctx) not in seen:  # O(1) set lookup
                items.append((f, 0, ctx, "verified", None))  # O(1)
    add_incidents(a.log, items, a.task)  # O(k + F) one append
    resolve_passed(a.log, a.task, failures, files)  # O(B + I + k) a --task run closes its tests that pass now (#180)

    summary = (f"{counts['passed']} {counts['failed']} {counts['skipped']} "  # O(1)
               f"{seconds:.1f}")  # O(1)
    ct.append_ledger(a.ledger, f"- tests {label} passed={counts['passed']} "  # O(1)
                     f"failed={counts['failed']} skipped={counts['skipped']} "  # O(1)
                     f"seconds={seconds:.1f}")  # O(1)
    print(summary)  # O(1)
    red = counts["failed"] or not (counts["passed"] or counts["skipped"])  # O(1)
    if not red:  # O(1)
        stamp_unit(getattr(a, "unit_snap", None))  # O(n)
    return 1 if red else 0  # O(1)


if __name__ == "__main__":  # O(1)
    sys.exit(main())  # O(1)
