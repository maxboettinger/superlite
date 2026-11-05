#!/usr/bin/env python3
"""Commit one or more tasks: stage only each task's Owns files, block anything else.

    commit_task.py Tn [Tm ...] [--plan P] [--ledger .superlite/progress.md]
                      [--log .superlite/incidents.jsonl] [--allow-other-tasks]
                      [--also FILE ... --ruling TEXT]
                      [--dispatch [--pool .superlite/pool.json] [--running T3] [--cap 10] [--batch N]]

Several ids commit in order in one process (one plan parse, one exclude check). Output:
the SHA for one task; `Tn <sha>` per task for several. A task that is not checkpointed prints `Tn FAILED: <reason>`
(one task or several) and the call exits non-zero. Each committed
task's agent in the pool (`current: Tn`) gets `current` cleared, `busy: false`, and Tn in
its `tasks`. `--dispatch` then prints `next:` and the `dispatch` lines (ready tasks and
agents) for the updated ledger, with the run's batch setting (`--batch`, else the plan's experiment claim, as
`dispatch` does); a dispatch failure only warns, the commits stand.

`--also FILE` (several tasks: the first gets the files; needs `--ruling TEXT`) commits FILE with that task though
another task owns it or nobody does, and writes `- Ruling: Tn also commits FILE - TEXT` to
the ledger, after which that task owns FILE for the rest of the run; a FILE with no change is noted on stderr and ignored. The commit message is
`autocommit.message()`: `KEY Tn: title` when the plan has a `**Ticket:** KEY` header.

Default is checkpoint mode: instead of committing, a shadow commit (never on HEAD, the
branch or the user's index) is stored under refs/superlite/<run>/<Tn> and its SHA is what
the ledger, probes and seam checks use; `sl autocommit on` (or SUPERLITE_AUTOCOMMIT=1)
makes real commits.

Steps: scope check (a change outside every task's Owns blocks the commit and is logged as an incident when it was dirty
before the run (stable.json `baseline_dirty`) or the run recorded no baseline; with a baseline, any other such file is
unrelated to the task: it is left uncommitted and listed as `left uncommitted (outside every Owns): F`; files another
task owns are left uncommitted, silently), py_compile plus an import check on each touched .py file, commit
with the task title, append the SHA to the progress ledger, then launch in the
background `sl probe_run --commit SHA` and, for every seam of the task graph
(`sl plan_tools taskgraph --format full`) that involves this task and whose both
sides are now committed per the ledger, `sl pt_review contract --plan P --seam
Ta,Tb --log LOG` (mismatches become incidents, a pass logs `verified`). Prints the
SHA, or exits 1 listing the problem files. Run it from the repository root.

Scope rules: `tests/regression/` (where probe_run writes `test_probe_*.py`) is owned
by whichever task is committing, so the task or review that fixes a defect commits
the regression test it caused. `.superlite/` is never staged and never blocks; add it
to the repo's `.git/info/exclude` at setup (`setup_exclude()` here does it, and
commit_task also does it on every run). Unowned files under the plan's own folder (the
directory of --plan: sibling spec, review) never block and are never staged; owned ones commit.
A tracked, modified (not new, not deleted) file under a `tests/` folder that no task owns
commits with the task being committed (a fixer's edit to a shared test): `shared-test <path>`
on stderr and a `workaround` incident `Tn: shared test adjusted` (resolution `accepted`).
New tests, deletions and source files still block; T0 never takes shared tests.
Stdlib only.
"""

# Complexity notation:
# n = tasks in the plan, e = dependency edges, L = plan text size
# m = changed files in the working tree, m_py = touched .py files
# f = Owns paths of this task, o = Owns paths across the whole plan (~n*f)
# s = seams in the task graph (<= e), c = lines in the progress ledger, x = lines in .git/info/exclude
# "process spawn" = fork/exec of git, sl or python; dominates wall time over the O(...) CPU term
import argparse  # O(1)
import json  # O(1)
import os  # O(1)
import py_compile  # O(1)
import re  # O(1)
import subprocess  # O(1)
import sys  # O(1)
import tempfile  # O(1)
from pathlib import Path  # O(1)

sys.path.insert(0, str(Path(__file__).resolve().parent))  # O(1)
import next_tasks as nt  # noqa: E402 | O(1)
import autocommit  # noqa: E402 | O(1)
import pyroots  # noqa: E402 | O(1)
import _pyrun  # noqa: E402 | O(1)
from pool import currents  # noqa: E402 | O(1)
import state  # noqa: E402 | O(1)

DEFAULT_LEDGER = ".superlite/progress.md"  # O(1)
DEFAULT_LOG = ".superlite/incidents.jsonl"  # O(1)
IGNORED_PARTS = (".superlite/", "__pycache__/")  # never staged, never blocking | O(1)
SHARED_OWNS = ("tests/regression/",)  # generated probe regression tests: owned by the committer | O(1)
COMMIT_LINE = re.compile(r"^\s*[-*+]?\s*commit\s+([A-Z]{1,3}\d+[A-Za-z]?)\s+[0-9a-f]{7,40}")  # O(1)
SURROGATE = re.compile("[\ud800-\udfff]")  # lone surrogates from argv cannot be written as UTF-8 | O(1)
TASK_ID = re.compile(r"\b[A-Z]{1,3}\d+[A-Za-z]?\b")  # O(1)

IMPORT_DRIVER = r"""
import importlib, importlib.util, json, os, sys, traceback
sys.dont_write_bytecode = True
root = os.path.abspath(sys.argv[1])
roots = sorted((os.path.abspath(r) for r in json.loads(sys.argv[2])), key=len, reverse=True)
files = sys.argv[3:]
sys.path.insert(0, root)
if os.path.isdir(os.path.join(root, "src")):
    sys.path.insert(1, os.path.join(root, "src"))
for r in roots:
    sys.path.append(r)
failures = []
for rel in files:
    path = os.path.join(root, rel)
    parts = rel.replace("\\", "/")[:-3].split("/")
    under = [r for r in roots if os.path.abspath(path).startswith(r + os.sep)]
    if under:
        parts = os.path.relpath(path, under[0])[:-3].replace("\\", "/").split("/")
    elif parts[0] == "src" and os.path.isdir(os.path.join(root, "src")):
        parts = parts[1:]
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    try:
        if parts and all(p.isidentifier() for p in parts):
            importlib.import_module(".".join(parts))
        else:
            name = "_slcheck_" + "_".join(p.replace("-", "_") for p in parts)
            sys.path.append(os.path.dirname(path))
            spec = importlib.util.spec_from_file_location(name, path)
            mod = importlib.util.module_from_spec(spec)
            sys.modules[name] = mod
            spec.loader.exec_module(mod)
    except BaseException as e:
        line = 0
        for fr in traceback.extract_tb(e.__traceback__):
            if os.path.abspath(fr.filename) == os.path.abspath(path):
                line = fr.lineno
        failures.append({"file": rel, "line": line,
                         "error": f"{type(e).__name__}: {e}"[:150]})
print(json.dumps(failures))
"""  # O(1)


def git(*args, check=True):  # O(output) + process spawn
    r = subprocess.run(["git", *args], capture_output=True, text=True,  # O(output) + process spawn
                       encoding="utf-8")  # O(1)
    if check and r.returncode != 0:  # O(1)
        nt.die(f"git {' '.join(args[:2])} failed: {(r.stderr or r.stdout).strip()}", 1)  # O(output)
    return r  # O(1)


def ignored(path):  # O(len path)
    p = "/" + path  # O(1)
    return any(f"/{part}" in p for part in IGNORED_PARTS) or path.endswith(".pyc")  # O(len path)


def plan_folder(plan):  # O(len path) + process spawn
    """The plan's directory relative to the repo root, `dir/` with forward slashes; "" at the root or outside the repo."""
    r = git("rev-parse", "--show-toplevel", check=False)  # O(1) + process spawn
    if r.returncode != 0 or not r.stdout.strip():  # O(1)
        return ""  # O(1)
    try:  # O(1)
        rel = Path(str(plan).replace("\\", "/")).resolve().parent.relative_to(Path(r.stdout.strip()).resolve()).as_posix()  # O(len path)
    except ValueError:  # plan outside the repo | O(1)
        return ""  # O(1)
    return "" if rel == "." else rel + "/"  # O(1)


def changed_entries(skip_prefix=""):  # O(m log m) + process spawn
    """Sorted (path, XY) pairs from porcelain status; XY is the two-letter status code."""
    r = git("status", "--porcelain", "-z", "--untracked-files=all", "--no-renames")  # O(m) output + process spawn
    entries = {}  # O(1)
    for entry in r.stdout.split("\0"):  # O(m) iterations
        if len(entry) > 3:  # O(1)
            path = entry[3:].replace("\\", "/")  # O(len path)
            if not ignored(path) and not (skip_prefix and path.startswith(skip_prefix)):  # O(len path)
                entries[path] = entry[:2]  # O(1)
    return sorted(entries.items())  # O(m log m)


def changed_files(skip_prefix=""):  # O(m log m) + process spawn
    return [p for p, _ in changed_entries(skip_prefix)]  # O(m)


def shared_test(path, code):  # O(len path)
    """True for a tracked, modified (not new, not deleted) file under a `tests/` folder."""
    p = "/" + path.replace("\\", "/")  # O(len path)
    return "/tests/" in p and "M" in code and set(code) <= {"M", " "}  # O(len path)


def syntax_errors(files):  # O(total size of m_py files)
    errors = []  # O(1)
    with tempfile.TemporaryDirectory() as tmp:  # O(1) temp dir
        for f in files:  # O(m_py) iterations
            try:  # O(1)
                py_compile.compile(f, cfile=os.path.join(tmp, "x.pyc"), doraise=True)  # O(file size) compile
            except py_compile.PyCompileError as e:  # O(1)
                exc = e.exc_value  # O(1)
                line = getattr(exc, "lineno", 0) or 0  # O(1)
                msg = getattr(exc, "msg", None) or str(e)  # O(1)
                errors.append((f, line, f"SyntaxError: {msg}"))  # O(1)
    return errors  # O(1)


def import_errors(files, roots=None, root="."):  # O(m_py * import cost) + 1 process spawn (batched)
    """Import every file once under the project's own interpreter (root/.venv, VIRTUAL_ENV, else ours)."""
    if not files:  # O(1)
        return []  # O(1)
    py = _pyrun.project_python(root)  # O(1) file lookups, never run
    try:  # O(1)
        r = subprocess.run([py, "-I", "-c", IMPORT_DRIVER, str(root), json.dumps(list(roots or [])), *files],  # O(output) + process spawn
                           capture_output=True, text=True, encoding="utf-8", timeout=120,  # O(1)
                           env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})  # O(1)
    except OSError as e:  # a venv interpreter that cannot start (not executable, wrong platform): a block, not a traceback | O(1)
        return [(files[0], 0, f"import check crashed under {os.path.abspath(py)}: {e}"[:300])]  # O(1)
    try:  # O(1)
        out = json.loads(r.stdout.strip().splitlines()[-1])  # O(output)
    except (IndexError, json.JSONDecodeError):  # O(1)
        return [(files[0], 0, f"import check crashed under {os.path.abspath(py)}: {r.stderr.strip()[-150:]}")]  # O(1) absolute, so the log names the exact file
    return [(f["file"], f["line"], f["error"]) for f in out]  # O(failures)


def is_module(path):  # O(len path)
    name = Path(path).name  # O(1)
    return (path.endswith(".py") and not name.startswith("test_")  # O(1)
            and not name.endswith("_test.py") and name != "conftest.py")  # O(1)


def append_ledger(ledger, line):  # O(1) file I/O
    p = Path(ledger)  # O(1)
    p.parent.mkdir(parents=True, exist_ok=True)  # O(1)
    line = SURROGATE.sub("\ufffd", line)  # O(len line)
    new = not p.exists() or p.stat().st_size == 0  # O(1) stat
    with open(p, "a", encoding="utf-8", newline="\n") as f:  # O(1)
        if new:  # O(1)
            f.write("# Progress ledger\n\n")  # O(1)
        f.write(line + "\n")  # O(1)


def setup_exclude():  # O(x) + process spawn
    """Add `.superlite/` to the repo's .git/info/exclude (idempotent); True if it did."""
    r = git("rev-parse", "--git-path", "info/exclude", check=False)  # O(output) + process spawn
    if r.returncode != 0 or not r.stdout.strip():  # O(1)
        return False  # O(1)
    p = Path(r.stdout.strip())  # O(1)
    try:  # O(1)
        old = p.read_text(encoding="utf-8") if p.exists() else ""  # O(x) read
        if any(ln.strip() in (".superlite", ".superlite/") for ln in old.splitlines()):  # O(x)
            return False  # O(1)
        p.parent.mkdir(parents=True, exist_ok=True)  # O(1)
        with open(p, "a", encoding="utf-8", newline="\n") as f:  # O(1)
            f.write(("" if not old or old.endswith("\n") else "\n") + ".superlite/\n")  # O(1)
    except OSError:  # O(1)
        return False  # O(1)
    return True  # O(1)


def spawn_background(cmd):  # O(1) + process spawn
    kw = {}  # O(1)
    if os.name == "nt":  # O(1)
        kw["creationflags"] = 0x08000000 | 0x00000200  # CREATE_NO_WINDOW | NEW_GROUP (not DETACHED: it makes NO_WINDOW ignored and console children pop windows) | O(1)
    else:  # O(1)
        kw["start_new_session"] = True  # O(1)
    subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,  # O(1) + process spawn
                     stderr=subprocess.DEVNULL, **kw)  # O(1)


def probe_categories(plan):  # O(L + categories)
    """Union of the Review Focus categories in the plan, comma separated ("" if none).

    There is no plan or progress source for the app type, so --app-type is not passed."""
    try:  # O(1)
        import pt_review  # O(1) after first import
        cats = []  # O(1)
        for _pkg, cs in pt_review.focus_packages(pt_review.parse_plan(plan)):  # O(L) parse; O(packages) iterations
            cats += [c for c in cs if c not in cats]  # O(categories^2), categories <= 6
        return ",".join(cats)  # O(categories)
    except Exception:  # O(1)
        return ""  # O(1)


def launch_probes(sha, plan=None):  # O(L) + process spawn
    probe = Path(os.environ.get("SUPERLITE_PROBE_RUN")  # O(1)
                 or nt.SCRIPTS.parent / "probes" / "probe_run.py")  # O(1)
    if not probe.exists():  # O(1)
        return False  # O(1)
    extra = []  # O(1)
    cats = probe_categories(plan) if plan else ""  # O(L)
    if cats:  # O(1)
        extra = ["--categories", cats]  # O(1)
    spawn_background(nt.sl_command("probe_run", "--commit", sha, *extra))  # O(1) + process spawn
    return True  # O(1)


def release_agents(pool_path, tids):  # O(pool bytes)
    """In pool.json, the agent whose `current` is a committed task: clear `current`, set
    `busy: false`, add the task to its `tasks`. No pool file: nothing to do."""
    p = Path(pool_path)  # O(1)
    if not tids or not p.exists():  # O(1)
        return  # O(1)
    try:  # O(1)
        pool = json.loads(p.read_text(encoding="utf-8"))  # O(pool bytes)
    except (OSError, ValueError) as e:  # O(1)
        print(f"warning: pool not updated: {e}", file=sys.stderr)  # O(1)
        return  # O(1)
    done = set(tids)  # O(t)
    changed = False  # O(1)
    for ag in pool.get("agents", []):  # O(a) iterations
        curs = currents(ag)  # O(len current)
        hit = [t for t in curs if t in done]  # O(batch)
        if not hit:  # O(1)
            continue  # O(1)
        for t in hit:  # O(batch) iterations
            if t not in ag.setdefault("tasks", []):  # O(tasks per agent)
                ag["tasks"].append(t)  # O(1)
        left = [t for t in curs if t not in done]  # O(batch)
        if left:  # O(1)
            ag["current"] = ",".join(left)  # O(batch)
        else:  # O(1)
            ag.pop("current", None)  # O(1)
            ag["busy"] = False  # O(1)
        changed = True  # O(1)
    if changed:  # O(1)
        tmp = p.with_name(p.name + ".tmp")  # O(1)
        tmp.write_text(json.dumps(pool, indent=1) + "\n", encoding="utf-8")  # O(pool bytes)
        tmp.replace(p)  # O(1) atomic rename


def committed_tasks(ledger):  # O(c)
    p = Path(ledger)  # O(1)
    if not p.exists():  # O(1)
        return set()  # O(1)
    out = set()  # O(1)
    for ln in p.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n").split("\n"):  # O(c) iterations
        m = COMMIT_LINE.match(ln)  # O(1) regex
        if m:  # O(1)
            out.add(m.group(1))  # O(1)
    return out  # O(1)


ALSO_LINE = re.compile(r"^\s*[-*+]?\s*(?:\*\*)?Ruling:(?:\*\*)?\s*([A-Z]{1,3}\d+[A-Za-z]?) also commits (\S+) - ")  # O(1)


def also_owned(ledger):  # O(c)
    """{file or dir/ entry: task} from `Ruling: Tn also commits F - why` ledger lines; a missing ledger gives {}."""
    p = Path(ledger)  # O(1)
    if not p.exists():  # O(1)
        return {}  # O(1)
    out = {}  # O(1)
    for ln in p.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n").split("\n"):  # O(c) iterations
        m = ALSO_LINE.match(ln)  # O(1) regex
        if m:  # O(1)
            out[m.group(2)] = m.group(1)  # O(1)
    return out  # O(1)


def add_also_owns(info, ledger):  # O(c + o)
    """Append every recorded --also entry to its task's owns (once); ids not in the plan are ignored."""
    for entry, tid in also_owned(ledger).items():  # O(c) iterations
        if tid in info and entry not in info[tid]["owns"]:  # O(o)
            info[tid]["owns"] = info[tid]["owns"] + [entry]  # O(o)


def seams(plan):  # O(n + e), plan parsed once per process (nt.taskgraph_full)
    """[(producer, consumer)] from the task graph; [] on failure."""
    try:  # O(1)
        data = nt.taskgraph_full(plan)  # O(L + n + e) first call, O(1) after
    except SystemExit:  # nt.die on a bad graph: commit anyway, no seams | O(1)
        print("warning: no seams (taskgraph failed)", file=sys.stderr)  # O(1)
        return []  # O(1)
    pairs = []  # O(1)
    known = set(data.get("graph") or {})  # only real task ids: `S3`, `UTF8` in seam text are not tasks | O(n)
    for s in data.get("seams") or []:  # O(s) iterations
        ids = [i for i in TASK_ID.findall(s) if not known or i in known]  # O(len seam)
        if len(ids) == 2:  # O(1)
            pairs.append((ids[0], ids[1]))  # O(1)
    if not pairs:  # seams missing from the output: derive them from the graph edges | O(1)
        for t, deps in (data.get("graph") or {}).items():  # O(n) iterations
            pairs += [(d, t) for d in deps]  # O(deps) per task, O(e) total
    return pairs  # O(1)


def launch_seam_checks(plan, task, ledger, log):  # O(c + s) + process spawn per matching seam
    """Background `pt_review contract --seam` for each seam of `task` now fully committed.

    Seams that do not involve `task` were launched when their own later side committed."""
    done = committed_tasks(ledger) | {task}  # O(c)
    launched = []  # O(1)
    for a_, b_ in seams(plan):  # O(s) iterations
        if task in (a_, b_) and a_ in done and b_ in done:  # O(1)
            spawn_background(nt.sl_command("pt_review", "contract", "--plan", plan,  # O(1) + process spawn
                                           "--seam", f"{a_},{b_}", "--log", log))  # O(1)
            launched.append(f"{a_},{b_}")  # O(1)
    return launched  # O(1)


def log_incidents(log, task, items):  # O(k) + one append (no spawn in process)
    """items: (file, line, msg) -> one batched incident write."""
    nt.add_incidents(log, [(f, line, f"{task}: {msg}", "exception", "commit_task", "open")  # O(k)
                           for f, line, msg in items])


def changed_vs_parent(files):  # O(m) + 2 git spawns, batched
    """Subset of files whose working-tree blob differs from the parent checkpoint (HEAD without one)."""
    st = None if autocommit.is_on() else autocommit.load_state()  # O(1) file read
    parent = st["entries"][-1]["sha"] if st and st.get("entries") else "HEAD"  # O(1)
    have = {}  # path -> blob sha in parent | O(1)
    for ln in git("ls-tree", "-z", parent, "--", *files).stdout.split("\0"):  # O(m) + process spawn
        if ln:  # O(1)
            meta, _, p = ln.partition("\t")  # O(len)
            have[p] = meta.split()[2]  # O(1)
    gone = [f for f in files if not os.path.lexists(f)]  # deleted: changed when the parent has it | O(m) stat
    here = [f for f in files if f not in gone]  # O(m)
    live = git("hash-object", "--", *here).stdout.split() if here else []  # O(m) + process spawn
    now = dict(zip(here, live))  # O(m)
    gone = set(gone)  # O(m)
    return [f for f in files if (f in have if f in gone else f not in now or have.get(f) != now[f])]  # O(m) unreadable hash = changed


def deleted_owned(owns, live, plan):  # O(e*f + m) + 2 git spawns; checkpoint mode only
    """Files this plan's checkpoints hold that this task owns and that are gone from disk and from git status."""
    if autocommit.is_on():  # O(1)
        return []  # O(1)
    st = autocommit.load_state()  # O(1) file read
    if not st or autocommit.plan_key(st.get("plan")) != autocommit.plan_key(plan):  # same plan only | O(len)
        return []  # O(1)
    seen = {f for e in st.get("entries", []) for f in e.get("files", [])}  # O(e*f)
    gone = [f for f in sorted(seen) if f not in live and not os.path.lexists(f) and nt.owns_match(f, owns)]  # O(f) stat
    return changed_vs_parent(gone) if gone else []  # O(m) + process spawns


def resolve_blocked(log, tid, files):  # O(log size) read + one append
    """Files this commit takes in that an earlier run blocked get a resolved entry at the same location."""
    newest = {}  # file -> newest entry | O(1)
    try:  # O(1)
        for ln in Path(log).read_text(encoding="utf-8").splitlines():  # O(log size)
            try:  # O(1)
                e = json.loads(ln)  # O(len)
            except ValueError:  # O(1)
                continue  # O(1)
            if e.get("file") in files and e.get("line") == 0 and e.get("kind") != "verified":  # O(1)
                newest[e["file"]] = e  # O(1)
    except OSError:  # O(1)
        return  # O(1)
    todo = [f for f, e in newest.items() if "blocked by commit_task" in str(e.get("context", ""))  # O(f)
            and str(e.get("resolution", "")).lower() in ("", "none", "open", "unresolved")]  # O(f)
    nt.add_incidents(log, [(f, 0, f"{tid}: {f} committed with {tid}; earlier block resolved",  # O(f) one append
                            "exception", "commit_task", "resolved") for f in sorted(todo)])


def _rel(f):
    """Repo-relative posix form of an --also path (`./x`, absolute under the cwd)."""
    f = f.replace("\\", "/")
    try:
        if os.path.isabs(f):
            f = os.path.relpath(f, os.getcwd()).replace("\\", "/")
    except ValueError:
        pass
    return os.path.normpath(f).replace("\\", "/")


def docs_joins(f, owns):  # O(o)
    """True when `f` (a docs.md) sits in the folder of an owned path, or is the root docs.md and the task owns anything."""
    d = os.path.dirname(f)  # O(len)
    return any(not d or o.replace("\\", "/").startswith(d + "/") for o in owns)  # O(o)


def others_running(pool_path, tids):  # O(pool bytes)
    """Tasks that busy pool agents are working on, other than `tids`; [] when the pool is missing or unreadable."""
    try:  # O(1)
        pool = json.loads(Path(pool_path).read_text(encoding="utf-8"))  # O(pool bytes)
        agents = pool.get("agents", [])  # O(1)
        return sorted({t for ag in agents if ag.get("busy") for t in currents(ag)  # O(a)
                       if t not in tids})  # O(a)
    except (OSError, ValueError, AttributeError, TypeError):  # O(1)
        return []  # O(1)


def baseline_dirty(plan):  # O(b) paths dirty before the run from stable.json; None when unknown (missing, broken, no key)
    try:  # O(1)
        data = json.loads((state.plan_dir(plan).parent / ".superlite" / "stable.json").read_text(encoding="utf-8"))  # O(size)
        got = data.get("baseline_dirty") if isinstance(data, dict) else None  # O(1)
        return {x for x in got if isinstance(x, str)} if isinstance(got, list) else None  # O(b)
    except Exception:  # missing, unreadable, not JSON, no plan folder | O(1)
        return None  # O(1)


def commit_one(a, tid, info, own_files):  # O(m*o + py size) + git spawns (status, add, commit, rev-parse)
    """Commit one task; (exit code, sha or None). Files other tasks own are left alone. A task not committed leaves its
    reason in a.failed[tid] for the `Tn FAILED: <reason>` line."""
    def fail(code, why):  # O(1)
        a.failed[tid] = why  # O(1)
        return code, None  # O(1)
    if tid not in info:  # O(1)
        print(f"error: unknown task {tid}", file=sys.stderr)  # O(1)
        return fail(2, "unknown task")  # O(1)
    task = info[tid]  # O(1)
    owns = task["owns"]  # O(1)
    if not owns:  # O(1)
        print(f"error: {tid} has no Owns line", file=sys.stderr)  # O(1)
        return fail(2, "no Owns line")  # O(1)
    owns = owns + [o for o in SHARED_OWNS if o not in owns]  # O(f)
    other = [o for t, i in info.items() if t != tid for o in i["owns"]  # O(o)
             if o not in SHARED_OWNS]

    mine, out_of_scope = [], []  # O(1)
    skip = plan_folder(a.plan)  # O(1) + process spawn
    shared, cand = [], []  # modified tracked tests no task owns | O(1)
    entries = changed_entries()  # O(m log m) + process spawn
    live = {f for f, _ in entries}  # O(m)
    also = [_rel(f).rstrip("/") for f in (getattr(a, "also", None) or [])]  # O(k)
    hit = lambda f, e: f == e or f.startswith(e + "/")  # file, or file under a directory entry | O(len f)
    ruled = {e.replace("\\", "/").rstrip("/"): t for e, t in {**also_owned(a.ledger), **getattr(a, "claims", {})}.items()}  # ledger rulings and claims | O(c)
    named = {}  # entry -> name as given (directory entries keep the user's text) | O(1)
    for raw in (getattr(a, "also", None) or []):  # O(k) iterations
        named[_rel(raw).rstrip("/")] = raw if raw.replace("\\", "/").endswith("/") else _rel(raw)  # O(1)
    for e in also:  # O(k) iterations
        if not any(hit(f, e) for f in live):  # O(m)
            print(f"also {e}: unchanged, ignored", file=sys.stderr)  # O(1)
    also = [e for e in also if any(hit(f, e) for f in live)]  # entries committed with this task whoever owns them | O(k*m)
    for f, code in entries:  # O(m) iterations
        if any(hit(f, e) for e in also):  # O(k)
            mine.append(f)  # O(1)
            continue  # O(1)
        if skip and f.startswith(skip) and not nt.owns_match(f, owns):  # plan folder: only owned paths count | O(f)
            continue  # O(1)
        if f.startswith("docs/") and f.endswith(".md") and not nt.owns_match(f, owns):  # docs: only owned ones count | O(f)
            continue  # O(1)
        if f in own_files and not nt.owns_match(f, owns):  # O(f)
            continue  # O(1)
        if tid == "T0" and nt.owns_match(f, other):  # Wave 0 globs never take another task's file | O(f)
            continue  # O(1)
        if nt.owns_match(f, owns):  # O(f)
            mine.append(f)  # O(1)
        elif nt.owns_match(f, other):  # O(o)
            for e, t2 in ruled.items():  # a ruling or claim made it theirs: say so | O(r)
                if t2 != tid and hit(f, e):  # O(len f)
                    print(f"left uncommitted (claimed by {t2}): {f}", file=sys.stderr)  # O(1)
                    break  # O(1)
            continue  # another task's file, built in parallel in this tree: leave it alone | O(1)
        elif tid != "T0" and shared_test(f, code):  # a fixer's edit to a shared test joins this task | O(len path)
            cand.append(f)  # O(1)
        elif os.path.basename(f) == "docs.md" and docs_joins(f, task["owns"]):  # a folder's docs.md joins the task owning a path in it | O(o)
            mine.append(f)  # O(1)
        else:  # O(1)
            out_of_scope.append(f)  # O(1)

    if out_of_scope and not autocommit.is_on():  # a file already in the parent checkpoint (an earlier --also) is no new change | O(1)
        keep = set(changed_vs_parent(out_of_scope))  # O(m) + process spawns
        out_of_scope = [f for f in out_of_scope if f in keep]  # O(m)
    mine += deleted_owned(owns, live, a.plan)  # an owned file only the checkpoints hold, deleted since | O(e*f) + process spawns
    if cand:  # a shared test already in the parent checkpoint is not this task's change | O(1)
        shared = changed_vs_parent(cand)  # O(m) + process spawns
        mine += shared  # O(m)

    running = others_running(getattr(a, "pool", None) or state.pool_path(), [tid]) if out_of_scope else []  # O(pool bytes)
    if out_of_scope and running:  # a running task's stray file is not this task's block | O(m)
        for f in out_of_scope:  # O(m) iterations
            print(f"left uncommitted (another task is running: {', '.join(running)}): {f}", file=sys.stderr)  # O(1)
        out_of_scope = []  # O(1)
    if out_of_scope:  # O(1)
        base = baseline_dirty(a.plan)  # O(b)
        unrelated = [f for f in out_of_scope if base is not None and f not in base]  # the run recorded its start and this file is not in it: not this task's (#179) | O(m)
        out_of_scope = [f for f in out_of_scope if f not in unrelated]  # a file dirty before the run, or with no baseline known, blocks as before | O(m)
        for f in unrelated:  # O(m) iterations
            if f not in a.left:  # once per call, not per task | O(1)
                a.left.add(f)  # O(1)
                print(f"left uncommitted (outside every Owns): {f}", file=sys.stderr)  # stdout stays the bare SHA | O(1)
        if unrelated:  # O(1)
            nt.add_incidents(a.log, [(f, 0, f"{tid}: {f} left uncommitted (outside every Owns)", "workaround", "commit_task", "accepted")  # O(m) one append
                                     for f in unrelated])
    if out_of_scope:  # O(1)
        why = {f: (" (dirty before the run)" if base and f in base else "") for f in out_of_scope}  # O(m)
        for f in out_of_scope:  # O(m) iterations
            print(f"out-of-scope {f}{why[f]}")  # O(1)
            a.blocked.add(f)  # O(1)
        log_incidents(a.log, tid, [(f, 0, f"change outside Owns{why[f]} blocked by commit_task; "  # O(m) one append
                                    "nothing committed") for f in out_of_scope])
        return fail(1, "out-of-scope " + ", ".join(out_of_scope[:5]) + (" ..." if len(out_of_scope) > 5 else ""))  # O(m)
    if not mine:  # O(1)
        print(f"nothing to commit for {tid}", file=sys.stderr)  # O(1)
        return fail(1, "nothing to commit")  # O(1)

    for f in shared:  # O(m) iterations
        print(f"shared-test {f}", file=sys.stderr)  # O(1)
    present = [f for f in mine if os.path.exists(f)]  # O(m) stat
    py = [f for f in present if f.endswith(".py")]  # O(m)
    problems = syntax_errors(py)  # O(size of py files)
    if not problems:  # O(1)
        problems = import_errors([f for f in py if is_module(f)], a.roots)  # O(m_py * import cost) + process spawn
    if problems:  # O(1)
        shown = [f"{'syntax' if msg.startswith('SyntaxError') else 'import'} {f}:{line} {msg}" for f, line, msg in problems]  # O(problems)
        for ln in shown:  # O(problems) iterations
            print(ln)  # O(1)
        log_incidents(a.log, tid, [(f, line, f"{msg}; nothing committed")  # O(problems) one append
                                   for f, line, msg in problems])
        return fail(1, "; ".join(shown[:3]) + (" ..." if len(shown) > 3 else ""))  # O(problems)

    if shared:  # O(1)
        nt.add_incidents(a.log, [(f, 0, f"{tid}: shared test adjusted", "workaround", "commit_task", "accepted")  # O(m) one append
                                 for f in shared])
    if autocommit.is_on():  # opt-in: a real commit on the user's branch | O(1)
        git("add", "-A", "--", *mine)  # O(m) + process spawn
        title = autocommit.message(tid, task["title"], a.plan)  # O(L) file read
        r = git("commit", "-m", title, check=False)  # O(1) + process spawn
        if r.returncode != 0:  # O(1)
            err = (r.stderr or r.stdout).strip()  # O(len)
            print(err, file=sys.stderr)  # O(1)
            return fail(1, "git commit failed: " + (err.splitlines() or ["no output"])[0][:120])  # O(len)
        sha = git("rev-parse", "HEAD").stdout.strip()  # O(1) + process spawn
    else:  # default: shadow checkpoint under refs/superlite, HEAD/branch/index/tree untouched | O(m) + git spawns
        sha = autocommit.checkpoint(tid, task["title"], mine, a.plan)  # O(m) + process spawn
    append_ledger(a.ledger, f"- commit {tid} {sha[:10]} {task['title']}")  # O(1) file I/O
    for f in also:  # O(k) iterations
        append_ledger(a.ledger, f"- Ruling: {tid} also commits {named.get(f, f)} - {a.ruling}")  # O(1) file I/O
    resolve_blocked(a.log, tid, set(mine))  # O(log size)
    launch_probes(sha, a.plan)  # O(L) + process spawn
    launch_seam_checks(a.plan, tid, a.ledger, a.log)  # O(c + s) + process spawn per seam (graph memoized)
    return 0, sha  # O(1)


def main(argv=None):  # O(L + t*(m*o)) + git spawns per task; one process for all tasks
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])  # O(1)
    ap.add_argument("task", nargs="*", help="one or more task ids, committed in order")  # O(1)
    ap.add_argument("--plan", help=f"default: {nt.DEFAULT_PLAN}")  # O(1)
    ap.add_argument("--ledger", help="default: progress.md of the run folder")  # O(1)
    ap.add_argument("--log", help="default: incidents.jsonl of the run folder")  # O(1)
    ap.add_argument("--allow-other-tasks", action="store_true",  # O(1)
                    help="no-op alias (kept for compatibility): other tasks' files are always left alone")  # O(1)
    ap.add_argument("--dispatch", action="store_true",  # O(1)
                    help="after committing, print `dispatch` output (next tasks and agents)")  # O(1)
    ap.add_argument("--pool", help="pool for --dispatch; default: pool.json of the run folder")  # O(1)
    ap.add_argument("--running", help="running tasks for --dispatch (default: from the pool)")  # O(1)
    ap.add_argument("--cap", type=int, default=10, help="cap for --dispatch")  # O(1)
    ap.add_argument("--batch", type=int, help="batch for --dispatch (1 = one task per agent); default: the plan's experiment claim")  # O(1)
    ap.add_argument("--also", action="extend", nargs="+", default=[], metavar="FILE",  # O(1)
                    help="commit FILE with the one named task even if another task owns it or nobody does")  # O(1)
    ap.add_argument("--claim", action="extend", nargs="+", default=[], metavar="FILE",  # O(1)
                    help="record that the one named task also commits FILE (needs --ruling); commits nothing")  # O(1)
    ap.add_argument("--ruling", help="why --also or --claim is needed; written to the ledger")  # O(1)
    a = ap.parse_args(argv)  # O(1)
    sd = state.for_plan(a.plan) if a.plan else state.resolve()  # the run folder: --plan's own once started (#178), else the session's | O(d)
    a.plan = a.plan or nt.DEFAULT_PLAN  # O(1)
    a.ledger = a.ledger or str(sd / "progress.md")  # defaults follow the parsed --plan, not the session's binding | O(1)
    a.log = a.log or str(sd / "incidents.jsonl")  # O(1)
    a.pool = a.pool or str(sd / "pool.json")  # O(1)
    ids = [x for x in a.also + a.claim if re.fullmatch(r"T\d+", x) and not os.path.exists(x)]  # `--also F T1`: the greedy flag took the task id | O(k)
    a.also = [x for x in a.also if x not in ids]  # O(k)
    a.claim = [x for x in a.claim if x not in ids]  # `--claim F T1` too | O(k)
    a.task = a.task + ids  # O(k)
    if not a.task:  # O(1)
        ap.error("the following arguments are required: task")  # O(1)
    if a.also and not a.ruling:  # O(1)
        nt.die("--also needs --ruling TEXT")  # O(1)
    if a.claim and not a.ruling:  # O(1)
        nt.die("--claim needs --ruling TEXT")  # O(1)
    if a.claim and a.also:  # O(1)
        nt.die("--claim and --also cannot be combined")  # O(1)
    if a.claim and len(a.task) != 1:  # O(1)
        nt.die("--claim takes exactly one task")  # O(1)

    info = nt.parse_plan(a.plan)  # O(L) parse plan, once for every task
    if "T0" not in info:  # a Wave 0 task synthesized by `wave0` | O(1)
        import wave0  # O(1) lazy
        w0 = wave0.synth_info(a.plan)  # O(1) file read
        if w0:  # O(1)
            info["T0"] = {"id": "T0", "title": w0["title"], "owns": w0["owns"], "body": ""}  # O(1)
    add_also_owns(info, a.ledger)  # O(c + o) --also files stay owned by their task
    if a.claim:  # a claim only records the ruling: nothing is committed | O(k)
        if a.task[0] not in info:  # O(1)
            nt.die(f"unknown task {a.task[0]}")  # O(1)
        for raw in a.claim:  # O(k) iterations
            name = raw if raw.replace("\\", "/").endswith("/") else _rel(raw)  # O(1)
            append_ledger(a.ledger, f"- Ruling: {a.task[0]} also commits {name} - {a.ruling}")  # O(1) file I/O
            print(f"{a.task[0]} claimed {name}")  # O(1)
        return 0  # O(1)
    a.claims = {}  # entry -> task for this call's --also, known to every task in the call | O(1)
    if a.also and a.task[0] in info:  # O(k)
        for raw in a.also:  # O(k) iterations
            e = _rel(raw).rstrip("/")  # O(1)
            a.claims[e] = a.task[0]  # O(1)
            if e not in info[a.task[0]]["owns"]:  # O(o)
                info[a.task[0]]["owns"] = info[a.task[0]]["owns"] + [e]  # O(o)
    unknown = [t for t in a.task if t not in info]  # O(t)
    if len(a.task) == 1 and unknown:  # O(1)
        nt.die(f"unknown task {unknown[0]}")  # O(1)
    if len(a.task) == 1 and not info[a.task[0]]["owns"]:  # O(1)
        nt.die(f"{a.task[0]} has no Owns line")  # O(1)
    setup_exclude()  # O(x) + process spawn, once

    own_files = set()  # bookkeeping files of the run itself, never in scope | O(1)
    for p in (a.plan, a.ledger, a.log):  # O(1) iterations (3 paths)
        try:  # O(1)
            own_files.add(Path(p).resolve().relative_to(Path.cwd().resolve()).as_posix())  # O(1)
        except ValueError:  # O(1)
            pass  # O(1)

    a.roots = pyroots.import_roots(Path("."), a.plan)  # O(dirs) once per process
    a.blocked = set()  # files reported out-of-scope by any task | O(1)
    a.left = set()  # unrelated files already listed as left uncommitted | O(1)
    a.failed = {}  # task -> why it was not checkpointed | O(1)
    worst = 0  # O(1)
    committed = []  # O(1)
    also_all = a.also  # only the first task receives --also | O(1)
    for i, tid in enumerate(a.task):  # O(t) iterations
        a.also = also_all if i == 0 else []  # O(1)
        code, sha = commit_one(a, tid, info, own_files)  # see commit_one
        add_also_owns(info, a.ledger)  # O(c + o) rulings just recorded
        worst = max(worst, code)  # O(1)
        if sha:  # O(1)
            committed.append(tid)  # O(1)
            print(sha if len(a.task) == 1 else f"{tid} {sha}")  # O(1)
        else:  # a task that is not checkpointed always says so, one task or several (#179) | O(1)
            print(f"{tid} FAILED: {a.failed.get(tid, 'not checkpointed')}")  # O(1)
    if a.blocked:  # one hint for every task, not one per task | O(1)
        print("hint: commit or exclude these files, they are outside every Owns: " + ", ".join(sorted(a.blocked)))  # O(b log b)
    release_agents(a.pool, committed)  # O(pool bytes)

    if a.dispatch:  # O(1)
        print("next:")  # O(1)
        try:  # the commits stand whatever happens here | O(1)
            import dispatch  # O(1) lazy: dispatch imports this module
            batch = a.batch  # O(1)
            if batch is None:  # the run claimed an experiment (`sl experiment`, #53): its batch, as dispatch.main reads it | O(f)
                import experiment  # O(1)
                batch = (experiment.for_plan(a.plan, Path(a.pool).parent) or {}).get("batch")  # O(f)
            dispatch.render(*dispatch.run(a.plan, a.pool, a.ledger, None, a.running, a.cap, batch=batch))  # see dispatch.run
        except (SystemExit, Exception) as e:  # O(1)
            print(f"warning: dispatch failed ({e}); run `dispatch` after fixing it", file=sys.stderr)  # O(1)
    return worst  # O(1)


if __name__ == "__main__":  # O(1)
    sys.exit(main())  # O(1)
