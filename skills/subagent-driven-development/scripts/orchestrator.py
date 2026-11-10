#!/usr/bin/env python3
"""Who orchestrates: a human (approves the plan before it runs) or an AI (does everything itself).

    orchestrator.py set human|ai [--by NAME] [--ruling TEXT]
    orchestrator.py approve [--by NAME] [--review PATH]
    orchestrator.py status [--plan P]
    orchestrator.py bind [--plan P]
    orchestrator.py end [--plan P]
    orchestrator.py takeover [--plan P]
    orchestrator.py resume [--plan P]

State: `.superlite/orchestrator.json` {mode, approved, by, time}, in the folder `state.resolve` finds: the plan's git toplevel
with --plan (the review plan's with `approve --review` and no --plan), else $SUPERLITE_STATE_DIR, the session's binding, ./.superlite.
`set`, `approve` and `bind` bind the session (CLAUDE_CODE_SESSION_ID) to that folder, so the hooks find the same state
whatever directory the session was launched from. `end` closes a run: it moves the run markers (stable.json, prime.md,
prime-haiku.md, pool.json) and the gate files (orchestrator.json, human-replies.jsonl) into `.superlite/runs/<time>/` and
releases the session's binding, so the coordinator guard stops. `takeover` binds this session to a run folder another
session owns (`bind --force` plus a one-line message), so `end` and `set` act on it; `end` refuses another live session's folder and names it. In human mode `plan_tools lint --stable`, `dispatch`,
`wave0` and `build_prime` refuse to run (exit 4, one line) until `approve` has been recorded; `schedule --insert` and
`prune` stay allowed so the plan can be shown whole with its Gantt. In AI mode nothing is gated. With no file nothing is
gated (existing runs behave as before). `--ruling` on `set ai` also appends a `Ruling:` line to `.superlite/progress.md`
(for a headless run where no human can answer).
Without --plan, `end` and `set` refuse (exit 2, one line naming both folders) when the cwd is in a linked worktree and the folder found lies outside it, so one worktree never ends or rewrites another worktree's run (#199). Every other command without --plan refuses the same way when the session binding names a folder in another worktree (`state.resolve`, #224); `bind` never resolves and binds the launch folder. A submodule's `.git` file is not a linked worktree (#225).
In human mode `approve` needs `--review PATH` (the plain-language review plan; refused without it, exit 2; a missing file exit 2)
and evidence of a real human reply: `.superlite/human-replies.jsonl` (written only by the UserPromptSubmit hook, one
{"t": epoch ms, "approves": bool, "text": ...} per human prompt while unapproved) must hold a line with approves true whose t is
later than the review file's modification time, else exit 3 with a BLOCKED line. The path and sha256 are recorded. AI mode never
needs `approve`. `status` and `finish` print the review plan path; `status` also says whether an approving reply exists. Library: gate(plan_or_dir, tool) -> message or None,
require(plan_or_dir, tool) -> exit code (prints the message), read_state, summary_line, foreign_worktree (= state.foreign_worktree). Stdlib only.
"""
# Complexity notation:
#   everything here is O(1) file work
import argparse  # O(1)
import hashlib  # O(1)
import json  # O(1)
import os  # O(1)
import re  # O(1)
import subprocess  # O(1)
import sys  # O(1)
import time  # O(1)
from datetime import datetime  # O(1)
from pathlib import Path  # O(1)

sys.path.insert(0, str(Path(__file__).resolve().parent))  # O(1)
import state  # noqa: E402 | O(1)

FILE = "orchestrator.json"  # O(1)
REPLIES = "human-replies.jsonl"  # written only by the UserPromptSubmit hook | O(1)
NO_REPLY = ("BLOCKED: no human approval reply since the review plan was written; show the plan, ask the human to reply approve, "
            "end your turn")  # O(1)
NO_REVIEW = "BLOCKED: write the review plan first, then approve --review <path>"  # O(1)
EXIT_BLOCKED = 4  # exit 3 already means "no Python" for sl | O(1)
BLOCK = ("BLOCKED: human orchestrator selected, show the plan, ask for approval, then run sl orchestrator approve")  # O(1)
RUN_FILES = ("stable.json", "prime.md", "prime-haiku.md", "pool.json", FILE, REPLIES,  # what `end` archives: markers, gate, | O(1)
             "progress.md", "incidents.jsonl", "metrics.jsonl", "lint-log.jsonl", "chain-rulings.json",  # and the run's logs, so
             "test-summary.json", "briefs")  # the next run starts clean (config, checkpoints and probes stay)
NO_SESSION = "orchestrator: no session id (CLAUDE_CODE_SESSION_ID); set SUPERLITE_STATE_DIR instead"  # O(1)


def sl_dir(plan_or_dir=None) -> Path:  # O(d)
    """The `.superlite` folder: the argument itself when it is one, else the plan's git toplevel (see state.resolve)."""
    return state.resolve(plan_or_dir)  # O(d)


def read_state(plan_or_dir=None):  # O(file)
    f = sl_dir(plan_or_dir) / FILE  # O(1)
    try:  # O(1)
        d = json.loads(f.read_text(encoding="utf-8"))  # O(file)
    except (OSError, ValueError):  # O(1)
        return None  # O(1)
    return d if isinstance(d, dict) and d.get("mode") in ("human", "ai") else None  # O(1)


def write_state(plan_or_dir, state: dict) -> None:  # O(1)
    d = sl_dir(plan_or_dir)  # O(1)
    d.mkdir(parents=True, exist_ok=True)  # O(1)
    (d / FILE).write_text(json.dumps(state, indent=1) + chr(10), encoding="utf-8")  # O(1)


def gate(plan_or_dir=None, tool: str = "") -> str | None:  # O(file)
    """None when the tool may run, else the one-line reason. Only human mode without an approval blocks."""
    st = read_state(plan_or_dir)  # O(file)
    if st and st["mode"] == "human" and not st.get("approved"):  # O(1)
        return BLOCK  # O(1)
    return None  # O(1)


def require(plan_or_dir=None, tool: str = "") -> int:  # O(file)
    """0 to go on; prints the reason to stderr and returns EXIT_BLOCKED when the gate is shut."""
    msg = gate(plan_or_dir, tool)  # O(file)
    if msg:  # O(1)
        print(msg, file=sys.stderr)  # O(1)
        return EXIT_BLOCKED  # O(1)
    return 0  # O(1)


def read_replies(plan_or_dir=None) -> list:  # O(replies)
    f = sl_dir(plan_or_dir) / REPLIES  # O(1)
    out = []  # O(1)
    try:  # O(1)
        lines = f.read_text(encoding="utf-8", errors="replace").splitlines()  # O(file)
    except OSError:  # O(1)
        return out  # O(1)
    for ln in lines:  # O(replies)
        try:  # O(1)
            e = json.loads(ln)  # O(w)
        except ValueError:  # O(1)
            continue  # O(1)
        if isinstance(e, dict) and isinstance(e.get("t"), (int, float)):  # O(1)
            out.append(e)  # O(1)
    return out  # O(replies)


def approving_reply(plan_or_dir=None, since_ms: float = 0):  # O(replies)
    """The newest human reply with approves true and t later than since_ms, or None."""
    hits = [e for e in read_replies(plan_or_dir) if e.get("approves") is True and e["t"] > since_ms]  # O(replies)
    return max(hits, key=lambda e: e["t"]) if hits else None  # O(replies)


def reply_note(plan_or_dir=None, review=None) -> str:  # O(replies)
    since = 0  # O(1)
    if review and Path(review).is_file():  # O(1)
        since = Path(review).stat().st_mtime * 1000  # O(1)
    hit = approving_reply(plan_or_dir, since)  # O(replies)
    if hit:  # O(1)
        return f"approving reply at {datetime.fromtimestamp(hit['t'] / 1000).isoformat(timespec='seconds')}"  # O(1)
    return "no qualifying human reply yet" if review else "no approving human reply yet"  # O(1)


def summary_line(plan_or_dir=None, review=None) -> str:  # O(file)
    st = read_state(plan_or_dir)  # O(file)
    if not st:  # O(1)
        return "orchestrator: not set (ungated)"  # O(1)
    if st["mode"] == "ai":  # O(1)
        return f"orchestrator: AI (set {st.get('time', '?')} by {st.get('by', '?')})"  # O(1)
    if st.get("approved"):  # O(1)
        review = f", review plan {st['review_path']}" if st.get("review_path") else ""  # O(1)
        return f"orchestrator: human, approved {st.get('approved_time') or st.get('time')} by {st.get('approved_by') or st.get('by')}{review}"  # O(1)
    return f"orchestrator: human, awaiting approval (set {st.get('time', '?')}; {reply_note(plan_or_dir, review)})"  # O(1)


def now() -> str:  # O(1)
    return datetime.now().isoformat(timespec="seconds")  # O(1)


def end(sd: Path) -> str:  # O(files)
    """Archive the run's markers, gate files and logs into sd/runs/<time>/ and release the session; one line."""
    present = [f for f in RUN_FILES if (sd / f).exists()]  # O(1)
    present += sorted({p.name for pat in ("test-summary-*.json", "test-summary-*.log", "test-summary.latest")  # per-run summaries | O(files)
                       for p in sd.glob(pat)})  # O(files)
    state.unbind(sd)  # O(d)
    (sd / "inline-flow.json").unlink(missing_ok=True)  # the inline-flow marker ends with the run (#148) | O(1)
    if not present:  # O(1)
        return f"orchestrator: nothing to end in {sd}"  # O(1)
    dest = sd / "runs" / time.strftime("%Y%m%d-%H%M%S")  # O(1)
    while dest.exists():  # two ends in one second | O(1) amortized
        dest = dest.with_name(dest.name + "-1")  # O(1)
    dest.mkdir(parents=True)  # O(1)
    for f in present:  # O(files)
        (sd / f).replace(dest / f)  # O(1)
    return f"orchestrator: run ended; {len(present)} files moved to {dest}"  # O(1)


foreign_worktree = state.foreign_worktree  # the #199 check and state.resolve share one test (#224) | O(1)

def plan_file(sd: Path, given: str | None = None) -> Path | None:  # O(1)
    """The plan of the run in sd: --plan when it is a file, else stable.json, pool.json, sd/plan.md (the first that exists)."""
    if given and Path(given).is_file():  # O(1)
        return Path(given)  # O(1)
    for name in ("stable.json", "pool.json"):  # O(1) iterations
        try:  # O(1)
            p = json.loads((sd / name).read_text(encoding="utf-8")).get("plan")  # O(file)
        except (OSError, ValueError, AttributeError):  # O(1)
            continue  # O(1)
        if isinstance(p, str) and p and Path(p).is_file():  # O(1)
            return Path(p)  # O(1)
    return sd / "plan.md" if (sd / "plan.md").is_file() else None  # O(1)


def changed_since(root: Path, ref: str, files: list[str]) -> list[str]:  # O(f) plus two git calls
    """The files (regular files, or deleted ones) whose working-tree blob differs from ref's, sorted."""
    if not files:  # O(1)
        return []  # O(1)
    want = set(files)  # O(f)
    run = subprocess.run(["git", "-C", str(root), "ls-tree", "-r", "-z", ref, "--", *files], capture_output=True, text=True)  # O(f) git
    if run.returncode:  # ref no longer exists (rebased, pruned): compare with HEAD | O(1)
        run = subprocess.run(["git", "-C", str(root), "ls-tree", "-r", "-z", "HEAD", "--", *files], capture_output=True, text=True)  # O(f) git
    out = run.stdout  # O(1)
    old = {}  # O(1)
    for ent in out.split("\0"):  # O(f) iterations
        head, _, path = ent.partition("\t")  # O(1)
        if path in want:  # O(1)
            old[path] = head.split()[2]  # O(1)
    live = sorted(f for f in want if (root / f).is_file())  # O(f)
    now_ = {}  # O(1)
    if live:  # O(1)
        hashed = subprocess.run(["git", "-C", str(root), "hash-object", "--", *live],
                                capture_output=True, text=True).stdout.split()  # O(f) git
        now_ = dict(zip(live, hashed))  # O(f)
    return sorted(f for f in want if now_.get(f) != old.get(f) and (f in now_ or f in old))  # O(f log f)


def test_run_line(sd: Path) -> str:  # O(1)
    """One line about the last test run recorded in sd/test-summary.json."""
    f = sd / "test-summary.json"  # O(1)
    if not f.is_file():  # O(1)
        return f"last test run: none in {sd}"  # O(1)
    try:  # O(1)
        d = json.loads(f.read_text(encoding="utf-8"))  # O(file)
        at = datetime.fromtimestamp(f.stat().st_mtime).strftime("%H:%M:%S")  # O(1)
        line = f"last test run: {d['mode']}, {d['passed']} passed, {d['failed']} failed, ended {at}"  # O(1)
        return line + (f", error: {d['error']}" if d.get("error") else "")  # O(1)
    except (OSError, ValueError, KeyError, TypeError, AttributeError):  # O(1)
        return f"last test run: unreadable {f}"  # O(1)


def compare_ref(root: Path, ref: str) -> str:  # O(1) git
    """ref when it still names a commit, else HEAD's full sha."""
    ok = subprocess.run(["git", "-C", str(root), "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"], capture_output=True, text=True)  # O(1) git
    if ref and ok.returncode == 0:  # O(1)
        return ref  # O(1)
    return subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()  # O(1) git


def task_test_run(sd: Path, files: list[str]) -> dict | None:  # O(s * f)
    """The newest test summary (by mtime) in sd whose files map names one of files: mode, passed, failed in those files, ended."""
    want = {f.replace("\\", "/").removeprefix("./") for f in files}  # O(f)
    best = None  # O(1)
    for p in [*sd.glob("test-summary.json"), *sd.glob("test-summary-*.json")]:  # O(s) iterations
        try:  # O(1)
            d = json.loads(p.read_text(encoding="utf-8"))  # O(file)
            mt = p.stat().st_mtime  # O(1)
        except (OSError, ValueError):  # O(1)
            continue  # O(1)
        if not isinstance(d, dict) or not isinstance(d.get("files"), dict):  # O(1)
            continue  # O(1)
        hit = [v for k, v in d["files"].items() if isinstance(k, str) and k.replace("\\", "/").removeprefix("./") in want]  # O(f)
        if not hit:  # O(1)
            continue  # O(1)
        if not all(isinstance(v, (list, tuple)) and len(v) == 2 and all(type(n) is int for n in v) for v in hit):  # O(f)
            continue  # O(1)
        if best is None or mt > best["ended"]:  # O(1)
            best = {"mode": d.get("mode", "?"), "passed": sum(v[0] for v in hit), "failed": sum(v[1] for v in hit), "ended": mt}  # O(f)
    return best  # O(1)


def task_test_line(tid: str, run: dict | None, changed: list[str], root: Path) -> str:  # O(f)
    """One line: the last test run that named the task's files, and which changed files were edited after it."""
    if run is None:  # O(1)
        return f"{tid} last test run: none covers its files"  # O(1)
    at = datetime.fromtimestamp(run["ended"]).strftime("%H:%M:%S")  # O(1)
    late = [f for f in changed if (root / f).is_file() and (root / f).stat().st_mtime > run["ended"]]  # O(f)
    tail = f"; edited after it: {', '.join(late)}" if late else "; nothing edited after it"  # O(f)
    return f"{tid} last test run: {run['mode']}, {run['passed']} passed, {run['failed']} failed in its files, ended {at}{tail}"  # O(1)


def resume_lines(sd: Path, plan: Path) -> list[str]:  # O(t * f) plus git calls
    """Per plan task, what a dead coordinator left behind: checkpoint, edits after it, uncommitted Owns files."""
    import autocommit  # lazy: orchestrator is imported by every gated tool | O(1)
    import plan_tools  # O(1)
    root = state.git_root(sd)  # O(d)
    tasks = plan_tools.Plan.load(str(plan)).tasks  # O(plan)
    entries = []  # O(1)
    try:  # O(1)
        ck = json.loads((root / ".superlite" / "checkpoints.json").read_text(encoding="utf-8"))  # O(file)
        if ck.get("plan") == autocommit.plan_key(str(plan)) and ck.get("entries"):  # O(1)
            entries = [e for e in ck["entries"] if isinstance(e, dict)]  # O(e)
    except (OSError, ValueError, AttributeError):  # O(1)
        entries = []  # O(1)
    shas, efiles = {}, {}  # O(1)
    for e in entries:  # O(e) iterations
        shas[e.get("task")] = e.get("sha", "")  # newest entry wins | O(1)
        efiles.setdefault(e.get("task"), []).extend(e.get("files") or [])  # O(f)
    try:  # O(1)
        ledger = (sd / "progress.md").read_text(encoding="utf-8").splitlines()  # O(file)
    except OSError:  # O(1)
        ledger = []  # O(1)
    for ln in ledger:  # O(lines) iterations
        m = re.match(r"\s*[-*+]?\s*commit\s+([A-Z]{1,3}\d+[A-Za-z]?)\s+([0-9a-f]{7,40})", ln)  # O(1)
        if m:  # O(1)
            shas.setdefault(m.group(1), m.group(2))  # O(1)
    if entries:  # O(1)
        ref = entries[-1].get("sha", "")  # O(1)
        head = (f"resume: plan {plan}; checkpointed tasks compared with their own checkpoint, "
                f"the others with the chain head {ref[:7]} ({entries[-1].get('task')})")  # O(1)
    else:  # O(1)
        ref = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()  # O(1)
        if shas:  # O(1)
            head = (f"resume: plan {plan}; no checkpoint chain; checkpointed tasks compared with their own checkpoint, "
                    f"the others with HEAD {ref[:7]}")  # O(1)
        else:  # O(1)
            head = f"resume: plan {plan}; no checkpoints; files compared with HEAD {ref[:7]}"  # O(1)
    lines, clean, none = [head], [], []  # O(1)
    for t in tasks:  # O(t) iterations
        files = list(dict.fromkeys([*t.owns, *efiles.get(t.id, [])]))  # O(f)
        full = shas.get(t.id, "")  # O(1)
        tref = compare_ref(root, full) if full else ref  # O(1) git
        ch = changed_since(root, tref, files)  # O(f) git
        sha = full[:7]  # O(1)
        if sha and ch:  # O(1)
            gone = f" (gone; compared with HEAD {tref[:7]})" if tref != full else ""  # O(1)
            lines.append(f"{t.id} checkpointed {sha}{gone}: edited after the checkpoint: {', '.join(ch)}; keep: sl commit_task {t.id} --plan {plan}; "
                         f"drop: git restore --source {tref[:7]} -- {' '.join(ch)}")  # O(f)
        elif sha:  # O(1)
            clean.append(t.id)  # O(1)
        elif ch:  # O(1)
            lines.append(f"{t.id} not checkpointed: uncommitted Owns files: {', '.join(ch)}; run its tests, then sl commit_task {t.id} --plan {plan}")  # O(f)
        else:  # O(1)
            none.append(t.id)  # O(1)
        if ch:  # O(1)
            lines.append(task_test_line(t.id, task_test_run(sd, files), ch, root))  # O(s * f)
    if clean:  # O(1)
        lines.append("checkpointed, nothing edited after: " + " ".join(clean))  # O(t)
    if none:  # O(1)
        lines.append("no changes: " + " ".join(none))  # O(t)
    lines.append(test_run_line(sd))  # O(1)
    return lines  # O(1)


def resume(sd: Path, given: str | None) -> int:  # O(t * f) the `resume` command
    """Prune dead pool entries (unless another live session owns sd), then print the per-task report; exit 2 without a plan."""
    other = state.live_owner(sd)  # O(d)
    if other:  # O(1)
        print(f"pool: not pruned: {sd} belongs to session {other}; take the run over first: sl orchestrator takeover --plan {sd}")  # O(1)
    else:  # O(1)
        import pool  # lazy | O(1)
        try:  # O(1)
            print(chr(10).join(pool.prune_file(str(sd / "pool.json"))))  # O(lines)
        except SystemExit as e:  # a corrupt pool.json must not stop the report | O(1)
            print(f"pool: not pruned: {e}")  # O(1)
        except Exception as e:  # noqa: BLE001 any prune failure is one line | O(1)
            print(f"pool: not pruned: {type(e).__name__}: {e}")  # O(1)
    plan = plan_file(sd, given)  # O(1)
    if plan is None:  # O(1)
        print(f"resume: no plan found for {sd}; pass --plan <plan.md>")  # O(1)
        return 2  # O(1)
    if state.git_root(sd) is None:  # O(d)
        print(f"resume: {sd} is in no git checkout")  # O(1)
        return 2  # O(1)
    try:  # O(1)
        import plan_tools  # O(1)
        plan_tools.Plan.load(str(plan))  # O(plan)
    except Exception as err:  # noqa: BLE001 any load failure is one line | O(1)
        print(f"resume: plan {plan} unreadable: {err}")  # O(1)
        return 2  # O(1)
    print(chr(10).join(resume_lines(sd, plan)))  # O(t * f)
    return 0  # O(1)


def main(argv=None):  # O(1)
    ap = argparse.ArgumentParser(description=__doc__.split(chr(10))[0])  # O(1)
    sub = ap.add_subparsers(dest="cmd", required=True)  # O(1)
    s = sub.add_parser("set")  # O(1)
    s.add_argument("mode", choices=["human", "ai"])  # O(1)
    s.add_argument("--by", default="user")  # O(1)
    s.add_argument("--ruling", help="with ai: also record a Ruling: line in .superlite/progress.md")  # O(1)
    a_ = sub.add_parser("approve")  # O(1)
    a_.add_argument("--by", default="human")  # O(1)
    a_.add_argument("--review", help="the approved review plan (docs/plans/<date>-<topic>.review.md): path and sha256 are recorded")  # O(1)
    st = sub.add_parser("status")  # O(1)
    st.add_argument("--review", help="review plan path: status says whether a reply newer than it approves")  # O(1)
    b_ = sub.add_parser("bind")  # O(1)
    e_ = sub.add_parser("end")  # O(1)
    t_ = sub.add_parser("takeover")  # O(1)
    r_ = sub.add_parser("resume")  # O(1)
    for p in (s, a_, st, b_, e_, t_, r_):  # O(1)
        p.add_argument("--plan", help="plan path (locates .superlite at its git toplevel); default: the session's binding, else ./.superlite")  # O(1)
    b_.add_argument("--force", action="store_true", help="take over a folder another live session owns")  # O(1)
    a = ap.parse_args(argv)  # O(1)
    review = getattr(a, "review", None)  # O(1)
    if a.cmd == "bind" and not a.plan:  # bind without a plan targets the launch directory, never resolves | O(d)
        sd = state.launch_dir() / ".superlite"  # O(d)
    elif a.cmd in ("end", "set", "takeover") and not a.plan:  # the #199 check below words the refusal | O(d)
        sd = state.resolve(None, strict=False)  # O(d)
    elif a.cmd == "approve" and review and not a.plan:  # O(1)
        sd = state.plan_dir(review)  # O(d)
    else:  # a writer or reader following a foreign binding exits 2 inside resolve (#224) | O(d)
        sd = sl_dir(a.plan)  # O(d)
    if a.cmd == "resume":  # O(1)
        return resume(sd, a.plan)  # O(t * f)
    if a.cmd in ("end", "set", "takeover") and not a.plan:  # without --plan never act on another worktree's run (#199) | O(d)
        top = foreign_worktree(sd)  # O(d)
        if top:  # O(1)
            how = "SUPERLITE_STATE_DIR" if os.environ.get("SUPERLITE_STATE_DIR") else "session binding"  # O(1)
            print(f"orchestrator: cwd is in worktree {top}, but the run folder found is {state._abs(sd)} ({how}); "
                  f"{ {'end': 'not ended', 'set': 'not set'}.get(a.cmd, 'not taken over') }; pass --plan {top / '.superlite'} for this worktree's run, "
                  f"or --plan {state._abs(sd)}", file=sys.stderr)  # O(d)
            return 2  # O(1)
    if a.cmd == "takeover":  # O(1)
        if a.plan and not Path(a.plan).exists():  # O(1)
            print(f"orchestrator: plan not found: {a.plan}", file=sys.stderr)  # O(1)
            return 2  # O(1)
        if not sd.is_dir():  # O(1)
            print(f"orchestrator: no run folder {sd}; nothing to take over", file=sys.stderr)  # O(1)
            return 2  # O(1)
        old = state.owner(sd)  # O(1)
        if not state.bind(sd, force=True):  # O(b + d)
            print(NO_SESSION, file=sys.stderr)  # O(1)
            return 2  # O(1)
        if old and old != state.session_id():  # O(1)
            print(f"orchestrator: run {state._abs(sd)} taken over from session {old}; this session owns it now")  # O(d)
        else:  # O(1)
            print(f"orchestrator: session bound to {state._abs(sd)}; no other session owned it")  # O(d)
        return 0  # O(1)
    if a.cmd == "end":  # O(1)
        if a.plan and not Path(a.plan).exists():  # a removed worktree's path would walk up to another checkout | O(1)
            print(f"orchestrator: plan not found: {a.plan}; end before removing the worktree", file=sys.stderr)  # O(1)
            return 2  # O(1)
        other = state.live_owner(sd)  # O(d)
        if other:  # O(1)
            print(f"orchestrator: {sd} belongs to session {other}; not ended; take the run over first: sl orchestrator takeover --plan {sd}", file=sys.stderr)  # O(1)
            return 2  # O(1)
        print(end(sd))  # O(files)
        return 0  # O(1)
    if a.cmd in ("bind", "set", "approve"):  # bind first: it refuses another session's folder and brings a pending gate | O(1)
        try:  # O(1)
            bound = state.bind(sd, force=getattr(a, "force", False))  # O(b + d)
        except state.Owned:  # O(1)
            other = state.live_owner(sd) or state.owner(sd)  # O(d)
            print(f"orchestrator: {state._abs(sd)} belongs to session {other}; pass --plan with your own worktree's plan, "
                  f"or take the run over: sl orchestrator takeover --plan {state._abs(sd)}", file=sys.stderr)  # O(d)
            return 2  # O(1)
        if a.cmd == "bind":  # O(1)
            if not bound:  # O(1)
                print(NO_SESSION, file=sys.stderr)  # O(1)
                return 2  # O(1)
            print(f"orchestrator: session bound to {state._abs(sd)}")  # O(d)
            return 0  # O(1)
    if a.cmd == "set":  # O(1)
        write_state(sd, {"mode": a.mode, "approved": a.mode == "ai", "by": a.by, "time": now()})  # O(1)
        if a.mode == "ai" and a.ruling:  # O(1)
            f = sd / "progress.md"  # O(1)
            with f.open("a", encoding="utf-8") as fh:  # O(1)
                fh.write(f"Ruling: {a.ruling}" + chr(10))  # O(1)
        print(summary_line(sd))  # O(1)
        return 0  # O(1)
    cur = read_state(sd)  # O(file)
    if a.cmd == "approve":  # O(1)
        if not cur or cur["mode"] != "human":  # O(1)
            print("orchestrator: approve applies to human mode only; run: sl orchestrator set human", file=sys.stderr)  # O(1)
            return 2  # O(1)
        if not a.review:  # a human orchestrator approves a written review plan, never a bare yes | O(1)
            print(NO_REVIEW, file=sys.stderr)  # O(1)
            return 2  # O(1)
        if a.review:  # O(1)
            rp = Path(a.review)  # O(1)
            if not rp.is_file():  # O(1)
                print(f"orchestrator: review plan not found: {a.review}", file=sys.stderr)  # O(1)
                return 2  # O(1)
            if not approving_reply(sd, rp.stat().st_mtime * 1000):  # a real human reply, written by the hook, after the plan | O(replies)
                print(NO_REPLY, file=sys.stderr)  # O(1)
                return 3  # O(1)
            cur.update(review_path=a.review.replace(chr(92), "/"), review_sha256=hashlib.sha256(rp.read_bytes()).hexdigest())  # O(size)
        cur.update(approved=True, approved_by=a.by, approved_time=now())  # O(1)
        write_state(sd, cur)  # O(1)
    print(summary_line(sd, review))  # O(1)
    return 0  # O(1)


if __name__ == "__main__":  # O(1)
    sys.exit(main())  # O(1)
