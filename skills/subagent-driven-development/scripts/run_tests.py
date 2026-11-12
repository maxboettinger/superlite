#!/usr/bin/env python3
"""Run pytest, parse the junit XML, print one summary line.

    run_tests.py [--fast PATHS... | --full] [--log PATH] [--ledger PATH]
                 [--summary PATH] [--background] [-m EXPR]
    run_tests.py --record --passed N [--failed N] [--skipped N] [--seconds S] [--scope WORD] --command CMD   (a result run outside run_tests; mode `recorded` with its scope, default external, never the full run; report only, closes no incidents)
    run_tests.py [--timeout S] [--summary PATH] --wait [PATH]

The test command comes from, in order: the project's `.superlite/test-cmd.json`, the main checkout's, the user-level entry for the detected language (`~/.config/superlite/test-cmd.json`), then detection.
Every exit path leaves a summary: a usage error, an unknown task, a missing pytest, an unprepared tree or a crash (`run_tests crashed: ...`, exit 2) writes a red zero summary; `--wait` names a background run whose process died (its pid sits in `<summary>.pid`) and the log of one that timed out.
A foreground full run also keeps its summary as `test-summary-full.json` beside the summary; no later fast, recorded or failed run overwrites it (#593). A `--fast` test file carrying a marker the project's addopts `-m` deselects runs with `-m "<marker> or (<addopts expr>)"` and says so on stderr; an explicit `-m` wins.
A macOS `xcodebuild test` outside the desktop login session (`launchctl managername` not `Aqua`) stops before any run with an ENV-ERROR (exit 2); `SUPERLITE_GUI_CHECK=0` and `"lock": false` skip the check (#561).
A red xcodebuild run that never reached its test runner (testmanagerd) is the same ENV-ERROR stop, not a failing test (#561).
A red pytest id in the output is placed at its file with its message and line when the file exists, else it stays `-::<id>: <message>` (B119).
A red Swift (xcodebuild) run reports each failure at its file and line (`failure_sites`, #499); a counted `--fast` run limited to Swift files covers them, so a later green run closes those files' located failures and an uncounted run closes none.
When a run prints no test count and exits 0, the stop names the runner's own "no tests" line (`; runner: <line>`).
Every run keeps its full output (pytest with `-rP`, so a passing test's prints show) in `<summary stem>.output.log` beside the summary (newest 20 kept); the summary's `output` names it, a foreground run prints `run_tests: output <path>` and `--wait` prints `output: <path>` right before its summary line (#501).
A no-result stop keeps its command, exit and output in `.superlite/no-result-*.log` (newest 20) and its incident carries them as `target`, `command`, `exit`, `log`.
An isolated `--task` run prints a stderr `tree` line; its `--fast` tree overlays every working-tree change except files owned by unfinished sibling tasks (kept at base, named on the line), a `--full` tree the task's own files.
A fleet worker's `--fast` run without `--task` (package reviewer, fixer; not a lead) on an isolated stack runs in its own tree `.superlite/trees/worker-<Wn>`: every working-tree change except files of unfinished tasks and changed files another busy fixer's or reviewer's brief names (#479); `--full` runs stay in the run root.

An isolated tree links `.superlite/` to the project's, so a test command finds its scripts there. Before each run, every overlaid file whose bytes changed since the tree's last run gets a fresh mtime (`.superlite/trees/<task>.digests.json`), so a build tool sees the edit (#507).
With --task Tn whose plan **Tests:** field holds cmd=<command>, the run executes that command instead of the project's runner (a fast run; --fast paths are not passed; with no readable count its exit code is one test).
`--also F [F ...]` (needs `--task`; relative paths read from the caller's cwd) records `Ruling: Tn also commits F` in the ledger before the run, so the tree holds F and commit_task commits it; a red tree run names up to 5 changed files the tree lacks and suggests it.

Prints `passed failed skipped seconds` (errors count as failed). Each failing
test becomes a `test-failure` incident; on a --full run each test file whose
tests all pass becomes a `verified` incident (once per distinct entry). With `--task Tn` each
`test-failure` incident carries `task`, and a later run closes that task's open ones whose test
now passes (`resolution` `fixed`, as `sl incident resolve` writes it); a green `--task` run closes that task's `-` failures and re-logs other tasks' open ones there, and a green `--full` run without `--task` closes every run_tests failure (#380); a pytest run that produces
no results logs one `no-result` incident (so does a non-Python run that prints no test count: `no tests ran:`). A `--fast` path that does not exist (node suffix `::` ignored) is a usage error: exit 2, `test path not found`, no incident. A Node project without `node_modules` is refused the same way
(exit 2, `node_modules missing in <dir>: run <install> first`, no incident); in an isolated `--task` tree the root's and each workspace package's `node_modules` are symlinked in first (relative link, no setup command), and the guard checks the tree. Appends
a `tests` line to the progress ledger. On every run it also writes
`.superlite/test-summary.json` (--summary), the file `pt_review packet` reads:
`{"passed": N, "failed": N, "skipped": N, "seconds": S, "mode": "fast|full",
"failures": ["file::test: message", ...], "skipped_tests": ["file::test", ...],
"files": {"file": [passed, failed], ...}, "started": EPOCH}` (the background pointer also records `"mode"`)
(a run where pytest produced nothing records failed=1 and the reason, also as `"error"`). Exit 0 when nothing failed, 1 when a
test failed or none ran, 2 when pytest could not run.

--background starts a detached run of the same command, prints `summary: <path>`, a `next:` line (run the wait line now, in the foreground; do not end your turn until it reports) and, last, the `wait:` line, and exits 0
at once. Each background run gets its own summary file (`test-summary-<id>.json` next to
--summary) and the pointer `test-summary.latest` (atomic) names the newest run; when a run
finishes it also publishes its summary to --summary, unless a newer run has started since.
--wait blocks until the pointed run's own summary exists (an older summary never counts),
prints it, and exits 0 green, 1 red, 2 on timeout or when no background run was started.
--wait PATH waits on exactly that run's summary (the `summary:` line; --background also prints
`wait: <abs>/sl run_tests --wait <path>` with the absolute path of the sl launcher, copy it verbatim); bare --wait uses the shared pointer.
Put --wait last or before another flag: argparse takes a following word as its PATH.
A green --full run (not --task, not --fast, not --record) in a git toplevel holding `scripts/test_layers.py` also stamps the
unit layer green (a configured test command too) (`run_tests: unit layer stamped`), from digests taken before the run, so a file changed during it stays stale; a stamp
error prints `run_tests: unit layer not stamped: <err>` and never changes the exit code. `--record` never stamps.
A Swift `--fast` run whose template holds `{only_testing}` maps each test file to `-only-testing:<Target>/<Suite>` (target from the project's target membership: Sources phase files, synchronized folders, Package.swift paths; then folder names); a path outside every test target runs the unfiltered `test` command instead (#398).
Every test subprocess (pytest, a test-cmd.json command and its setup) gets the environment without `SUPERLITE_FLEET_*` variables (a fleet pane's worker, role and parent dir); a test-cmd.json `env` entry still applies on top.
A test-cmd.json `{only_testing}` placeholder in a project with no Swift files is refused before the run (exit 2, `test-cmd.json uses {only_testing}, the Xcode (Swift) placeholder, ...`, no incident; `--background` refuses in the parent).
`--wait` ends with a stderr summary line (`tests (full): P passed, F failed`), looks once more at its deadline, and on a timeout names the live pid and the rerun command; a runner's output goes to temp files, so a child left running cannot hold the run.
`--limit S` (default 3600; 0 = none) kills a test command's whole process tree after S seconds: exit 2, a red summary `wall-clock limit: test run killed after S s` and a `no-result` incident.
SIGTERM and SIGHUP on a run kill its test processes and leave a red summary (`run_tests stopped by SIGTERM; ...`, exit 2).
With `--task Tn` every summary carries `"task"` and `--background` also writes `test-summary-<Tn>.latest`; `--wait <earlier run of Tn>` then waits on Tn's newest run and says so on stderr.
`-m EXPR` selects a pytest marker (`-m EXPR` goes onto the pytest argv, or onto a test-cmd.json pytest command; a runner that is not pytest is a usage error, exit 2) and makes the run a fast (narrowed) run. A pytest exit 5 stops with `pytest collected nothing (exit 5): <cause>`: all tests deselected (by `-m`, or by a deselecting `-m` in the project's addopts), or the paths hold no tests.
A `--full` run holds a machine-wide lock per toolchain (`<superlite home>/locks/full-suite-<toolchain>.lock`, flock; the OS frees it when the process ends; toolchain = python, xcode, or the test-cmd.json language, shell by default) around its test command, so full suites of one toolchain on one machine run one at a time while other toolchains run alongside (#550). A waiting run prints `run_tests: waiting for the python full-suite lock (held by pid P in ROOT (task T) since HH:MM:SS, N min ago; its last full run took M min); python full runs on one machine run one at a time, in arrival order: queue place N of M` (a free lock with another waiter first: `(next in line: pid Q in ROOT)`; waiters queue first come first served in `<lock>.queue`, #655), then `run_tests: full-suite lock taken after N s`. The test processes get `SUPERLITE_FULL_SUITE_LOCK=<pid>`, so a nested run skips the lock. `--lock-wait S` (default 3600; 0 = no limit) bounds the wait: exit 2, a red summary `full-suite lock: still held by ... after S s (run_tests --lock-wait S; 0 = no limit)`, no incident. `--wait` names the lock a background run still waits for; every waiting run writes `<summary>.lockwait` (lock, holder, pid, since, place, queued). `~/.superlite/machine.json` `"admission"` says per toolchain how a full run is admitted (#659): a list `["<gate>", "run", "--"]` is the admission command for every toolchain; an object keyed by toolchain (python, xcode, shell, ... and an optional `"default"`) holds per key a list (admission command), `"self"` (the machine admits the run itself: no lock, no wrap, `SUPERLITE_FULL_SUITE_LOCK` set for nested runs; right only when the machine's gate really admits that toolchain's test command) or `"lock"` (the full-suite lock); no entry means the lock. The run names which applied, once, as `run_tests: full run through the admission command <gate> (...); no full-suite lock`, `run_tests: full run admitted by the machine itself (...)` or `run_tests: full run under the <toolchain> full-suite lock (...)`. With a command the commands run behind that argv prefix with no lock, the wait for the gate's start shows once as `waiting for the admission command <gate> to start the full run` (and `--wait` names it), the wait is left out of the run's seconds, and `--lock-wait S` bounds it (exit 2, red summary `admission: <gate> did not start the full run after S s`). An unusable entry, a missing command, or a gate that exits before the tests start prints one warning and the run takes the lock (#655). A lock file that cannot be opened prints `run_tests: full-suite lock not taken: ...; running without it`.
A run in an isolated tree builds there: an `xcodebuild` word in the command (not `-list`, not one that already has `-derivedDataPath`) gets `-derivedDataPath <tree>/.build/DerivedData`, so the build output (module cache included) goes with the tree (#574); the tree is marked busy while the run lasts.
Before each run (the run process, not the `--background` parent) the disk is checked (`trees.disk_gate`): below the floor the run stops (exit 2, red summary `disk: ...`, no tree made), below the warn level it prints a `disk: WARNING` line. Each run also removes the trees nothing needs (committed tasks, stopped workers' trees; never its own or a busy one) and orphaned DerivedData of removed trees. An `ENOSPC` anywhere ends the run with one `run_tests: disk full (ENOSPC): ...` line, exit 2, no traceback.
A tree run exports `SUPERLITE_DERIVED_DATA_PATH=<tree>/.build/DerivedData` to the test command and its setup (a test-cmd.json `env` entry of that name wins), so a project script can pass it to xcodebuild (#614).
A Swift project with an Xcode project whose command has no xcodebuild word to rewrite and names no script reading that variable prints one `run_tests: WARNING` line per command (remembered in `.superlite/derived-data-warned.json`) (#614).
When the disk is below the warn level the run also removes module cache entries (`ModuleCache.noindex` under the DerivedData home) untouched for 24 h and prints `module cache: removed N entries` (#614).
Stdlib only.
"""
# Complexity notation:
#   T = testcases in the junit XML, X = bytes of the XML, F = distinct test files, k = failing tests,
#   sk = skipped tests, I = lines in the incident log (B = its bytes), d = depth of a dotted classname,
#   p = pytest path args, O = bytes of pytest output, c = length of an incident context, w = width of one line
import argparse  # O(1)
import ast  # O(1)
import contextlib  # O(1)
import errno  # O(1)
import configparser  # O(1)
import hashlib  # O(1)
import importlib.util  # O(1)
import json  # O(1)
import os  # O(1)
import re  # O(1)
import shlex  # O(1)
import signal  # O(1)
import subprocess  # O(1)
import sys  # O(1)
import tempfile  # O(1)
import time  # O(1)
import traceback  # O(1)
import uuid  # O(1)
import xml.etree.ElementTree as ET  # O(1)
try:  # O(1)
    import fcntl  # O(1)
except ImportError:  # Windows: no flock | O(1)
    fcntl = None  # O(1)
from pathlib import Path  # O(1)

sys.path.insert(0, str(Path(__file__).resolve().parent))  # O(path list)
import _pyrun as pyrun  # noqa: E402  # O(1) module load
import testcmd  # noqa: E402  # O(1) module load
import full_queue  # noqa: E402  # O(1) module load
import full_gate  # noqa: E402  # O(1) module load
import failure_sites  # noqa: E402  # O(1) module load
import gui_session  # noqa: E402  # O(1) module load
import commit_task as ct  # noqa: E402  # O(1) module load
import state  # noqa: E402  # O(1) module load
import next_tasks as nt  # noqa: E402  # O(1) module load
import trees  # noqa: E402  # O(1) module load


DEFAULT_SUMMARY = ".superlite/test-summary.json"  # O(1)
FULL_COPY = "test-summary-full.json"  # O(1) the newest foreground full result, beside the summary (#593)
POLL_SECONDS = 0.5  # O(1)
DEFAULT_WAIT = 540.0  # O(1)
DEFAULT_LIMIT = 3600.0  # O(1) wall-clock seconds for one test run; 0 = none
LOCK_ENV = "SUPERLITE_FULL_SUITE_LOCK"  # O(1) exported to the test processes: the pid holding the lock
LOCK_POLL = 0.5  # O(1)
QUEUE_SEEN = 30.0  # seconds between a waiter's refreshes of its queue entry | O(1)
DEFAULT_LOCK_WAIT = 3600.0  # O(1) seconds a full run waits for the lock; 0 = no limit
CURRENT_TASK = None  # --task of this run; write_summary records it | O(1)
WRITTEN = set()  # resolved summary paths this process wrote; main clears it | O(1)
XCODE_OUT = re.compile(r"^\W*✘ Test |: error: -\[|^Test case '.*' failed on |\*\* TEST (?:FAILED|SUCCEEDED) \*\*", re.M)  # xcodebuild test output | O(1)
WARNING = ""  # the platform warning of this full run; write_summary records it, main clears it | O(1)
OUTPUT = ""  # the full-output log of this run; write_summary records it, main clears it | O(1)


class LimitHit(Exception):  # O(1) a test command ran past --limit and its process tree was killed
    def __init__(self, seconds, text, command=""):  # O(1)
        super().__init__(f"limit {seconds:g} s")  # O(1)
        self.seconds, self.text, self.command = seconds, text, command  # O(1)


class LockBusy(Exception):  # O(1) the full-suite lock stayed held past --lock-wait
    def __init__(self, seconds, holder):  # O(1)
        super().__init__(f"lock wait {seconds:g} s")  # O(1)
        self.seconds, self.holder = seconds, holder  # O(1)


def full_lock_path(toolchain):  # O(1) read at call time, so SUPERLITE_HOME moves it; one lock file per toolchain (#550)
    return state.home() / "locks" / f"full-suite-{toolchain}.lock"  # O(1)


def lock_toolchain(spec):  # O(len command) the toolchain a full run's lock is named for: python, xcode, or the spec's language
    if spec.get("python"):  # O(1)
        return "python"  # O(1)
    command = str(spec.get("command") or "")  # O(1)
    if "xcodebuild" in command:  # O(len)
        return "xcode"  # O(len)
    language = re.sub(r"[^a-z0-9]+", "-", str(spec.get("language") or "").lower()).strip("-")  # O(len)
    return language or "shell"  # O(1)


def lock_holder(path):  # O(file) the holder record in the lock file, None when missing, empty, half-written or not a record
    try:  # O(1)
        info = json.loads(Path(path).read_text(encoding="utf-8"))  # O(file)
    except (OSError, ValueError):  # O(1)
        return None  # O(1)
    return info if isinstance(info, dict) and isinstance(info.get("pid"), int) and not isinstance(info.get("pid"), bool) else None  # O(1)


def holder_text(info):  # O(1) `pid P in ROOT (task T) since HH:MM:SS`
    if not info:  # O(1)
        return "another run"  # O(1)
    text = f"pid {info.get('pid')} in {info.get('root')}"  # O(1)
    if info.get("task"):  # O(1)
        text += f" (task {info['task']})"  # O(1)
    started = info.get("started")  # O(1)
    if isinstance(started, (int, float)) and not isinstance(started, bool):  # O(1)
        text += " since " + time.strftime("%H:%M:%S", time.localtime(started))  # O(1)
    return text  # O(1)


def wait_detail(holder):  # O(file) `pid P in ROOT (task T) since HH:MM:SS, N min ago` plus the holder root's last full run length when known
    text = holder_text(holder)  # O(1)
    if not holder:  # O(1)
        return text  # O(1)
    started = holder.get("started")  # O(1)
    if isinstance(started, (int, float)) and not isinstance(started, bool):  # O(1)
        text += f", {max(0, int((time.time() - started) / 60))} min ago"  # O(1)
    try:  # O(1)
        last = json.loads((Path(str(holder.get("root"))) / ".superlite" / FULL_COPY).read_text(encoding="utf-8"))["seconds"]  # O(file)
        if isinstance(last, (int, float)) and not isinstance(last, bool) and last > 0:  # O(1)
            text += f"; its last full run took {round(last / 60)} min"  # O(1)
    except (OSError, ValueError, KeyError, TypeError):  # O(1)
        pass  # O(1)
    return text  # O(1)


def note_holder(note):  # O(file) the lock's current holder named by a .lockwait note; the note's own copy, or a bare old-style holder dict, when the lock is free
    try:  # O(1)
        data = json.loads(Path(note).read_text(encoding="utf-8"))  # O(file)
    except (OSError, ValueError):  # O(1)
        return None  # O(1)
    if not isinstance(data, dict):  # O(1)
        return None  # O(1)
    if "lock" not in data:  # a note from before the per-toolchain locks is the holder itself | O(1)
        return lock_holder(note)  # O(file)
    current = lock_holder(data["lock"]) if isinstance(data["lock"], str) else None  # O(file)
    inner = data.get("holder")  # O(1)
    return current or (inner if isinstance(inner, dict) and isinstance(inner.get("pid"), int) else None)  # O(1)


def admission_note(note):  # O(file) the .lockwait note of a run waiting for the admission command, None for any other note or a dead pid
    try:  # O(1)
        data = json.loads(Path(note).read_text(encoding="utf-8"))  # O(file)
    except (OSError, ValueError):  # O(1)
        return None  # O(1)
    if not isinstance(data, dict) or not isinstance(data.get("admission"), str) or not isinstance(data.get("pid"), int):  # O(1)
        return None  # O(1)
    return data if full_queue.pid_alive(data["pid"]) else None  # O(1)


def lock_name(note):  # O(file) the toolchain in a .lockwait note's lock path, python for an old-style note
    try:  # O(1)
        name = Path(json.loads(Path(note).read_text(encoding="utf-8"))["lock"]).stem  # O(file)
    except (OSError, ValueError, KeyError, TypeError):  # O(1)
        return "python"  # O(1)
    return name[len("full-suite-"):] if name.startswith("full-suite-") else "python"  # O(1)


def is_ancestor(pid):  # O(64) ps calls; True when pid is a parent, grandparent... of this process
    cur = os.getppid()  # O(1)
    for _ in range(64):  # O(64)
        if cur <= 1:  # O(1)
            return False  # O(1)
        if cur == pid:  # O(1)
            return True  # O(1)
        try:  # O(1)
            out = subprocess.run(["ps", "-o", "ppid=", "-p", str(cur)], capture_output=True, text=True, timeout=10).stdout  # O(1)
            cur = int(out.strip())  # O(1)
        except (OSError, ValueError, subprocess.SubprocessError):  # O(1)
            return False  # O(1)
    return False  # O(1)


@contextlib.contextmanager
def full_suite_lock(a, label, toolchain="python", enabled=True):  # O(wait / LOCK_POLL) polls; a full run holds the machine-wide lock around its test command
    if label == "full" and not enabled:  # O(1)
        print('run_tests: no full-suite lock: test-cmd.json sets "lock": false (its test command runs on another machine)', file=sys.stderr)  # O(1)
        yield  # O(1)
        return  # O(1)
    if label != "full" or fcntl is None:  # O(1)
        yield  # O(1)
        return  # O(1)
    path = full_lock_path(toolchain)  # O(1)
    holder = lock_holder(path)  # O(file)
    if holder and (os.environ.get(LOCK_ENV) == str(holder["pid"]) or is_ancestor(holder["pid"])):  # an outer run holds it for us, also when the env lost LOCK_ENV | O(64)
        yield  # O(1)
        return  # O(1)
    try:  # O(1)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)  # O(1)
        fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)  # O(1)
    except OSError as err:  # O(1)
        print(f"run_tests: full-suite lock not taken: {err}; running without it", file=sys.stderr)  # O(1)
        yield  # O(1)
        return  # O(1)
    note = Path(a.summary).with_suffix(".lockwait")  # O(1)
    me = {"id": uuid.uuid4().hex, "pid": os.getpid(), "root": str(Path.cwd()), "task": a.task, "time": time.time(), "seen": time.time()}  # O(1)
    try:  # the finally frees the lock, leaves the queue and deletes the note | O(1)
        t0 = time.monotonic()  # O(1)
        waited = False  # O(1)
        last_seen = time.monotonic()  # O(1)
        shown = None  # the (place, queued) the note holds | O(1)
        while True:  # O(wait / LOCK_POLL) iterations
            if time.monotonic() - last_seen >= QUEUE_SEEN:  # O(1)
                me["seen"], last_seen = time.time(), time.monotonic()  # O(1)
            try:  # O(1)
                snap = full_queue.join(path, me)  # O(queue)
            except OSError:  # an unwritable queue never blocks the run | O(1)
                snap = {"place": 1, "queued": 1, "first": me}  # O(1)
            try:  # O(1)
                if snap["place"] != 1:  # only the queue head tries the lock | O(1)
                    raise BlockingIOError  # O(1)
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)  # O(1)
                break  # O(1)
            except BlockingIOError:  # O(1)
                holder = lock_holder(path)  # O(file)
                if not waited:  # O(1)
                    waited = True  # O(1)
                    detail = wait_detail(holder) if holder else "next in line: " + holder_text(snap["first"])  # O(file)
                    print(f"run_tests: waiting for the {toolchain} full-suite lock (held by {detail}); {toolchain} full runs on one machine run one at a time, in arrival order: queue place {snap['place']} of {snap['queued']}".replace("(held by next in line:", "(next in line:"), file=sys.stderr)  # O(1)
                if shown != (snap["place"], snap["queued"]):  # O(1)
                    shown = (snap["place"], snap["queued"])  # O(1)
                    atomic_write(note, json.dumps({"lock": str(path), "holder": holder or {}, "pid": os.getpid(), "since": time.time() - (time.monotonic() - t0), "place": snap["place"], "queued": snap["queued"]}))  # O(1)
                remaining = None if a.lock_wait is None else a.lock_wait - (time.monotonic() - t0)  # O(1)
                if remaining is not None and remaining <= 0:  # O(1)
                    raise LockBusy(a.lock_wait, holder)  # O(1)
                time.sleep(LOCK_POLL if remaining is None else min(LOCK_POLL, remaining))  # O(1)
            except OSError as err:  # O(1)
                print(f"run_tests: full-suite lock not taken: {err}; running without it", file=sys.stderr)  # O(1)
                yield  # O(1)
                return  # O(1)
        with contextlib.suppress(OSError):  # O(1)
            note.unlink()  # O(1)
        if waited:  # O(1)
            print(f"run_tests: full-suite lock taken after {time.monotonic() - t0:.0f} s", file=sys.stderr)  # O(1)
        os.lseek(fd, 0, 0)  # O(1)
        os.ftruncate(fd, 0)  # O(1)
        os.write(fd, json.dumps({"pid": os.getpid(), "root": str(Path.cwd()), "task": a.task, "started": time.time()}).encode())  # O(1)
        earlier = os.environ.get(LOCK_ENV)  # O(1)
        os.environ[LOCK_ENV] = str(os.getpid())  # O(1)
        try:  # O(1)
            yield  # O(1)
        finally:  # O(1)
            if earlier is None:  # O(1)
                os.environ.pop(LOCK_ENV, None)  # O(1)
            else:  # O(1)
                os.environ[LOCK_ENV] = earlier  # O(1)
            with contextlib.suppress(OSError):  # O(1)
                os.ftruncate(fd, 0)  # O(1)
    finally:  # O(1)
        with contextlib.suppress(OSError):  # O(1)
            full_queue.leave(path, me["id"])  # O(queue)
        with contextlib.suppress(OSError):  # O(1)
            note.unlink()  # O(1)
        os.close(fd)  # O(1)


class Gate:  # O(1) where a full run's commands run: through the admission command, or under the full-suite lock (#655)
    def __init__(self, a=None, toolchain="python", prefix=None, stack=None):  # O(1)
        self.a, self.toolchain, self.prefix, self.stack = a, toolchain, prefix, stack  # O(1)
        self.waited = 0.0  # seconds the admission command held the run before its tests started | O(1)

    def run(self, cmd, limit=None, shell=False, env=None, cwd=None):  # O(o) + the run; LimitHit past `limit` seconds
        if self.prefix:  # O(1)
            try:  # O(1)
                r = full_gate.run_admitted(self.prefix, cmd, limit, self.a.lock_wait, {**(env if env is not None else os.environ), LOCK_ENV: str(os.getpid())}, cwd,  # O(o)
                                           Path(self.a.summary).with_suffix(".lockwait"))  # O(1)
                self.waited += r.waited  # O(1)
                return r  # O(1)
            except full_gate.NotAdmitted as e:  # one warning, then the lock for the rest of the run | O(1)
                print(f"run_tests: admission command {os.path.basename(self.prefix[0])} {e.reason}; running under the {self.toolchain} full-suite lock", file=sys.stderr)  # O(1)
                self.prefix = None  # O(1)
                self.stack.enter_context(full_suite_lock(self.a, "full", self.toolchain))  # O(wait / LOCK_POLL)
            except subprocess.TimeoutExpired as e:  # O(o)
                raise LimitHit(limit, (e.output or b"").decode("utf-8", errors="replace"), cmd if isinstance(cmd, str) else shlex.join(cmd)) from None  # O(o)
        return run_captured(cmd, limit=limit, **({"shell": True} if shell else {}), **({"env": env} if env is not None else {}), **({"cwd": cwd} if cwd else {}))  # O(o) + the run


@contextlib.contextmanager
def full_run_gate(a, label, toolchain="python", enabled=True):  # O(wait / LOCK_POLL); per machine.json "admission": the admission command, the machine itself ("self") or the full-suite lock (#659)
    adm = full_gate.Admission(None, None, None, None)  # O(1)
    if label == "full" and enabled:  # O(1)
        adm = full_gate.admission_for(toolchain)  # O(file)
        if adm.warning:  # O(1)
            print(f"run_tests: {adm.warning}", file=sys.stderr)  # O(1)
        outer = os.environ.get(LOCK_ENV, "")  # O(1)
        nested = adm.mode is not None and outer.isdigit() and is_ancestor(int(outer))  # an outer run covers this one | O(64)
        if nested and adm.mode in ("command", "self"):  # O(1)
            yield Gate(a, toolchain)  # O(1)
            return  # O(1)
        if not nested and adm.note:  # O(1)
            print(f"run_tests: {adm.note}", file=sys.stderr)  # O(1)
    if adm.mode == "command":  # O(1)
        with contextlib.ExitStack() as stack:  # O(1)
            yield Gate(a, toolchain, adm.argv, stack)  # O(1)
        return  # O(1)
    if adm.mode == "self":  # O(1)
        before = os.environ.get(LOCK_ENV)  # O(1)
        os.environ[LOCK_ENV] = str(os.getpid())  # O(1)
        try:  # O(1)
            yield Gate(a, toolchain)  # O(1)
        finally:  # O(1)
            if before is None:  # O(1)
                os.environ.pop(LOCK_ENV, None)  # O(1)
            else:  # O(1)
                os.environ[LOCK_ENV] = before  # O(1)
        return  # O(1)
    with contextlib.ExitStack() as stack:  # O(1)
        stack.enter_context(full_suite_lock(a, label, toolchain, enabled))  # O(wait / LOCK_POLL)
        yield Gate(a, toolchain)  # O(1)


class Stopped(Exception):  # O(1) SIGTERM or SIGHUP reached run_tests; run_tree kills the test processes on the way out
    pass  # O(1)


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


ALSO_RULING = "declared before the test run (run_tests --also)"  # the ledger text of an --also claim


def root_relative(x, cwd, root):  # O(len x) x against cwd, unless only the root holds it: then x is already root-relative (#548)
    mine = os.path.relpath(os.path.join(cwd, x), root)  # O(len)
    bare = x.split("::", 1)[0]  # O(len)
    prefix = os.path.relpath(cwd, root).replace(os.sep, "/") + "/"  # O(len) the cwd's own root-relative prefix; only a doubled prefix is read from the root
    if "..." in x or not x.replace(os.sep, "/").startswith(prefix) or os.path.exists(os.path.join(root, mine.split("::", 1)[0])) or not os.path.exists(os.path.join(root, bare)):  # O(1) stats
        return mine  # O(len)
    print(f"run_tests: --fast {x} read from the root", file=sys.stderr)  # O(1)
    return x  # O(1)


def to_root(a, argv, cwd, root):  # O(len argv + p) rewrite --fast paths against cwd, then chdir to root
    """Relative --fast paths are rewritten (in a.fast and in argv) so they stay valid from the root."""
    def fix(chunk):  # O(len chunk)
        parts = [x if os.path.isabs(x) else root_relative(x, cwd, root) for x in chunk.split(",") if x]  # O(len chunk)
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
    if a.also and "--also" in argv:  # every --also chunk stays valid from the root, a trailing / kept | O(len argv)
        in_also, fixed = False, []  # O(1)
        for k, x in enumerate(argv):  # O(len argv) iterations
            if x == "--also":  # O(1)
                in_also = True  # O(1)
            elif x.startswith("--"):  # O(1)
                in_also = False  # O(1)
            elif in_also:  # O(1)
                argv[k] = x if os.path.isabs(x) else os.path.relpath(os.path.join(cwd, x), root).replace(os.sep, "/") + ("/" if x.endswith("/") else "")  # O(len)
                fixed.append(argv[k])  # O(1)
        a.also = fixed  # O(n)
    os.chdir(root)  # O(1)
    print(f"run_tests: running from {root}", file=sys.stderr)  # O(1)


def pointer_path(summary):  # O(1)
    p = Path(summary)  # O(1)
    return p.with_name(p.stem + ".latest")  # O(1)


def task_pointer_path(summary, task):  # O(1) `<stem>-<task>.latest` beside the summary
    p = Path(summary)  # O(1)
    return p.with_name(f"{p.stem}-{task}.latest")  # O(1)


RUN_NAME = re.compile(r"^(.*)-\d{8}T\d{6}-\d+-[0-9a-f]{6}\.json$")  # O(1)


def run_stem(mine):  # O(len name) the stem before the run id in a run summary's name, else None
    m = RUN_NAME.match(Path(mine).name)  # O(len name)
    return m.group(1) if m else None  # O(1)


def run_summary_path(summary, run_id):  # O(1)
    p = Path(summary)  # O(1)
    return p.with_name(f"{p.stem}-{run_id}{p.suffix}")  # O(1)


def output_log_path(summary):  # O(1) `<stem>.output.log` beside the summary
    p = Path(summary)  # O(1)
    return p.with_name(p.stem + ".output.log")  # O(1)


def keep_output(summary, command, rc, text):  # O(n log n) n = logs kept, + file write; keeps the newest 20 logs
    """Write the run's full output (command, exit, blank line, text) to output_log_path(summary); return its path, "" on OSError."""
    try:  # O(1)
        path = output_log_path(Path(summary).resolve())  # O(1)
        atomic_write(path, f"command: {command}\nexit: {rc}\n\n{text}")  # O(len text)
        olds = sorted(path.parent.glob("*.output.log"), key=lambda q: (q.stat().st_mtime, q.name))  # O(n log n)
        for old in olds[:-20]:  # O(n)
            if old != path:  # O(1)
                old.unlink(missing_ok=True)  # O(1)
        return str(path)  # O(1)
    except OSError:  # O(1)
        return ""  # O(1)


def save_output(a, command, rc, text):  # O(len text) keep the run's output, remember it for the summary, name it on stderr
    global OUTPUT  # O(1)
    OUTPUT = keep_output(a.summary, command, rc, text)  # O(len text)
    if OUTPUT:  # O(1)
        print(f"run_tests: output {OUTPUT}", file=sys.stderr)  # O(1)


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


WAIT_CUE = "next: tests still running; run the wait line below now, in the foreground (never as a background command), and do not end your turn until it reports."  # O(1)


def narrowed(a):  # a run limited by paths, a marker or pass-through args is fast, not full | O(1)
    return bool(a.fast or a.marker or getattr(a, "passthrough", None))  # O(1)


def start_background(a, argv):  # O(len argv) + one detached spawn
    run_id = f"{time.strftime('%Y%m%dT%H%M%S')}-{os.getpid()}-{os.urandom(3).hex()}"  # O(1) unique id
    mine = run_summary_path(a.summary, run_id).resolve()  # O(1) absolute: --wait may run from another cwd
    child = [sys.executable, str(Path(__file__).resolve()),  # O(len argv)
             *[x for x in argv if x != "--background"],  # O(len argv)
             "--summary", str(mine), "--publish", str(Path(a.summary).resolve()), "--run-id", run_id,  # O(1) last flag wins
             *(["--", *a.passthrough] if a.passthrough else [])]  # the pass-through stays last, after the child's own flags | O(t)
    ptr = {"id": run_id, "summary": str(mine), "started": time.time(),  # O(1)
           "mode": "fast" if narrowed(a) else "full"}  # O(1)
    atomic_write(pointer_path(a.summary), json.dumps(ptr) + "\n")  # O(1)
    if a.task:  # a wait on an earlier run of this task finds its newest run (#507) | O(1)
        atomic_write(task_pointer_path(a.summary, a.task), json.dumps({**ptr, "task": a.task}) + "\n")  # O(1)
    proc = pyrun.spawn_detached(child, mine.with_suffix(".log"))  # O(1) + process spawn
    try:  # the pid lets --wait name a child that died without a summary | O(1)
        atomic_write(mine.with_suffix(".pid"), f"{proc.pid}\n")  # O(1)
    except OSError:  # O(1)
        pass  # O(1)
    print(f"summary: {mine}")  # O(1)
    print(WAIT_CUE)  # O(1) the cue sits right above the wait line, which stays last (#286)
    print(wait_line(mine))  # O(1)
    return 0  # O(1)


def pid_alive(mine):  # O(1) True when the pid recorded for a background run is a live process, False when gone or unknown (never claim a dead pid runs)
    if os.name == "nt":  # O(1) no cheap liveness probe: say nothing
        return False  # O(1)
    try:  # O(1)
        pid = int(mine.with_suffix(".pid").read_text(encoding="utf-8").strip())  # O(1)
        if pid <= 0:  # O(1)
            return False  # O(1)
        os.kill(pid, 0)  # O(1)
    except PermissionError:  # exists, owned by another user | O(1)
        return True  # O(1)
    except (OSError, ValueError):  # O(1)
        return False  # O(1)
    return True  # O(1)


def wait_line(path):  # O(1)
    sl = str(Path(__file__).resolve().with_name("sl"))  # O(1) absolute: shell variables do not persist between calls
    return f'wait: {json.dumps(sl) if " " in sl else sl} run_tests --wait {path}'  # O(1)


def wait_target(a):  # O(1)
    if a.wait_path:  # O(1) an explicit run
        return Path(a.wait_path)  # O(1)
    ptr = read_pointer(a.summary)  # O(1) bare --wait: the shared pointer
    return Path(ptr["summary"]) if ptr else None  # O(1)


def pid_gone(mine):  # O(1) the pid recorded for a background run, when that process no longer exists (POSIX only), else None
    if os.name == "nt":  # O(1)
        return None  # O(1)
    try:  # O(1)
        pid = int(mine.with_suffix(".pid").read_text(encoding="utf-8").strip())  # O(1)
        if pid <= 0:  # O(1)
            return None  # O(1)
        os.kill(pid, 0)  # O(1)
    except ProcessLookupError:  # O(1)
        return pid  # O(1)
    except (OSError, ValueError):  # no pid file, bad content or any other error: alive | O(1)
        return None  # O(1)
    return None  # O(1)


def summary_line(data):  # the last line of --wait: counts, mode and error | O(1)
    head = f"tests ({data['mode']})" if data.get("mode") else "tests"  # O(1)
    out = f"{head}: {data.get('passed', 0)} passed, {data.get('failed', 0)} failed"  # O(1)
    if data.get("skipped", 0) > 0:  # O(1)
        out += f", {data['skipped']} skipped"  # O(1)
    fails = data.get("failures") or []  # O(1)
    if data.get("failed", 0) > 0 and fails and not data.get("error"):  # failing names help only when the run itself worked | O(1)
        names = [str(f).split(": ", 1)[0].removeprefix("-::")[:60] for f in fails[:3]]  # O(1)
        out += f"; failing: {', '.join(names)}" + (f" (+{len(fails) - 3} more)" if len(fails) > 3 else "")  # O(1)
    if data.get("error"):  # O(1)
        out += f"; error: {str(data['error'])[:150]}"  # O(1)
    return out  # O(1)


def skip_non_test(paths):  # O(p) (test paths, non-test paths): docs, config and assets are no tests
    skipped = [p for p in paths if testcmd.is_non_test(p)]  # O(p)
    return [p for p in paths if p not in skipped], skipped  # O(p)


def non_test_reason(kept, skipped):  # O(p) the refusal text when --fast named only non-test files, else None
    return None if kept or not skipped else f"no test paths left: --fast named only non-test files ({', '.join(skipped)})"  # O(p)


def read_summary(mine):  # the summary, or None when missing or half-written | O(summary size)
    try:  # O(1)
        return json.loads(mine.read_text(encoding="utf-8"))  # O(summary size)
    except (OSError, ValueError):  # O(1)
        return None  # O(1)


def newest_run(mine, data):  # O(1) the summary a later run of mine's task started, else None
    task, stem = data.get("task"), run_stem(mine)  # O(1)
    if not task or not stem:  # O(1)
        return None  # O(1)
    try:  # O(1)
        ptr = json.loads(Path(mine).parent.joinpath(f"{stem}-{task}.latest").read_text(encoding="utf-8"))  # O(1)
        other = Path(ptr["summary"])  # O(1)
        later = float(ptr.get("started", 0)) > float(data.get("started", 0))  # O(1)
    except (OSError, ValueError, KeyError, TypeError):  # O(1)
        return None  # O(1)
    return other if later and other.resolve() != Path(mine).resolve() else None  # O(1)


def wait_background(a):  # O(timeout / POLL_SECONDS) polls
    mine = wait_target(a)  # O(1)
    if mine is None:  # O(1)
        print("run_tests: no background run to wait for", file=sys.stderr)  # O(1)
        return 2  # O(1)
    limit = a.timeout if a.timeout is not None else DEFAULT_WAIT  # O(1)
    deadline = time.monotonic() + limit  # O(1)
    redirected = False  # O(1)
    while True:  # O(timeout / POLL_SECONDS) iterations
        data = read_summary(mine)  # missing or half-written (non-atomic fs): not yet | O(summary size)
        if data is not None:  # O(1)
            newest = None if redirected else newest_run(mine, data)  # O(1)
            if newest is None:  # O(1)
                break  # O(1)
            print(f"run_tests: {mine} is an earlier run of {data['task']}; waiting on its newest run {newest}", file=sys.stderr)  # O(1)
            mine, redirected = newest, True  # O(1)
            continue  # O(1)
        dead = pid_gone(mine)  # O(1)
        if dead is not None and not mine.exists():  # one more look: the child may have written it just before exiting | O(1)
            reason = f"background run ended without a summary (pid {dead}); log {mine.with_suffix('.log')}"  # O(1)
            print(f"run_tests: {reason}", file=sys.stderr)  # O(1)
            write_summary(mine, "full", {"passed": 0, "failed": 0, "skipped": 0, "skipped_tests": []}, [], 0.0, error=reason)  # O(1)
            data = json.loads(mine.read_text(encoding="utf-8"))  # O(1)
            ptr = read_pointer(a.summary)  # O(1) the published summary the packet reads must carry the error too
            if ptr and Path(ptr["summary"]).resolve() == Path(mine).resolve():  # O(1)
                atomic_write(a.summary, mine.read_text(encoding="utf-8"))  # O(summary size)
            break  # O(1)
        if time.monotonic() >= deadline:  # O(1)
            data = read_summary(mine)  # a last look: the run may have finished during the final poll | O(summary size)
            if data is not None:  # O(1)
                break  # O(1)
            print(f"run_tests: timed out waiting for {mine}; log {mine.with_suffix('.log')}", file=sys.stderr)  # O(1)
            pid = None  # O(1)
            try:  # a live pid recorded for the run | O(1)
                pid = int(mine.with_suffix(".pid").read_text(encoding="utf-8").strip())  # O(1)
            except (OSError, ValueError):  # O(1)
                pass  # O(1)
            alive = f" (pid {pid} still running)" if pid and pid > 0 and pid_alive(mine) else ""  # O(1)
            note = mine.with_suffix(".lockwait")  # O(1)
            adm = admission_note(note)  # O(file)
            if adm:  # the run still waits for the admission command | O(1)
                print(f"run_tests: {mine} is waiting for the admission command {adm['admission']} (since {time.strftime('%H:%M:%S', time.localtime(adm.get('since') or time.time()))})", file=sys.stderr)  # O(1)
            elif note.exists():  # the run still waits for the full-suite lock | O(1)
                held = note_holder(note)  # O(file)
                print(f"run_tests: {mine} is waiting for the {lock_name(note)} full-suite lock (held by {wait_detail(held)})", file=sys.stderr)  # O(file)
            print(f"tests: no result yet after {limit:g} s{alive}; run again: {wait_line(mine)[len('wait: '):]}", file=sys.stderr)  # O(1)
            return 2  # O(1)
        time.sleep(POLL_SECONDS)  # O(1)
    print(json.dumps(data, ensure_ascii=False, indent=1))  # O(summary size)
    sys.stdout.flush()  # O(1)
    if data.get("output"):  # O(1)
        print(f"output: {data['output']}", file=sys.stderr)  # O(1)
    if data.get("warning"):  # O(1)
        print(f"warning: {data['warning']}", file=sys.stderr)  # O(1)
    print(summary_line(data), file=sys.stderr)  # O(1)
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
        data["error"] = error[:400]  # the placeholder refusal is longer than 200 chars | O(1)
    if CURRENT_TASK:  # a wait on an earlier run of the task finds its newest run (#507) | O(1)
        data["task"] = CURRENT_TASK  # O(1)
    if OUTPUT:  # the full output of this run (#501) | O(1)
        data["output"] = OUTPUT  # O(1)
    if WARNING:  # the platforms a full run did not build (#598) | O(1)
        data["warning"] = WARNING  # O(1)
    if started is not None:  # the packet closes only incidents logged before this run started (#101) | O(1)
        data["started"] = started  # O(1)
    p = Path(path)  # O(1)
    p.parent.mkdir(parents=True, exist_ok=True)  # O(1)
    tmp = p.with_name(p.name + ".tmp")  # O(1)
    WRITTEN.add(p.resolve())  # O(1)
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")  # O(k + sk) dumps + write
    tmp.replace(p)  # O(1) rename
    if mode == "full" and not error and run_stem(p.name) is None and not p.stem.endswith("-full"):  # a foreground full result keeps a copy no later run overwrites (#593) | O(1)
        atomic_write(p.with_name(f"{p.stem}-full{p.suffix}"), p.read_text(encoding="utf-8"))  # O(summary size)


def add_incidents(log, items, task=None, extra=None, raw=None):  # O(total c) + one locked append (no spawn in process)
    """items: (file, line, context, kind, resolution). A --task run stamps `task` on each entry; `extra` (a dict) is merged
    into every entry after `kind` and `task`; a kind outside
    incident.KINDS (`no-result`) is set after make_entry, as the hooks write theirs. Never spawns `incident add`,
    which takes neither `task` nor `no-result` (SUPERLITE_SL swaps only the launcher). `raw`: dicts appended unchanged after the built
    entries in the same append."""
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
        if extra:  # O(1)
            e.update(extra)  # O(1)
        entries.append(e)  # O(1)
    entries.extend(raw or [])  # O(r)
    try:  # O(1)
        inc.append(log, entries)  # O(total c) one locked write
    except OSError as err:  # O(1)
        print(f"warning: incidents not logged: {err}", file=sys.stderr)  # O(1)


def no_result_log(summary, command, cwd, rc, lines):  # O(L) + file write, keeps the newest 20 logs
    """Write `<dir of summary>/no-result-<time>-<ns>.log` (command, cwd, exit, the last 40 lines); return its absolute path, "" on OSError."""
    try:  # O(1)
        d = Path(summary).resolve().parent  # O(1)
        ns = time.time_ns()  # O(1)
        name = f"no-result-{time.strftime('%Y%m%dT%H%M%S', time.gmtime(ns // 10**9))}-{ns % 10**9:09d}.log"  # O(1)
        path = d / name  # O(1)
        atomic_write(path, "\n".join([f"command: {command}", f"cwd: {cwd}", f"exit: {rc}", "", *lines[-40:]]) + "\n")  # O(L)
        for old in sorted(d.glob("no-result-*.log"))[:-20]:  # O(n log n) n = logs kept
            old.unlink(missing_ok=True)  # O(1)
        return str(path)  # O(1)
    except OSError:  # O(1)
        return ""  # O(1)


def no_result_target(command, rc, log, cause=None):  # O(1) the feedback target of a no-result stop
    return (f"nothing collected: {cause}; " if cause else "") + f"exit {rc} from `{command[:200]}`; log {log or 'not written'}"  # O(1)


def signal_name(rc):  # O(1) the signal a return code means (-9 or 128+9 -> SIGKILL), None for an ordinary exit code
    num = -rc if rc < 0 else rc - 128 if 128 < rc <= 128 + 64 else 0  # O(1)
    try:  # O(1)
        name = signal.Signals(num).name if num else None  # O(1)
        return name if name in ("SIGKILL", "SIGTERM", "SIGHUP", "SIGINT") else None  # a crash signal is a real no-result | O(1)
    except ValueError:  # O(1)
        return None  # O(1)


def killed_reason(sig, rc):  # O(1) the summary error of a run whose test processes a signal ended, with the machine snapshot when known
    try:  # a snapshot failure never stops a run | O(registry + p)
        import machine_load  # noqa: PLC0415  # O(module)
        snap = machine_load.snapshot_text()  # O(registry + p)
    except Exception:  # noqa: BLE001  # O(1)
        snap = ""  # O(1)
    return f"test run killed by {sig} (exit {rc}): its test processes were killed, not failed" + (f"; {snap}" if snap else "")  # O(1)


def record_no_result(a, reason, command, rc, lines, tree=None, cause=None, sig=None):  # O(L + c) log the stop's trace, print its path, log the incident
    log = no_result_log(a.summary, command, str(tree) if tree else str(Path.cwd()), rc, lines)  # O(L)
    print(f"run_tests: no-result log {log}", file=sys.stderr)  # O(1)
    extra = {"target": no_result_target(command, rc, log, cause), "command": command[:300], "exit": rc, "log": log}  # O(1)
    if tree:  # O(1)
        extra["cwd"] = str(tree)  # O(1)
    if sig:  # O(1)
        extra["signal"] = sig  # O(1)
    add_incidents(a.log, [("-", 0, reason, "no-result", "open")], a.task, extra)  # a run with nothing to read is a stop, not a pass (#140) | O(c)


def resolve_passed(log, task, failures, files, green=False, full=False, started=None, covered=None):  # O(B + I + k) read the log once, one append (#180, #380)
    """Close open test-failure incidents logged before this run: a --task run closes its tests that pass now (`fixed: passed on a later run`);
    a green --task run also closes that task's `-` failures (`fixed: a green <task> run`) and re-logs other tasks' open ones there, so a sibling's red stays open; a green --full run without --task closes every
    run_tests failure (`fixed: the full suite passed`). The entry is what `sl incident resolve` writes (kind of the open entry, resolution `fixed`)."""
    p = Path(log)  # O(1)
    if not p.exists() or not (task and (files or covered) or green and (task or full)):  # O(1)
        return  # O(1)
    resolved = nt.sibling("pt_review").RESOLVED  # the resolutions the packet counts as closed; lazy | O(module)
    newest = {}  # location -> its newest non-verified entry, as the packet and `finish` count open | O(1)
    stretch = {}  # `-` location -> its non-verified entries after its last resolved one, in log order | O(1)
    for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():  # O(I) iterations; read O(B)
        try:  # O(1)
            e = json.loads(ln)  # O(w)
        except ValueError:  # O(1)
            continue  # O(1)
        if isinstance(e, dict) and "file" in e and "line" in e and e.get("kind") != "verified":  # O(1)
            newest[(e["file"], e["line"])] = e  # O(1)
            if e["file"] == "-":  # O(1)
                if str(e.get("resolution", "")).lower() in resolved:  # O(1)
                    stretch.pop((e["file"], e["line"]), None)  # O(1)
                else:  # O(1)
                    stretch.setdefault((e["file"], e["line"]), []).append(e)  # O(1)
    norm = lambda x: str(x).replace("\\", "/")  # noqa: E731 | O(len)
    ran = {norm(f) for f, (ok, _bad) in files.items() if ok}  # a file with no passing test (a collection error) closes nothing (#196) | O(F)
    cov = {norm(c) for c in covered} if covered and covered is not True else set()  # O(p) a counted run's covered files count as ran (#499)
    failing = {(norm(f), ctx.split(": ", 1)[0]) for f, _line, ctx in failures}  # (file, test name) still red | O(k)

    def before(e):  # O(1) logged before this run started
        ep = e.get("epoch")  # O(1)
        return started is None or isinstance(ep, bool) or not isinstance(ep, (int, float)) or ep < started  # O(1)

    def context(f, e):  # O(len) the closing context for the entry, or None to keep it open
        if e.get("kind") != "test-failure" or str(e.get("resolution", "")).lower() in resolved or not before(e):  # no rule closes an entry logged at or after this run's start | O(1)
            return None  # O(1)
        if task and e.get("task") == task and (norm(f) in ran or norm(f) in cov or covered is True and f != "-") and (norm(f), str(e.get("context", "")).split(": ", 1)[0]) not in failing:  # O(len)
            return "fixed: passed on a later run"  # O(1)
        if not task and green and full and e.get("agent") == "run_tests":  # O(1)
            return "fixed: the full suite passed"  # O(1)
        return None  # O(1)

    items = [(f, line, c, "test-failure", "fixed") for (f, line), e in newest.items() if (c := context(f, e))]  # O(I)
    raw = []  # O(1)
    if task and green:  # O(1)
        for (f, line), ents in stretch.items():  # O(I)
            closable = [e for e in ents if e.get("kind") == "test-failure" and e.get("task") == task and before(e)]  # O(len)
            keep = [e for e in ents if not (e.get("kind") == "test-failure" and e.get("task") == task and before(e))]  # O(len)
            if not closable or any(e.get("kind") != "test-failure" for e in keep):  # a re-logged stop would be counted twice | O(len)
                continue  # O(1)
            items.append((f, line, f"fixed: a green {task} run", "test-failure", "fixed"))  # O(1)
            last = {}  # (task, context) -> index of its newest kept entry | O(1)
            for i, e in enumerate(keep):  # O(len)
                last[(e.get("task"), e.get("context"))] = i  # O(1)
            raw.extend(keep[i] for i in sorted(last.values()))  # exact copies, log order | O(len log len)
    add_incidents(log, items, task, raw=raw)  # O(total c) one append


NODE_TEST_SUFFIXES = (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs")  # O(1) --fast paths of a non-Python project that are checked for existence


def missing_fast_paths(paths, python=True):  # O(p) the --fast paths that do not exist (a `::node` suffix is dropped; a `...` pattern is never checked; a non-Python project checks Node test files only)
    return [p for p in paths if "..." not in p and (python or p.split("::", 1)[0].endswith(NODE_TEST_SUFFIXES)) and not Path(p.split("::", 1)[0]).exists()]  # O(p)


def missing_line(paths, cwd, root, python=True):  # O(p) the usage-error text for missing --fast paths, else None
    gone = missing_fast_paths(paths, python)  # O(p)
    if not gone:  # O(1)
        return None  # O(1)
    return f"test path not found: {', '.join(gone)} (cwd {cwd}, root {root})"  # O(p)


NODE_RUNNERS = {"npm", "npx", "pnpm", "yarn", "bun", "bunx", "vitest", "jest", "mocha"}  # O(1)


def node_install_line(root, spec):  # O(m + f) the usage-error text for a Node runner without node_modules, else None
    if not spec or spec.get("python") or not spec.get("command") or (spec.get("setup") or "").strip():  # O(1)
        return None  # O(1)
    try:  # O(1)
        words = shlex.split(spec["command"])  # O(len command)
    except ValueError:  # O(1)
        return None  # O(1)
    while words and re.match(r"[A-Za-z_]\w*=", words[0]):  # O(w)
        words.pop(0)  # O(w)
    if not words or Path(words[0]).name not in NODE_RUNNERS:  # O(1)
        return None  # O(1)
    root = Path(root)  # O(1)
    try:  # O(1)
        pkg = json.loads((root / "package.json").read_text(encoding="utf-8"))  # O(size)
    except (OSError, ValueError):  # O(1)
        return None  # O(1)
    if not isinstance(pkg, dict):  # O(1)
        return None  # O(1)
    keys = ("dependencies", "devDependencies")  # O(1)
    if not any(isinstance(pkg.get(k), dict) and pkg[k] for k in keys):  # O(1)
        return None  # O(1)
    if (root / "node_modules").exists() or (root / ".pnp.cjs").exists() or (root / ".pnp.js").exists():  # O(1)
        return None  # O(1)
    import wave0  # lazy: only a Node project needs it | O(1) module load
    lock = next((cmd for name, cmd in wave0.LOCKFILES if name != "uv.lock" and (root / name).is_file()), "npm install")  # O(1)
    return f"node_modules missing in {root}: run {lock} first"  # O(1)


def _link_dir(src, dst):  # O(d) symlink dst to src (relative); True when the link changed
    if dst.is_symlink():  # O(1)
        try:  # a link loop must not crash the run | O(1)
            same = dst.resolve() == src.resolve()  # O(d)
        except (OSError, RuntimeError):  # O(1)
            same = False  # O(1)
        if same:  # already the source | O(1)
            return False  # O(1)
        try:  # O(1)
            dst.unlink()  # dangling, looping or wrong link | O(1)
        except OSError:  # O(1)
            return False  # O(1)
    elif dst.exists():  # a real folder in the tree stays | O(1)
        return False  # O(1)
    try:  # O(1)
        os.symlink(os.path.relpath(src, dst.parent.resolve()), dst)  # O(d)
    except OSError:  # O(1)
        return False  # the tree guard then names the tree | O(1)
    return True  # O(1)


def refresh_mtimes(tree, task, paths):  # O(P * size) touch the overlaid files whose bytes changed since the last run; returns the count touched
    tree = Path(tree)  # O(1)
    store = tree.parent / f"{task}.digests.json"  # O(1)
    try:  # O(1)
        old = json.loads(store.read_text(encoding="utf-8"))  # O(size)
        old = old if isinstance(old, dict) else {}  # O(1)
    except (OSError, ValueError):  # O(1)
        old = {}  # O(1)
    new, touched = {}, 0  # O(1)
    for p in paths:  # O(P) iterations
        f = tree / p  # O(1)
        if not f.is_file():  # O(1)
            continue  # O(1)
        try:  # O(1)
            new[p] = hashlib.sha256(f.read_bytes()).hexdigest()  # O(size)
            if old.get(p) != new[p]:  # new or changed: a build tool must see a newer file (#507) | O(1)
                os.utime(f, None)  # O(1)
                touched += 1  # O(1)
        except OSError:  # O(1)
            new.pop(p, None)  # O(1)
    try:  # O(1)
        store.write_text(json.dumps(new), encoding="utf-8")  # O(P)
    except OSError:  # O(1)
        pass  # O(1)
    return touched  # O(1)


def outside_tree(root, overlay):  # O(f * o) + two spawns: changed files of the main tree that are not in the task's tree
    copy, delete = trees.own_changes(root, trees.base_commit(root), ["**/*"])  # O(f)
    have = set(overlay)  # O(f)
    return sorted((set(copy) | set(delete)) - have)  # O(f log f)


def also_claims(a):  # O(c + k) ledger rulings for the --also files this run declares
    for raw in a.also:  # O(k) iterations
        f = Path(raw).as_posix() if not os.path.isabs(raw) else os.path.relpath(raw, Path.cwd()).replace(os.sep, "/") + ("/" if raw.endswith("/") else "")  # O(len)
        if ct.also_owned(a.ledger).get(f) == a.task:  # already claimed by this task | O(c)
            continue  # O(1)
        ct.append_ledger(a.ledger, f"- Ruling: {a.task} also commits {f} - {a.ruling}")  # O(1)
        print(f"run_tests: {a.task} also commits {f} (ledger ruling; commit_task {a.task} commits it)", file=sys.stderr)  # O(1)


def package_dirs(tree):  # O(F log F) the tree's package folders (posix, sorted), outside node_modules; [] on a git error
    try:  # O(1)
        names = trees.split_z(trees.git(tree, "ls-files", "-co", "--exclude-standard", "-z"))  # O(F)
    except (RuntimeError, OSError):  # not a git tree, or no git binary | O(1)
        return []  # O(1)
    out = set()  # O(1)
    for name in names:  # O(F)
        parts = name.split("/")  # O(len name)
        if parts[-1] == "package.json" and len(parts) > 1 and "node_modules" not in parts:  # O(len name)
            out.add("/".join(parts[:-1]))  # O(len name)
    return sorted(out)  # O(F log F)


def link_node_modules(root, tree, spec):  # O(F log F) link the root's and each package's node_modules into an isolated task tree; True when any link changed
    if (spec.get("setup") or "").strip():  # a setup command installs inside the tree itself | O(1)
        return False  # O(1)
    root, tree = Path(root).resolve(), Path(tree)  # O(1)
    if not (root / "package.json").is_file():  # O(1)
        return False  # O(1)
    changed = False  # O(1)
    for d in ["", *package_dirs(tree)]:  # O(F log F + P)
        src = root / d / "node_modules"  # O(1)
        if src.is_dir() and (tree / d).is_dir():  # O(1)
            changed = _link_dir(src, tree / d / "node_modules") or changed  # O(d)
    return changed  # O(1)


def has_swift(root):  # does the git tree (tracked or untracked, not ignored) hold Swift sources or an Xcode project; None when git cannot say | O(files)
    try:  # O(1)
        r = subprocess.run(["git", "-C", str(root), "-c", "core.quotepath=off", "ls-files", "-co", "--exclude-standard", "--",  # O(files)
                            "*.swift", "*.xcodeproj/*", "*.xcworkspace/*"], capture_output=True, text=True, timeout=30)  # O(1)
    except (OSError, subprocess.SubprocessError):  # O(1)
        return None  # O(1)
    if r.returncode != 0:  # O(1)
        return None  # O(1)
    return bool(r.stdout.strip())  # O(1)


def placeholder_line(root, spec):  # the refusal text for a test-cmd.json {only_testing} placeholder in a project without Swift files, else None | O(m + f)
    if not spec or spec.get("python") or spec.get("source") not in ("test-cmd.json", "user"):  # O(1)
        return None  # O(1)
    root = Path(root)  # O(1)
    cfg = testcmd.config_source(root)[0]  # O(m + f)
    if not isinstance(cfg, dict) or not any(isinstance(cfg.get(k), str) and "{only_testing}" in cfg[k] for k in ("test", "test_file")):  # O(1)
        return None  # O(1)
    if has_swift(root) is not False:  # O(files)
        return None  # O(1)
    user = spec.get("source") == "user"  # O(1)
    if user:  # O(1)
        where = f'the "{spec.get("language")}" entry of {spec.get("origin") or testcmd.shown(testcmd.user_config_path())}'  # O(1)
    else:  # O(1)
        where = ".superlite/test-cmd.json" if (root / ".superlite" / "test-cmd.json").is_file() else "the main checkout's .superlite/test-cmd.json"  # O(1)
    det = testcmd.detect(root)  # O(m + f)
    head = "test-cmd.json uses {only_testing}, the Xcode (Swift) placeholder, but this"  # O(1)
    if not det:  # O(1)
        return f"{head} project has no Swift files: in {where} use {{files}}"  # O(1)
    lang = det["language"]  # O(1)
    if lang == "python":  # O(1)
        return (f"{head} python project has no Swift files: in {where} write the python form {{files}} "  # O(1)
                '(e.g. "test_file": "python -m pytest {files}"), or delete that ' + ("entry" if user else "file") + ' so run_tests runs pytest itself')
    return f'{head} {lang} project has no Swift files: in {where} write the {lang} form {{files}} (e.g. "test_file": "{det["test_file"]}")'  # O(1)


def run_captured(cmd, limit=None, **kw):  # run_tree with both outputs in temp files, so a leftover child holding a pipe cannot block the run; LimitHit past `limit` seconds | O(o) + the run
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:  # O(1)
        try:  # O(1)
            r = pyrun.run_tree(cmd, stdout=out, stderr=err, timeout=limit, **kw)  # O(1) + the run
        except subprocess.TimeoutExpired:  # the process group is already killed | O(1)
            out.seek(0)  # O(1)
            err.seek(0)  # O(1)
            text = out.read().decode("utf-8", errors="replace") + err.read().decode("utf-8", errors="replace")  # O(o)
            raise LimitHit(limit, text, cmd if isinstance(cmd, str) else shlex.join(cmd)) from None  # O(o)
        out.seek(0)  # O(1)
        err.seek(0)  # O(1)
        return subprocess.CompletedProcess(cmd, r.returncode, out.read().decode("utf-8", errors="replace"),  # O(o)
                                           err.read().decode("utf-8", errors="replace"))  # O(o)


XCODEBUILD = re.compile(r"(?<![\w.-])xcodebuild(?=\s|$)")  # O(1) the xcodebuild word; a path before it is fine


SEGMENT_END = re.compile(r"[|;&\n]")  # O(1) a command segment ends at a pipe, semicolon, ampersand or newline
BUILDS = ("-scheme", "-xctestrun", "-testProductsPath")  # O(1) xcodebuild exits 65 on -derivedDataPath without one of these


def with_args(command, args):  # O(len command) the pass-through args joined onto the test command: end of each xcodebuild segment, else before the first single pipe, else the end
    if not args:  # O(1)
        return command  # O(1)
    text = shlex.join(args)  # O(len)
    parts = testcmd._segments(command)  # split at unquoted operators; 2>&1, &> and quoted | stay inside a segment | O(len)
    if XCODEBUILD.search(command):  # O(len)
        for i in range(0, len(parts), 2):  # operators sit at the odd indexes | O(segments)
            if not XCODEBUILD.search(parts[i]):  # O(len)
                continue  # O(1)
            core = parts[i].rstrip()  # O(len)
            parts[i] = core + " " + text + parts[i][len(core):]  # blanks before the operator stay after the args | O(len)
        return "".join(parts)  # O(len)
    for i in range(1, len(parts), 2):  # O(segments)
        if parts[i] == "|":  # the first single pipe outside quotes | O(1)
            return "".join(parts[:i]).rstrip() + " " + text + " " + "".join(parts[i:])  # O(len)
    return command + " " + text  # O(len)


def with_derived_data(command, tree):  # O(len command) build in the tree: -derivedDataPath after each xcodebuild whose segment names a scheme or test run
    flag = f"-derivedDataPath {shlex.quote(str(trees.derived_data_path(tree)))}"  # O(1)
    for m in reversed(list(XCODEBUILD.finditer(command))):  # last to first keeps earlier offsets valid | O(len)
        rest = command[m.end():]  # O(len)
        end = SEGMENT_END.search(rest)  # O(len)
        words = rest[:end.start() if end else len(rest)].split()  # O(len)
        if "-derivedDataPath" in words or not any(w in BUILDS for w in words):  # O(w)
            continue  # O(1)
        command = command[:m.end()] + " " + flag + command[m.end():]  # O(len)
    return command  # O(1)


MODULE_CACHE_HOURS = 24  # O(1) module cache entries older than this go when the disk is below the warn level
WARNED = ".superlite/derived-data-warned.json"  # O(1) a JSON list of commands already warned about
PROJECT_SKIP = {"node_modules", ".build", "DerivedData"}  # O(1) folders not searched for an Xcode project
SCRIPT_MAX = 1024 * 1024  # O(1) a script larger than this is not read


def has_xcode_project(root):  # an .xcodeproj or .xcworkspace in root or one or two folder levels below | O(entries)
    def scan(folder, depth):  # O(entries)
        try:  # O(1)
            entries = sorted(folder.iterdir())  # O(entries)
        except OSError:  # O(1)
            return False  # O(1)
        for e in entries:  # O(entries)
            if e.suffix in (".xcodeproj", ".xcworkspace"):  # O(1)
                return True  # O(1)
        if depth == 0:  # O(1)
            return False  # O(1)
        return any(scan(e, depth - 1) for e in entries if e.is_dir() and not e.name.startswith(".") and e.name not in PROJECT_SKIP)  # O(entries)
    return scan(Path(root), 2)  # O(entries)


def wrapped_build_warning(command, tree, root, language):  # the warning line for a wrapped xcodebuild the tree path cannot reach, else None | O(len + files)
    if language != "swift" or not has_xcode_project(root) or "SUPERLITE_DERIVED_DATA_PATH" in command:  # O(entries)
        return None  # O(1)
    try:  # O(1)
        words = shlex.split(command)  # O(len)
    except ValueError:  # O(1)
        words = command.split()  # O(len)
    for w in words:  # O(w)
        for base in (Path(tree), Path(root)):  # O(1)
            f = base / w  # an absolute word stays as it is | O(1)
            try:  # O(1)
                if f.is_file() and f.stat().st_size <= SCRIPT_MAX and "SUPERLITE_DERIVED_DATA_PATH" in f.read_text(encoding="utf-8", errors="replace"):  # O(size)
                    return None  # O(1)
            except OSError:  # O(1)
                continue  # O(1)
    shown = command if len(command) <= 200 else command[:200] + "..."  # O(1)
    return f'run_tests: WARNING: the test command `{shown}` has no xcodebuild word to rewrite and no script it names reads SUPERLITE_DERIVED_DATA_PATH, so it builds in the shared DerivedData; pass -derivedDataPath "$SUPERLITE_DERIVED_DATA_PATH" to xcodebuild in that script'  # O(1)


def warn_once(command, line):  # print the line unless the command was warned about before; remember it | O(warned)
    path = Path(WARNED)  # O(1)
    try:  # O(1)
        seen = json.loads(path.read_text(encoding="utf-8"))  # O(warned)
        seen = seen if isinstance(seen, list) else []  # O(1)
    except (OSError, ValueError):  # O(1)
        seen = []  # O(1)
    if command in seen:  # O(warned)
        return  # O(1)
    print(line, file=sys.stderr)  # O(1)
    try:  # O(1)
        path.parent.mkdir(parents=True, exist_ok=True)  # O(1)
        path.write_text(json.dumps(seen + [command]), encoding="utf-8")  # O(warned)
    except OSError:  # O(1)
        pass  # O(1)


def free_disk(a, keep):  # O(T) + drops: reap, then gate; a removal or a low level sweeps DerivedData and gates again. The refusal line, else None
    removed = 0  # O(1)
    try:  # cleanup is best effort | O(1)
        gone = trees.reap(".", ct.committed_tasks(a.ledger), trees.stopped_workers(Path(".superlite")), keep=keep)  # O(T + c)
        removed = len(gone)  # O(1)
        if gone:  # O(1)
            print(f"run_tests: removed {len(gone)} tree(s) nothing needs: {', '.join(gone)}", file=sys.stderr)  # O(1)
    except Exception:  # noqa: BLE001  # O(1)
        pass  # O(1)
    state, line = trees.disk_gate(Path("."))  # O(1)
    if removed or state != "ok":  # O(1)
        try:  # O(1)
            folders, size = trees.sweep_derived_data()  # O(folders + files)
            if folders:  # O(1)
                print(f"run_tests: removed {folders} orphaned DerivedData folder(s), {size / 1024 ** 3:.1f} GB", file=sys.stderr)  # O(1)
            if state != "ok":  # O(1)
                n, freed = trees.prune_module_cache(MODULE_CACHE_HOURS)  # O(files)
                print(f"run_tests: module cache: removed {n} entries older than {MODULE_CACHE_HOURS} h, {freed / 1024 ** 3:.1f} GB", file=sys.stderr)  # O(1)
        except Exception:  # noqa: BLE001  # O(1)
            pass  # O(1)
        state, line = trees.disk_gate(Path("."))  # only this result refuses or warns | O(1)
    if state == "refuse":  # O(1)
        return line  # O(1)
    if state == "warn":  # O(1)
        print(f"run_tests: {line}", file=sys.stderr)  # O(1)
    return None  # O(1)


def usage_error(a, label, reason):  # O(summary size) a usage error: stderr, zero summary, exit 2
    print(f"run_tests: {reason}", file=sys.stderr)  # O(1)
    write_summary(a.summary, label, {"passed": 0, "failed": 0, "skipped": 0, "skipped_tests": []}, [], 0.0, error=reason)  # O(1)
    publish_summary(a)  # O(summary size)
    print("0 0 0 0.0")  # O(1)
    return 2  # O(1)


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
    ap.add_argument("-m", "--marker", default=None, metavar="EXPR", help="pytest marker expression (a fast run; a test-cmd.json pytest command gets it appended)")  # O(1)
    ap.add_argument("--background", action="store_true",  # O(1)
                    help="start a detached run, print `summary: <path>`, exit 0")  # O(1)
    ap.add_argument("--wait", nargs="?", const="", default=None, dest="wait_path", metavar="PATH",  # O(1)
                    help="wait for PATH's run (the `summary:` line); bare: the latest background run")  # O(1)
    ap.add_argument("--timeout", type=float, default=None, help=f"--wait limit in seconds (default {DEFAULT_WAIT:.0f})")  # O(1)
    ap.add_argument("--limit", type=float, default=DEFAULT_LIMIT, help="wall-clock seconds before the test command tree is killed (default %(default)g; 0 = none)")  # O(1)
    ap.add_argument("--lock-wait", type=float, default=DEFAULT_LOCK_WAIT, help="seconds a full run waits for the machine-wide full-suite lock (default 3600; 0 = no limit)")  # O(1)
    ap.add_argument("--task", default=None, help="task id: compiled stacks run in .superlite/trees/<task> (own files only); incidents carry it and a green run closes its red ones")  # O(1)
    ap.add_argument("--also", nargs="+", action="extend", default=[], metavar="F", help="declare files this --task commits besides its Owns, before the run (ledger ruling; needs --task)")  # O(1)
    ap.add_argument("--ruling", default=ALSO_RULING, help=argparse.SUPPRESS)  # O(1)
    ap.add_argument("--plan", default=None, help=f"plan for --task Owns (default: the plan in .superlite/stable.json, else {nt.DEFAULT_PLAN})")  # O(1)
    ap.add_argument("--record", action="store_true", help="record a result run outside run_tests (needs --passed and --command), no test run")  # O(1)
    ap.add_argument("--passed", type=int, default=None, help="--record: tests that passed")  # O(1)
    ap.add_argument("--failed", type=int, default=0, help="--record: tests that failed (default 0)")  # O(1)
    ap.add_argument("--skipped", type=int, default=0, help="--record: tests that were skipped (default 0)")  # O(1)
    ap.add_argument("--seconds", type=float, default=0.0, help="--record: run time in seconds (default 0)")  # O(1)
    ap.add_argument("--command", default=None, help="--record: the command that ran them")  # O(1)
    ap.add_argument("--scope", default=None, help="--record: one word naming what ran (default external; never full or fast)")  # O(1)
    ap.add_argument("--run-id", default=None, help=argparse.SUPPRESS)  # O(1) set by --background
    ap.add_argument("--publish", default=None, help=argparse.SUPPRESS)  # O(1) set by --background
    ap.add_argument("--destination", action="append", default=[], metavar="D", help="xcodebuild destination to run (repeatable; `all` = every test-cmd.json destination); default: all on a full run, the first on a fast run")  # O(1)
    ap.add_argument("--env", action="append", default=[], metavar="K=V", help="set K=V in the test command's environment (repeatable; beats test-cmd.json env)")  # O(1)
    argv = list(sys.argv[1:] if argv is None else argv)  # O(len argv)
    tail = argv[argv.index("--") + 1:] if "--" in argv else []  # args after the first bare -- go to the test command | O(len argv)
    argv = argv[:argv.index("--")] if "--" in argv else argv  # O(len argv)
    a = ap.parse_args(argv)  # O(1)
    a.passthrough = tail  # O(1)
    a.cli_env = {}  # O(1)
    for item in a.env:  # O(e)
        key, eq, val = item.partition("=")  # O(len)
        if not eq or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):  # O(len)
            print(f"run_tests: --env needs K=V, got {item}", file=sys.stderr)  # O(1)
            return 2  # O(1)
        a.cli_env[key] = val  # O(1)
    if tail and (a.record or a.wait_path is not None):  # O(1)
        print("run_tests: pass-through args (after --) need a test run", file=sys.stderr)  # O(1)
        return 2  # O(1)
    WRITTEN.clear()  # O(1)
    global CURRENT_TASK, OUTPUT, WARNING  # O(1)
    OUTPUT = ""  # O(1)
    WARNING = ""  # O(1)
    CURRENT_TASK = a.task or None  # O(1)
    a.limit = a.limit if a.limit > 0 else None  # <= 0 means no limit | O(1)
    a.lock_wait = a.lock_wait if a.lock_wait > 0 else None  # O(1)
    a.started = time.time()  # before the runner reads any code: the summary's `started` (#101) | O(1)
    cwd = Path.cwd().resolve()  # O(1)
    a.cwd = cwd  # for the missing-path message, before to_root moves us | O(1)
    root = project_root(cwd) if a.wait_path is None else None  # --wait paths are absolute | O(d)
    if root is not None and root != cwd:  # O(1)
        to_root(a, argv, cwd, root)  # O(len argv + p)
    if a.scope is not None and not a.record:  # O(1)
        print("run_tests: --scope needs --record", file=sys.stderr)  # O(1)
        return 2  # O(1)
    if a.record:  # O(1)
        return record_run(a)  # O(1)
    if a.wait_path is not None:  # O(1)
        return wait_background(a)  # O(timeout / POLL_SECONDS)
    if a.background:  # O(1)
        try:  # a crash in resolve never breaks today's background start | O(1)
            gate = placeholder_line(Path.cwd(), testcmd.resolve(".", ()))  # O(m + f)
        except Exception:  # O(1)
            gate = None  # O(1)
        if gate:  # refused in the parent: nothing spawned, no summary | O(1)
            print(f"run_tests: {gate}", file=sys.stderr)  # O(1)
            return 2  # O(1)
        if not a.fast:  # a Node project without node_modules is refused here too | O(m + f)
            try:  # a crash in resolve never breaks today's background start | O(1)
                node_gone = node_install_line(Path.cwd(), testcmd.resolve(".", ()))  # O(m + f)
            except Exception:  # O(1)
                node_gone = None  # O(1)
            if node_gone:  # O(1)
                print(f"run_tests: {node_gone}", file=sys.stderr)  # O(1)
                return 2  # O(1)
        if a.fast:  # a missing path is refused here, not in the detached child | O(1)
            fast, skipped = skip_non_test([p for chunk in a.fast for p in nt.csv(chunk)])  # O(p)
            if non_test_reason(fast, skipped):  # nothing spawned | O(1)
                print(f"run_tests: {non_test_reason(fast, skipped)}", file=sys.stderr)  # O(p)
                return 2  # O(1)
            try:  # O(1)
                fast = expand_fast_paths(fast)  # O(p)
                spec = fast_spec(fast, quiet=True)  # O(m + f)
            except FileNotFoundError:  # left to the child | O(1)
                fast, spec = [], None  # O(1)
            except testcmd.UnknownTestName as e:  # refused in the parent: nothing spawned | O(1)
                print(f"run_tests: {e}", file=sys.stderr)  # O(1)
                return 2  # O(1)
            gone = missing_line(fast, a.cwd, Path.cwd(), spec["python"]) if spec and fast else None  # O(p)
            gone = gone or node_install_line(Path.cwd(), spec)  # O(m + f)
            if gone:  # O(1)
                print(f"run_tests: {gone}", file=sys.stderr)  # O(1)
                return 2  # O(1)
        return start_background(a, argv)  # O(len argv) + spawn
    if os.name != "nt":  # a killed run_tests must not leave its test processes running (#489) | O(1)
        def stop(num, _frame):  # O(1)
            raise Stopped(signal.Signals(num).name)  # O(1)
        signal.signal(signal.SIGTERM, stop)  # O(1)
        signal.signal(signal.SIGHUP, stop)  # O(1)
    try:  # O(1)
        return run(a)  # see run
    except LimitHit as e:  # O(1)
        secs = e.seconds  # O(1)
        reason = f"wall-clock limit: test run killed after {secs:g} s (run_tests --limit S; 0 = none)"  # O(1)
        print(f"run_tests: {reason}", file=sys.stderr)  # O(1)
        save_output(a, e.command, -9, e.text)  # O(len text)
        write_summary(a.summary, "fast" if narrowed(a) else "full", {"passed": 0, "failed": 0, "skipped": 0, "skipped_tests": []}, [], secs, error=reason)  # O(1)
        publish_summary(a)  # O(summary size)
        record_no_result(a, reason, e.command, -9, e.text.splitlines(), None)  # O(L + c)
        print(f"0 0 0 {secs:.1f}")  # O(1)
        return 2  # O(1)
    except LockBusy as e:  # O(1)
        reason = f"full-suite lock: still held by {holder_text(e.holder)} after {e.seconds:g} s (run_tests --lock-wait S; 0 = no limit)"  # O(1)
        print(f"run_tests: {reason}", file=sys.stderr)  # O(1)
        write_summary(a.summary, "full", {"passed": 0, "failed": 0, "skipped": 0, "skipped_tests": []}, [], 0.0, error=reason)  # O(1)
        publish_summary(a)  # O(summary size)
        print("0 0 0 0.0")  # O(1)
        return 2  # O(1)
    except full_gate.AdmissionBusy as e:  # O(1)
        reason = f"admission: {e.name} did not start the full run after {e.seconds:g} s (run_tests --lock-wait S; 0 = no limit)"  # O(1)
        print(f"run_tests: {reason}", file=sys.stderr)  # O(1)
        write_summary(a.summary, "full", {"passed": 0, "failed": 0, "skipped": 0, "skipped_tests": []}, [], 0.0, error=reason)  # O(1)
        publish_summary(a)  # O(summary size)
        print("0 0 0 0.0")  # O(1)
        return 2  # O(1)
    except BaseException as e:  # a crash still leaves a (red) summary and the zero line | O(1)
        if isinstance(e, SystemExit) and e.code in (0, None):  # O(1)
            raise  # O(1)
        full = isinstance(e, OSError) and e.errno == errno.ENOSPC  # a full disk is one clear line, not a traceback (#574) | O(1)
        full_reason = f"disk full (ENOSPC): {e.strerror}" + (f": {e.filename}" if e.filename else "") + "; run sl trees clean and free space, then rerun" if full else ""  # O(1)
        try:  # the summary may not fit either | O(1)
            if Path(a.summary).resolve() not in WRITTEN:  # a result already written stays | O(1)
                write_summary(a.summary, "fast" if narrowed(a) else "full", {"passed": 0, "failed": 0, "skipped": 0,  # O(1)
                                                                        "skipped_tests": []}, [], 0.0,  # O(1)
                              error=full_reason or (f"run_tests stopped by {e}; its test processes were killed" if isinstance(e, Stopped) else f"run_tests crashed: {e!r}"[:200]))  # O(1)
                publish_summary(a)  # O(summary size)
                print("0 0 0 0.0")  # O(1)
        except OSError:  # O(1)
            if not full:  # O(1)
                raise  # O(1)
        if full:  # O(1)
            print(f"run_tests: {full_reason}", file=sys.stderr)  # O(1)
            return 2  # O(1)
        if isinstance(e, Stopped):  # no traceback for a signal | O(1)
            print(f"run_tests: stopped by {e}", file=sys.stderr)  # O(1)
            return 2  # O(1)
        if not isinstance(e, Exception):  # O(1)
            raise  # O(1)
        traceback.print_exc()  # O(depth)
        print(f"run_tests: crashed: {e!r}", file=sys.stderr)  # O(1)
        return 2  # O(1)


def record_run(a):  # a full result the agent ran outside run_tests: reports only, closes no incidents | O(1)
    for flag, val in (("--passed", a.passed), ("--command", a.command)):  # O(1)
        if val is None or val == "":  # O(1)
            print(f"run_tests: --record needs {flag}", file=sys.stderr)  # O(1)
            return 2  # O(1)
    for flag, val in (("--passed", a.passed), ("--failed", a.failed), ("--skipped", a.skipped), ("--seconds", a.seconds)):  # O(1)
        if val < 0:  # O(1)
            print(f"run_tests: {flag} must be >= 0", file=sys.stderr)  # O(1)
            return 2  # O(1)
    scope = "external" if a.scope is None else a.scope  # O(1)
    if not re.fullmatch(r"\w+", scope) or scope in ("full", "fast"):  # O(1)
        print(f"run_tests: --scope must be one word other than full or fast (a recorded run never counts as the full run): {scope}", file=sys.stderr)  # O(1)
        return 2  # O(1)
    write_summary(a.summary, "recorded", {"passed": a.passed, "failed": a.failed, "skipped": a.skipped, "skipped_tests": []}, [], a.seconds, started=a.started)  # O(1)
    data = json.loads(Path(a.summary).read_text(encoding="utf-8"))  # O(1)
    data["scope"] = scope  # O(1)
    data["recorded"] = a.command[:200]  # O(1)
    atomic_write(a.summary, json.dumps(data, ensure_ascii=False, indent=1) + "\n")  # O(1)
    pointer_path(a.summary).unlink(missing_ok=True)  # an older background run must not shadow the recorded result | O(1)
    ct.append_ledger(a.ledger, f"- tests {scope} passed={a.passed} failed={a.failed} skipped={a.skipped} seconds={round(a.seconds, 1):g} recorded")  # O(1)
    print(f"{a.passed} {a.failed} {a.skipped} {a.seconds:.1f}")  # O(1)
    return 0  # O(1)


FLEET_PREFIX = "SUPERLITE_FLEET_"  # O(1) a fleet pane (lead, worker) exports these; no test subprocess inherits them (#219)


def child_env(extra=None):  # O(env) the test subprocess environment: os.environ without SUPERLITE_FLEET_*, then extra on top (test-cmd.json env wins)
    env = {k: v for k, v in os.environ.items() if not k.startswith(FLEET_PREFIX)}  # O(env)
    env.update(extra or {})  # O(e)
    return env  # O(1)


def root_superlite(s, root, raw=False):  # O(len s) a tree has no .superlite/ (git-ignored): point its word-initial uses at the project root
    def at(m):  # O(1) raw root for env values and inside quotes, shell-quoted otherwise
        quoted = m.start() > 0 and s[m.start() - 1] in "\"'"  # O(1)
        return (str(root) if raw or quoted else shlex.quote(str(root))) + "/.superlite/"  # O(1)
    return re.sub(r"(?<![\w./~-])\.superlite/", at, s)  # O(len s)


def chosen_destinations(a, spec, label):  # O(d) the destinations to run: --destination flags (`all` = every configured one), else all configured on a full run, the first on a fast run
    configured = list(spec.get("destinations") or [])  # O(d)
    flags = list(getattr(a, "destination", None) or [])  # O(d)
    if flags:  # O(d)
        return [x for f in flags for x in (configured if f == "all" else [f])]  # O(d)
    return configured if label == "full" else configured[:1]  # O(d)


def platform_warning(declared, built):  # O(d + b) the warning text for declared platforms a full run did not build, else ""
    missing = [p for p in declared if p not in built]  # O(d * b)
    if not missing:  # O(1)
        return ""  # O(1)
    where = f"built for {', '.join(built)} only" if built else "built for no declared platform"  # O(b)
    return (f"Package.swift declares {', '.join(declared)}; this full run {where}; "  # O(d)
            'add "destinations" to .superlite/test-cmd.json, e.g. ["platform=macOS", "platform=iOS Simulator,name=iPhone 16"]')  # O(1)


def behind_main():  # O(1) spawns: (commits, branch) when this linked worktree lacks commits of the main checkout's HEAD, else None
    try:  # O(1)
        main = testcmd._main_checkout_root(Path("."))  # O(1)
        if main is None:  # O(1)
            return None  # O(1)
        sha = subprocess.run(["git", "-C", str(main), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=10)  # O(1)
        branch = subprocess.run(["git", "-C", str(main), "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True, timeout=10)  # O(1)
        count = subprocess.run(["git", "rev-list", "--count", f"HEAD..{sha.stdout.strip()}"], capture_output=True, text=True, timeout=10)  # O(commits)
        if sha.returncode or branch.returncode or count.returncode or not sha.stdout.strip():  # a git error | O(1)
            return None  # O(1)
        n = int(count.stdout.strip())  # O(1)
    except (OSError, ValueError, subprocess.SubprocessError):  # O(1)
        return None  # O(1)
    return (n, branch.stdout.strip()) if n > 0 else None  # O(1)


def run_other(a, spec, paths, label, cwd=None, gate=None):  # one runner command (any language) | O(X + o) + the run
    """Run the resolved non-Python command: JUnit when the runner wrote one, else exit code plus output parsing."""
    if getattr(a, "passthrough", None):  # O(1)
        spec = {**spec, "command": with_args(spec["command"], a.passthrough)}  # O(len)
    with tempfile.TemporaryDirectory() as tmp:  # O(1)
        xml_path = Path(tmp) / "junit.xml"  # O(1)
        root = Path.cwd().resolve()  # main chdir'd to the project root | O(1)
        sub = lambda s: root_superlite(s, root) if cwd else s  # noqa: E731 | O(len)
        sub = (lambda f: lambda s: f(s).replace("{junit}", str(xml_path)))(sub)  # noqa: E731 | O(len)
        subenv = lambda s: (root_superlite(s, root, raw=True) if cwd else s).replace("{junit}", str(xml_path))  # noqa: E731 | env is never shell-parsed | O(len)
        env = child_env({**{k: subenv(str(v)) for k, v in (spec.get("env") or {}).items()}, **(getattr(a, "cli_env", None) or {})})  # --env wins over the config | setup and command, no SUPERLITE_FLEET_* (#219) | O(env)
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
        dests = chosen_destinations(a, spec, label)  # O(d)
        if dests and not XCODEBUILD.search(spec["command"]):  # O(len)
            print(f"run_tests: WARNING: destinations need an xcodebuild command; ran `{spec['command']}` once", file=sys.stderr)  # O(len)
            dests = []  # O(1)
        runs = [(d, testcmd.with_destination(sub(spec["command"]), d) or sub(spec["command"])) for d in dests] or [(None, sub(spec["command"]))]  # O(d * len)
        gui = gui_session.preflight([c for _, c in runs]) if spec.get("lock") is not False else None  # a macOS xcodebuild test outside the desktop session (#561) | O(d * len)
        if gui:  # O(1)
            return usage_error(a, label, gui)  # O(summary size)
        marker = Path(cwd) / ".superlite-setup.done" if cwd else Path(".superlite") / "setup.done"  # setup runs once per run directory (per tree) | O(1)
        if spec["setup"] and not marker.exists():  # O(1)
            (gate.run if gate else run_captured)(sub(spec["setup"]), limit=a.limit, shell=True, env=env, cwd=cwd)  # O(o)
            marker.parent.mkdir(parents=True, exist_ok=True)  # O(1)
            marker.write_text("ok\n", encoding="utf-8")  # O(1)
        global WARNING  # O(1)
        if label == "full":  # a full run names the declared platforms it did not build (#598) | O(entries)
            declared = testcmd.declared_platforms(root)  # O(entries)
            built = [p for p in dict.fromkeys(testcmd.destination_platform(d) for d in dests) if p] if dests else testcmd.command_platforms(spec["command"])  # O(d)
            WARNING = platform_warning(declared, built)  # O(d)
            if WARNING:  # O(1)
                print(f"run_tests: WARNING: {WARNING}", file=sys.stderr)  # O(1)
        t0, w0 = time.monotonic(), gate.waited if gate else 0.0  # O(1)
        results = [(d, (gate.run if gate else run_captured)(c, limit=a.limit, shell=True, env=env, cwd=cwd)) for d, c in runs]  # one run per destination, in order | O(o) + the runs
        seconds = time.monotonic() - t0 - ((gate.waited - w0) if gate else 0.0)  # the admission wait is not test time | O(1)
        texts = [(d, (x.stdout or "") + (x.stderr or "")) for d, x in results]  # O(o)
        text = "".join(f"run_tests: destination {d}\n{t}" if d else t for d, t in texts)  # O(o)
        rc0 = next((x.returncode for _, x in results if x.returncode), 0)  # the first non-zero exit | O(d)
        r = subprocess.CompletedProcess(runs[0][1], rc0, text, "")  # O(1)
        save_output(a, " ; ".join(c for _, c in runs), r.returncode, text)  # O(o)
        if alt and not literal.exists():  # O(1)
            literal = alt  # O(1)
        reports = [] if len(results) > 1 else junit_reports(xml_path, literal)  # the main report plus sidecars; several destinations are read from their output | O(n log n)
        report = None  # O(1)
        if reports:  # O(1)
            counts, failures, files = merge_junit(reports)  # O(X + T*d)
            if sum(counts[k] for k in ("passed", "failed", "skipped")):  # nothing parseable: fall back to the exit code | O(1)
                report = reports  # O(1)
        if report is None:  # no JUnit: exit code plus the last 40 lines, failing names best effort | O(o)
            if len(results) > 1:  # one parse per destination, merged (#598) | O(o)
                p = testcmd.merge_parsed([(d, testcmd.parse_output(strip_ansi(t), x.returncode)) for (d, t), (_, x) in zip(texts, results)])  # O(o)
            else:  # O(1)
                p = testcmd.parse_output(strip_ansi(text), r.returncode)  # O(o)
            counts = {"passed": p["passed"], "failed": p["failed"], "skipped": p["skipped"], "skipped_tests": []}  # O(1)
            last = next((ln for ln in reversed(p["tail"]) if ln.strip()), "no output")  # O(1)
            files = {}  # O(1)
            reasons = p.get("reasons", {})  # pytest ids with their message and line (B119) | O(1)
            failures = []  # O(1)
            for n in p["names"]:  # a pytest id whose file exists is placed there, else it stays unlocated | O(k)
                msg, line = reasons[n] if n in reasons else (None, 0)  # O(1)
                path, _, rest = n.partition("::")  # O(len)
                if n in reasons and path and ((Path(cwd) if cwd else root) / path).is_file():  # O(1)
                    failures.append((path, line, f"{rest}: {msg or 'failed'}" if rest else msg or "failed"))  # O(1)
                    files.setdefault(path, [0, 0])[1] += 1  # O(1)
                else:  # O(1)
                    failures.append(("-", 0, f"{n}: {msg or 'failed'}" if n in reasons else f"{n}: failed"))  # O(1)
            if XCODE_OUT.search(text) or spec.get("language") == "swift":  # xcodebuild output: failures with file and line (#499) | O(o)
                sites = failure_sites.failures(strip_ansi(text), str(Path(cwd) if cwd else root), paths, p["names"])  # O(o + f*n)
                if sites:  # O(1)
                    failures = sites  # O(1)
                    for f, _line, _ctx in sites:  # a located file counts its failed tests | O(k)
                        if f != "-":  # O(1)
                            files.setdefault(f, [0, 0])[1] += 1  # O(1)
            covered = None  # O(1)
            if p["counted"]:  # a counted run (it compiled; an XCTest failure line is no build error) covers its files: a full run all, a fast run the Swift files it was limited to (#499) | O(p)
                covered = True if label == "full" else [f.replace("\\", "/") for f in paths if f.replace("\\", "/").endswith(".swift")] if label == "fast" else None  # O(p)
            if r.returncode and gui_session.runner_unreachable(strip_ansi(text)):  # xcodebuild could not reach its test runner: no result, not a red test (#561) | O(o)
                reason = gui_session.unreachable_reason(gui_session.session_kind() if spec.get("lock") is not False else None)  # O(1)
                print(f"run_tests: {reason}", file=sys.stderr)  # O(1)
                write_summary(a.summary, label, {"passed": 0, "failed": 0, "skipped": 0, "skipped_tests": []}, [], seconds, error=reason)  # O(1)
                publish_summary(a)  # O(summary size)
                record_no_result(a, reason, sub(spec["command"]), r.returncode, [*p["tail"]], cwd)  # O(40 + c)
                print(f"0 0 0 {seconds:.1f}")  # O(1)
                return 2  # O(1)
            sig = signal_name(r.returncode) if r.returncode and not (p["counted"] or p["passed"] or p["skipped"] or p["names"]) else None  # a kill with no result at all | O(1)
            if sig:  # the test processes were killed from outside: no result, not a failing test (#548) | O(1)
                reason = killed_reason(sig, r.returncode)  # O(registry + p)
                print(f"run_tests: {reason}", file=sys.stderr)  # O(1)
                write_summary(a.summary, label, {"passed": 0, "failed": 0, "skipped": 0, "skipped_tests": []}, [], seconds, error=reason)  # O(1)
                publish_summary(a)  # O(summary size)
                record_no_result(a, reason, sub(spec["command"]), r.returncode, [*p["tail"]], cwd, sig=sig)  # O(40 + c)
                print(f"0 0 0 {seconds:.1f}")  # O(1)
                return 2  # O(1)
            if r.returncode in (126, 127) and not (p["counted"] or p["names"]):  # the shell could not start the command: no result, not a failing test | O(1)
                reason = f"test command could not run (exit {r.returncode}: {'not executable' if r.returncode == 126 else 'command not found'}): {last}"[:300]  # O(1)
                print(f"run_tests: {reason}", file=sys.stderr)  # O(1)
                write_summary(a.summary, label, {"passed": 0, "failed": 0, "skipped": 0, "skipped_tests": []}, [], seconds, error=reason)  # O(1)
                publish_summary(a)  # O(summary size)
                record_no_result(a, reason, sub(spec["command"]), r.returncode, [*p["tail"]], cwd)  # O(40 + c)
                print(f"0 0 0 {seconds:.1f}")  # O(1)
                return 2  # O(1)
            if len(results) > 1:  # each red destination is named (#598) | O(d)
                failures += [("-", 0, f"destination {d}: exit {x.returncode}") for d, x in results if x.returncode]  # O(d)
            elif dests and r.returncode:  # O(1)
                failures += [("-", 0, f"destination {dests[0]}: exit {r.returncode}")]  # O(1)
            if r.returncode and not failures:  # a red exit with no names: name the command | O(1)
                failures = [("-", 0, f"exit code {r.returncode} from `{spec['command']}`: {last}"[:200])]  # O(1)
            if r.returncode and p["error"]:  # a compile error leads the failures | O(1)
                failures.insert(0, ("-", 0, f"build error: {p['error']}"[:160]))  # O(1)
            tail_set = {x.strip() for x in p["tail"]}  # O(40)
            kept = [x for x in (p["error"] if r.returncode else "", p["marker"]) if x and x not in tail_set]  # the error and marker may sit above the last 40 lines | O(40)
            atomic_write(Path(a.summary).with_name("test-output.log"), "\n".join([*kept, *p["tail"]]) + "\n")  # O(40)
            if not r.returncode and spec.get("source") == "plan" and not p["counted"]:  # a green cmd with no readable count is one passed test | O(1)
                counts["passed"] = 1  # O(1)
            red_empty = bool(r.returncode and p["empty"] and not (p["counted"] or p["names"]))  # a red exit whose runner says no test matched (#597) | O(1)
            if red_empty or (not r.returncode and not (p["passed"] or counts["passed"] or p["failed"] or p["skipped"] or p["names"])):  # the runner counted zero tests: a stop, not a pass (#240) | O(1)
                runner = f"; runner: {p['empty']}"[:120] if p["empty"] else ""  # the runner's own "no tests" line | O(1)
                reason = f"no tests ran: exit {r.returncode} from `{spec['command']}` with no test count; its filter may select nothing"[:300 - len(runner)] + runner  # O(1)
                print(f"run_tests: {reason}", file=sys.stderr)  # O(1)
                write_summary(a.summary, label, {"passed": 0, "failed": 0, "skipped": 0, "skipped_tests": []}, [], seconds, error=reason)  # O(1)
                publish_summary(a)  # O(summary size)
                record_no_result(a, reason, sub(spec["command"]), r.returncode, [*kept, *p["tail"]], cwd)  # O(40 + c)
                print(f"0 0 0 {seconds:.1f}")  # O(1)
                return 1  # O(1)
    if label == "full" and spec.get("lock") is False and r.returncode:  # a red remote run in a worktree behind the main checkout may only lack its fix (#638) | O(1)
        behind = behind_main()  # O(1)
        if behind:  # O(1)
            hint = f"this worktree lacks {behind[0]} commit{'s' if behind[0] != 1 else ''} of {behind[1]}; run `git merge {behind[1]}` before trusting this red run"  # O(1)
            WARNING = f"{WARNING}; {hint}" if WARNING else hint  # O(1)
            print(f"run_tests: WARNING: {hint}", file=sys.stderr)  # O(1)
    return finish_run(a, label, counts, failures, files, seconds, r.returncode, covered=covered if report is None else None)  # O(k + F)


# the Swift -only-testing mapping lives in testcmd.py: one by-target-membership mapping for every caller (#431)
swift_test_targets = testcmd.swift_test_targets  # O(1)
owning_test_target = testcmd.owning_test_target  # O(1)
xcode_only_testing = testcmd.xcode_only_testing  # O(1)


def fast_spec(paths: list[str], quiet: bool = False):  # testcmd.resolve plus its notes under a `run_tests:` prefix | O(m + f)
    cfg = testcmd.config_source(Path("."))[0]  # O(m + f)
    tpl = [cfg.get(k) for k in ("test_file", "test")] if cfg else []  # O(1)
    if not paths or not any(isinstance(t, str) and "{only_testing}" in t for t in tpl):  # O(1)
        return testcmd.resolve(".", paths)  # O(m + f)
    notes: list[str] = []  # O(1)
    spec = testcmd.resolve(".", paths, notes=notes)  # O(m + f)
    if not quiet:  # O(1)
        for n in notes:  # O(notes)
            print(f"run_tests: {n}", file=sys.stderr)  # O(1)
    return spec  # O(1)


def marker_spec(spec, paths, marker):  # O(m + f) (spec, note) running `-m MARKER` for a test command that is not pytest: the config's test_file, else the local pytest runner; None for neither
    cfg = testcmd.config_source(Path("."))[0]  # O(m + f)
    template = cfg.get("test_file") if cfg else None  # O(1)
    if isinstance(template, str) and template:  # O(1)
        files = " ".join(shlex.quote(x) for x in (paths or testcmd.python_full_args(Path("."))))  # O(p)
        marked = with_marker(template.replace("{files}", files), marker)  # O(len)
        if marked is not None:  # O(1)
            return {**spec, "command": marked}, f"run_tests: -m runs the test_file command `{marked}`, not the remote test command"  # O(1)
    language = (cfg or {}).get("language") or (testcmd.detect(Path(".")) or {}).get("language")  # O(m + f)
    if language != "python":  # O(1)
        return None  # O(1)
    local = {"language": "python", "python": True, "command": None, "junit": "", "env": spec.get("env") or {}, "setup": "", "source": spec.get("source"), "origin": spec.get("origin"), "isolate": False, "lock": True, "destinations": []}  # O(1)
    return local, "run_tests: -m runs the local pytest runner, not the remote test command"  # O(1)


def with_marker(command, marker):  # O(len command) the pytest command plus `-m MARKER` (shell-quoted), None when the command is not pytest
    try:  # O(1)
        lex = shlex.shlex(command, posix=True, punctuation_chars=True)  # O(1)
        lex.whitespace_split = True  # O(1)
        words = list(lex)  # O(len)
    except ValueError:  # O(1)
        return None  # O(1)
    names = [Path(w.replace("\\", "/")).name for w in words]  # O(len)
    hits = [i for i, n in enumerate(names) if n in ("pytest", "py.test")]  # `python -m pytest` has the word pytest too | O(len)
    if not hits:  # O(1)
        return None  # O(1)
    if any(w and all(c in "();<>|&" for c in w) for w in words[hits[0] + 1:]):  # a shell operator or redirect after pytest: the marker would reach another program | O(len)
        return None  # O(1)
    return f"{command} -m {shlex.quote(marker)}"  # O(1)


def addopts_text(root, name):  # O(file) the addopts of one pytest config file as argv words: (file owns the pytest config, words)
    path = Path(root) / name  # O(1)
    if not path.is_file():  # O(1)
        return False, []  # O(1)
    try:  # O(1)
        text = path.read_text(encoding="utf-8")  # O(file)
        if name == "pyproject.toml":  # O(1)
            import tomllib  # O(1)
            tbl = tomllib.loads(text).get("tool", {}).get("pytest", {}).get("ini_options")  # O(file)
            if not isinstance(tbl, dict):  # O(1)
                return False, []  # O(1)
            val = tbl.get("addopts", "")  # O(1)
        else:  # O(1)
            cp = configparser.ConfigParser(interpolation=None, strict=False)  # O(1)
            cp.read_string(text)  # O(file)
            section = "tool:pytest" if name == "setup.cfg" else "pytest"  # O(1)
            if not cp.has_section(section):  # an existing pytest.ini wins even without a section | O(1)
                return name == "pytest.ini", []  # O(1)
            val = cp.get(section, "addopts", fallback="")  # O(1)
        return True, [str(x) for x in val] if isinstance(val, list) else shlex.split(str(val))  # O(len)
    except (OSError, ValueError, ImportError, AttributeError, TypeError, configparser.Error):  # an unreadable config still owns the settings | O(1)
        return True, []  # O(1)


def addopts_marker(root):  # O(file) (marker expression, config file name) of the `-m` in the project's pytest addopts, else None
    for name in ("pytest.ini", "pyproject.toml", "tox.ini", "setup.cfg"):  # pytest's own precedence | O(1)
        found, words = addopts_text(root, name)  # O(file)
        if not found:  # O(1)
            continue  # O(1)
        expr = None  # O(1)
        for i, w in enumerate(words):  # the last -m wins | O(len)
            if w == "-m" and i + 1 < len(words):  # O(1)
                expr = words[i + 1]  # O(1)
            elif w.startswith("-m") and len(w) > 2 and not w.startswith("--"):  # O(1)
                expr = w[2:]  # O(1)
        return (expr, name) if expr else None  # O(1)
    return None  # O(1)


def file_markers(path):  # O(file) the `<x>.mark.X` and `mark.X` names a test file uses (decorators, pytestmark); empty when unreadable or unparsable
    try:  # O(1)
        tree = ast.parse(Path(path).read_text(encoding="utf-8"))  # O(file)
    except (OSError, SyntaxError, ValueError):  # O(1)
        return set()  # O(1)
    found = set()  # O(1)
    for n in ast.walk(tree):  # O(nodes)
        if isinstance(n, ast.Attribute) and ((isinstance(n.value, ast.Attribute) and n.value.attr == "mark")
                                             or (isinstance(n.value, ast.Name) and n.value.id == "mark")):  # `<x>.mark.NAME` and a bare `mark.NAME` | O(1)
            found.add(n.attr)  # O(1)
    return found  # O(1)


def honoured_marker(paths, root="."):  # O(p + files) (-m expression, notice) for test files marked with a marker the addopts `-m` deselects, else None
    found = addopts_marker(root)  # O(file)
    if not found:  # O(1)
        return None  # O(1)
    expr, cfg = found  # O(1)
    negated = list(dict.fromkeys(re.findall(r"\bnot\s+(\w+)", expr)))  # O(len expr) EXPR's order
    used, first = set(), None  # O(1)
    for p in paths:  # O(p)
        f = p.split("::")[0]  # O(len p)
        full = Path(root) / f  # O(1)
        if not f.endswith(".py") or not full.is_file():  # O(1)
            continue  # O(1)
        hit = set(file_markers(full)) & set(negated)  # O(file)
        if hit:  # O(1)
            used |= hit  # O(1)
            first = first or (f, hit)  # O(1)
    if not used:  # O(1)
        return None  # O(1)
    names = [m for m in negated if m in used]  # O(1)
    new = " or ".join([*names, f"({expr})"])  # O(1)
    shown = ", ".join(m for m in negated if m in first[1])  # O(1)
    return new, f"run_tests: {first[0]} is marked {shown}, which addopts -m '{expr}' in {cfg} deselects; running with -m '{new}'"  # O(1)


def nothing_collected(output, paths, marker, root):  # O(len output + file) why a pytest run (exit 5) collected nothing
    m = re.search(r"(\d+) deselected", output)  # O(len output)
    if m:  # O(1)
        n = m.group(1)  # O(1)
        if marker:  # O(1)
            return f"all {n} collected tests deselected by -m '{marker}'"  # O(1)
        found = addopts_marker(root)  # O(file)
        if found:  # O(1)
            return f"all {n} collected tests deselected by addopts -m '{found[0]}' in {found[1]}; pass run_tests -m EXPR to select them"  # O(1)
        return f"all {n} collected tests deselected by a -m or -k filter"  # O(1)
    if paths:  # O(p)
        return "no tests found in " + ", ".join(paths)  # O(p)
    return "no tests found (check testpaths and python_files in the pytest config)"  # O(1)


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


def task_cmd_spec(a):  # O(L + m + f) the spec of the `cmd=` in --task's plan **Tests:** field, else None
    if not getattr(a, "task", None):  # O(1)
        return None  # O(1)
    plan = a.plan or next((p for p in (stable_plan(), nt.DEFAULT_PLAN) if p and Path(p).is_file()), None)  # O(1)
    if not plan or not Path(plan).is_file():  # O(1)
        return None  # O(1)
    try:  # O(1)
        info = nt.parse_plan(plan)  # O(L)
    except Exception:  # an unreadable plan is the old path's usage error, not ours  # O(1)
        return None  # O(1)
    if a.task not in info:  # O(1)
        return None  # O(1)
    cmd = testcmd.task_command(nt._field(info[a.task]["body"], "Tests"))  # O(len body)
    if not cmd:  # O(1)
        return None  # O(1)
    try:  # O(1)
        base = testcmd.resolve(".", ())  # O(m + f)
    except Exception:  # O(1)
        base = None  # O(1)
    base = base or {}  # O(1)
    return {"language": "task", "python": False, "command": cmd, "junit": "", "env": base.get("env") or {}, "setup": base.get("setup") or "",  # O(1)
            "source": "plan", "origin": f"{plan}: {a.task} **Tests:** cmd=", "isolate": bool(base.get("isolate"))}  # O(1)


def run(a):  # O(X + T*d + B + F log F) + the runner + one incident append
    paths = [p for chunk in (a.fast or []) for p in nt.csv(chunk)]  # O(p)
    label = "fast" if paths or a.marker or getattr(a, "passthrough", None) else "full"  # O(1)
    if a.also and not a.task:  # O(1)
        return usage_error(a, label, "--also needs --task Tn")  # O(summary size)
    if a.also:  # the claim is recorded before any runner or tree, so the tree below holds the file | O(c + k)
        also_claims(a)  # O(c + k)
    tspec = task_cmd_spec(a)  # the task's own **Tests:** cmd= | O(L + m + f)
    if tspec:  # a fast run of the named command; --fast paths are not handed to it | O(1)
        label = "fast"  # O(1)
        print(f"run_tests: {a.task} runs its **Tests:** cmd: {tspec['command']}", file=sys.stderr)  # O(1)
        if paths:  # O(1)
            print(f"run_tests: --fast paths are not passed to {a.task}'s **Tests:** cmd=", file=sys.stderr)  # O(1)
        paths = []  # O(1)
    if paths and not tspec:  # a workflow, config or doc file is no test (#597) | O(p)
        paths, skipped = skip_non_test(paths)  # O(p)
        if skipped:  # O(1)
            print(f"run_tests: --fast skips non-test paths: {', '.join(skipped)}", file=sys.stderr)  # O(p)
        if non_test_reason(paths, skipped):  # O(1)
            return usage_error(a, label, non_test_reason(paths, skipped))  # O(summary size)
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
    a.unit_snap = None if tspec else unit_snapshot(a, label)  # before the runner touches anything | O(n * size)
    try:  # a test name no Swift target declares is refused, never widened | O(m + f)
        spec = tspec or fast_spec(paths)  # .superlite/test-cmd.json, else marker files | O(m + f)
    except testcmd.UnknownTestName as e:  # O(1)
        return usage_error(a, label, str(e))  # O(summary size)
    if spec is None:  # no test command: exit 2 with a clear summary | O(1)
        hint = getattr(testcmd, "missing_reason", None)  # T3's text when present | O(1)
        reason = hint(Path(".")) if hint else ("no test command found: add .superlite/test-cmd.json "  # O(1)
                  '{"language","test","test_file","junit","setup"} or a package.json scripts.test, go.mod, Cargo.toml, *.csproj or pytest project')
        if a.task:  # a task run names the plan-side fix too (#566) | O(1)
            reason += f"; or name {a.task}'s own command on its Tests line: **Tests:** fast cmd=<command>"  # O(1)
        print(f"run_tests: {reason}", file=sys.stderr)  # O(1)
        write_summary(a.summary, label, {"passed": 0, "failed": 0, "skipped": 0, "skipped_tests": []}, [], 0.0, error=reason)  # O(1)
        publish_summary(a)  # O(summary size)
        print("0 0 0 0.0")  # O(1)
        return 2  # O(1)
    gate = placeholder_line(Path("."), spec)  # O(m + f)
    if gate:  # a Swift placeholder in a project without Swift files: exit 2, no incident | O(1)
        return usage_error(a, label, gate)  # O(summary size)
    node_gone = node_install_line(Path.cwd(), spec)  # O(m + f)
    if node_gone:  # no install yet: a usage error, not a test failure (#269) | O(1)
        return usage_error(a, label, node_gone)  # O(summary size)
    if a.marker and not spec["python"]:  # a test-cmd.json command takes the marker only when it is pytest | O(len)
        marked = with_marker(spec["command"], a.marker)  # O(len)
        if marked is not None:  # O(1)
            spec = {**spec, "command": marked}  # O(1)
        else:  # a remote or wrapped `test`: the marker runs through test_file or the local pytest runner (#638) | O(m + f)
            fallback = marker_spec(spec, paths, a.marker) if spec.get("source") != "plan" else None  # O(m + f)
            if fallback is None:  # O(1)
                return usage_error(a, label, f"-m EXPR selects pytest markers; the {spec['language']} test command `{spec['command']}` is not pytest")  # O(summary size)
            spec = fallback[0]  # O(1)
            print(fallback[1], file=sys.stderr)  # O(1)
    elif not a.marker and not spec["python"] and paths and spec.get("source") != "plan":  # a --fast test file with a deselected marker, in a pytest test-cmd.json command (#593) | O(p + files)
        honoured = honoured_marker(paths, ".")  # O(p + files)
        marked = with_marker(spec["command"], honoured[0]) if honoured else None  # O(len)
        if marked is not None:  # O(1)
            spec = {**spec, "command": marked}  # O(1)
            print(honoured[1], file=sys.stderr)  # O(1)
    if paths and (spec["python"] or label == "fast"):  # a missing path is a usage error, not a no-result stop (#235) | O(p)
        gone = missing_line(paths, getattr(a, "cwd", Path.cwd()), Path.cwd(), spec["python"])  # O(p)
        if gone:  # O(1)
            return usage_error(a, label, gone)  # O(summary size)
    refused = free_disk(a, {k for k in (a.task, worker_tree_name()) if k})  # before any tree or build | O(T + c)
    if refused:  # O(1)
        return usage_error(a, label, refused)  # O(summary size)
    if not spec["python"]:  # O(1)
        with contextlib.ExitStack() as stack:  # the tree is busy from before prepare to the end of the run (#574) | O(1)
            tree = None  # O(1)
            key = a.task or (worker_tree_name() if paths and spec.get("isolate", False) else None)  # a fleet worker's --fast run without --task gets worker-<Wn> (#479) | O(env)
            if key and spec.get("isolate", False):  # compiled stack: test own files only, in an isolated tree | O(1)
                sp = stable_plan()  # O(S)
                plan = a.plan or next((p for p in (sp, nt.DEFAULT_PLAN) if p and Path(p).is_file()), None)  # --plan, else the first existing of stable.json's plan and the default | O(1)
                if not a.task:  # a worker has no task of its own: no plan just means no unfinished tasks to hold back | O(1)
                    info = nt.parse_plan(plan) if plan and Path(plan).is_file() else {}  # O(L)
                elif not plan or not Path(plan).is_file():  # O(1)
                    tried = a.plan or ", ".join(x for x in (sp and f"{sp} (.superlite/stable.json)", nt.DEFAULT_PLAN) if x)  # O(1)
                    reason = f"--task {a.task} needs its plan: pass --plan PLAN (tried {tried}, not found)"  # O(1)
                    return usage_error(a, label, reason)  # O(summary size)
                else:  # O(1)
                    info = nt.parse_plan(plan)  # O(L)
                    if a.task not in info:  # O(1)
                        return usage_error(a, label, f"unknown task {a.task} in {plan}")  # O(summary size)
                ct.add_also_owns(info, a.ledger)  # --also and --claim rulings own their files too (#239) | O(c + o)
                held = {}  # O(1)
                try:  # O(1)
                    if paths:  # a --fast run tests every working-tree change except the files of unfinished siblings | O(1)
                        overlay, kept = fast_overlay(".", a.task, info, a.ledger) if a.task else worker_overlay(".", key, info, a.ledger)  # O(c + f * T * o)
                        held = kept  # {path: sorted owner ids}
                    stack.enter_context(trees.busy(".", key))  # O(1)
                    tree = trees.prepare(".", key, overlay if paths else info[a.task]["owns"])  # a --full run tests the task's own files | O(f * o) + git checkout
                except (RuntimeError, OSError) as err:  # O(1)
                    return usage_error(a, label, f"isolated tree for {key} not prepared: {err}")  # O(summary size)
                _link_dir(Path.cwd() / ".superlite", Path(tree) / ".superlite")  # the tree reaches the root's .superlite/ (#511) | O(d)
                try:  # O(1)
                    overlay_now = json.loads(trees.overlay_file(".", key).read_text(encoding="utf-8"))  # O(f)
                except (OSError, ValueError):  # O(1)
                    overlay_now = []  # O(1)
                refresh_mtimes(tree, key, overlay_now)  # O(P * size)
                announce_tree(tree, key, bool(paths), held)  # O(f)
                link_node_modules(Path.cwd(), tree, spec)  # O(d)
                tree_gone = node_install_line(tree, spec)  # a tree without node_modules fails like the root | O(m + f)
                if tree_gone:  # O(1)
                    return usage_error(a, label, tree_gone)  # O(summary size)
            if tree:  # the build output lives in the tree and goes with it (#574) | O(len)
                built = with_derived_data(spec["command"], tree)  # O(len)
                if built != spec["command"] or (spec.get("setup") and with_derived_data(spec["setup"], tree) != spec["setup"]):  # O(len)
                    spec = {**spec, "command": built, "setup": with_derived_data(spec["setup"], tree) if spec.get("setup") else spec.get("setup")}  # setup builds there too | O(len)
                    print(f"run_tests: build output in {trees.derived_data_path(tree)} (removed with the tree)", file=sys.stderr)  # O(1)
                else:  # a wrapped build the rewrite cannot reach: warn once per command | O(len + files)
                    warning = wrapped_build_warning(spec["command"], tree, Path.cwd(), spec.get("language"))  # O(len + files)
                    if warning:  # O(1)
                        warn_once(spec["command"], warning)  # O(warned)
                spec = {**spec, "env": {"SUPERLITE_DERIVED_DATA_PATH": str(trees.derived_data_path(tree)), **(spec.get("env") or {})}}  # O(env)
            with full_run_gate(a, label, lock_toolchain(spec), spec.get("lock", True)) as gate:  # O(wait / LOCK_POLL)
                rc = run_other(a, spec, paths, label, cwd=tree, gate=gate)  # O(X + o)
            if tree and rc == 1:  # a red tree run names the changed files the tree lacks (#517) | O(f)
                try:  # O(1)
                    out = outside_tree(".", overlay_now)  # O(f log f)
                except (RuntimeError, OSError):  # O(1)
                    out = []  # O(1)
                if out:  # O(1)
                    more = f" (+{len(out) - 5} more)" if len(out) > 5 else ""  # O(1)
                    tail = f"if {a.task} needs one, rerun with --also F" if a.task else "kept at base while their task or worker is busy"  # O(1)
                    print(f"run_tests: {len(out)} changed file(s) not in {key}'s tree: {', '.join(out[:5])}{more}; {tail}", file=sys.stderr)  # O(1)
            return rc  # O(1)

    with tempfile.TemporaryDirectory() as tmp:  # O(1) mkdtemp
        xml_path = Path(tmp) / "junit.xml"  # O(1)
        try:  # O(1)
            base = pyrun.pytest_cmd()  # O(1) + at most one probe spawn
        except pyrun.PytestUnavailable as e:  # O(1)
            return usage_error(a, label, str(e))  # the summary is written too | O(summary size)
        marker = a.marker  # O(1)
        if not marker and paths:  # a file marked with a marker the addopts deselect runs its tests (#593) | O(p + files)
            honoured = honoured_marker(paths, ".")  # O(p + files)
            if honoured:  # O(1)
                marker = honoured[0]  # O(1)
                print(honoured[1], file=sys.stderr)  # O(1)
        cmd = [*base, *(paths or testcmd.python_full_args(Path("."))), *(["-m", marker] if marker else []), "-q", "-rP", "-p", "no:cacheprovider",  # O(p) -rP: a passing test's prints reach the output log (#501)
               "-o", "junit_family=xunit1", f"--junitxml={xml_path}", *(getattr(a, "passthrough", None) or [])]  # O(1)
        with full_run_gate(a, label, enabled=spec.get("lock", True) if spec else True) as gate:  # O(wait / LOCK_POLL)
            t0 = time.monotonic()  # O(1)
            r = gate.run(cmd, limit=a.limit, env=child_env(getattr(a, "cli_env", None)))  # no SUPERLITE_FLEET_* in the pytest run (#219) | O(env)
            seconds = time.monotonic() - t0 - gate.waited  # the admission wait is not test time | O(1)
        save_output(a, shlex.join(cmd), r.returncode, r.stdout + r.stderr)  # O(o)
        has_xml = xml_path.exists() and xml_path.stat().st_size > 0  # O(1)
        parsed = collection_report(xml_path) if r.returncode == 2 and has_xml else None  # a collection error stops pytest with exit 2 (#196) | O(X + T*d)
        if parsed is None and (r.returncode not in (0, 1) or not has_xml):  # O(1)
            tail = (r.stdout + r.stderr).strip().splitlines()[-5:]  # O(O)
            cause = nothing_collected(strip_ansi(r.stdout + r.stderr), paths, a.marker, Path(".")) if r.returncode == 5 else None  # O(O + file)
            sig = signal_name(r.returncode) if parsed is None else None  # O(1)
            reason = f"pytest collected nothing (exit 5): {cause}" if cause else killed_reason(sig, r.returncode) if sig else f"pytest produced no results (exit {r.returncode}): " + (" | ".join(tail) or "no output")  # O(1)
            print(reason, file=sys.stderr)  # O(1)
            write_summary(a.summary, label, {"passed": 0, "failed": 0, "skipped": 0,  # O(1)
                                             "skipped_tests": []}, [], seconds,  # O(1)
                          error=reason)  # O(1)
            publish_summary(a)  # O(summary size)
            record_no_result(a, reason, shlex.join(cmd), r.returncode, (r.stdout + r.stderr).splitlines(), cause=cause, sig=sig)  # O(O + c)
            print(f"0 0 0 {seconds:.1f}")  # O(1)
            return 1 if r.returncode == 5 else 2  # O(1)
        counts, failures, files = parsed or parse_junit(xml_path)  # O(X + T*d)
    return finish_run(a, label, counts, failures, files, seconds, r.returncode)  # O(k + F)


def unfinished_owners(path, task, info, done):  # O(T * o) the other uncommitted plan tasks owning path; [] when task owns it too (done: committed task ids)
    if nt.owns_match(path, info[task]["owns"]):  # O(o)
        return []  # O(1)
    return sorted(t for t in info if t != task and t not in done and nt.owns_match(path, info[t]["owns"]))  # O(T * o)


def fast_overlay(root, task, info, ledger):  # O(f * T * o) + two spawns: (paths to overlay, paths kept at base), both sorted
    copy, delete = trees.own_changes(root, trees.base_commit(root), ["**/*"])  # O(f)
    done = ct.committed_tasks(ledger)  # one ledger read per run | O(c)
    overlay, held = [], {}  # O(1)
    for p in sorted(set(copy) | set(delete)):  # O(f log f)
        owners = unfinished_owners(p, task, info, done)  # O(T * o)
        if owners:  # O(1)
            held[p] = owners  # O(1)
        else:  # O(1)
            overlay.append(p)  # O(1)
    return overlay, held  # O(1)


def worker_tree_name(env=None):  # O(1) `worker-<Wn>` for a fleet worker that tests (not a lead), else None
    env = os.environ if env is None else env  # O(1)
    wid, agent = env.get("SUPERLITE_FLEET_WORKER") or "", (env.get("SUPERLITE_FLEET_AGENT") or "").split(":")[-1]  # O(1)
    if not re.fullmatch(r"[A-Za-z0-9_-]+", wid) or env.get("SUPERLITE_FLEET_ROLE") == "lead" or agent in ("", "lead"):  # O(1)
        return None  # O(1)
    return f"worker-{wid}"  # O(1)


def busy_held(sd, me, paths):  # O(w + p * w) the paths another busy fixer's or reviewer's brief names, {path: [worker ids]}; a path me's own brief names is not held
    briefs = ct.busy_briefs(sd, None)  # O(w + brief size)
    mine = briefs.pop(me, None)  # O(1)
    out = {}  # O(1)
    for p in paths:  # O(p) iterations
        if mine and ct.brief_names(mine[1], p):  # O(brief size)
            continue  # O(1)
        owners = sorted(wid for wid, (_label, text) in briefs.items() if ct.brief_names(text, p))  # O(w * brief size)
        if owners:  # O(1)
            out[p] = owners  # O(1)
    return out  # O(1)


def worker_overlay(root, key, info, ledger):  # O(f * T * o) + two spawns: (paths to overlay, {path: owners}) for a worker's tree; owners are unfinished task ids and `busy Wn`
    copy, delete = trees.own_changes(root, trees.base_commit(root), ["**/*"])  # O(f)
    done = ct.committed_tasks(ledger)  # O(c)
    paths = sorted(set(copy) | set(delete))  # O(f log f)
    busy = busy_held(Path(root) / ".superlite", key.removeprefix("worker-"), paths)  # O(w + p * w)
    overlay, held = [], {}  # O(1)
    for p in paths:  # O(f)
        owners = sorted(t for t in info if t not in done and nt.owns_match(p, info[t]["owns"])) + [f"busy {w}" for w in busy.get(p, [])]  # O(T * o)
        if owners:  # O(1)
            held[p] = owners  # O(1)
        else:  # O(1)
            overlay.append(p)  # O(1)
    return overlay, held  # O(1)


def announce_tree(tree, task, fast, held=None):  # O(f) name the isolated tree and how many files it overlays on stderr
    try:  # O(1)
        n = len(json.loads(trees.overlay_file(".", task).read_text(encoding="utf-8")))  # O(f)
    except (OSError, ValueError, TypeError):  # an unreadable overlay counts 0 | O(1)
        n = 0  # O(1)
    try:  # O(1)
        rel = Path(tree).resolve().relative_to(Path.cwd().resolve()).as_posix()  # O(1)
    except ValueError:  # O(1)
        rel = Path(tree).as_posix()  # O(1)
    what = "all working-tree changes (--fast)" if fast else f"{task}'s own changes"  # O(1)
    kept = ""  # O(1)
    if held:  # O(1)
        every = {t for owners in held.values() for t in owners}  # O(f)
        ids, busy = sorted(t for t in every if not t.startswith("busy ")), sorted(t[5:] for t in every if t.startswith("busy "))  # O(f log f)
        what_held = ", ".join(x for x in (f"of unfinished {' '.join(ids)}" if ids else "", f"of busy {' '.join(busy)}" if busy else "") if x)  # O(1)
        kept = f"; kept at base: {len(held)} file{'' if len(held) == 1 else 's'} {what_held}"  # O(1)
    print(f"run_tests: tree {rel} = base + {what}: {n} file{'' if n == 1 else 's'}{kept}", file=sys.stderr)  # O(1)


def finish_run(a, label, counts, failures, files, seconds, returncode, covered=None):  # O(k + F + B) one incident append
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
    resolve_passed(a.log, a.task, failures, files, green=not (counts["failed"] or not (counts["passed"] or counts["skipped"])), full=label == "full", started=getattr(a, "started", None), covered=covered)  # O(B + I + k) a green run closes stale failures (#180, #380)

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
