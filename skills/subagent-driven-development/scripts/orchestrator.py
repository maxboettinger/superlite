#!/usr/bin/env python3
"""Who orchestrates: a human (approves the plan before it runs) or an AI (does everything itself).

    orchestrator.py set human|ai [--by NAME] [--ruling TEXT]
    orchestrator.py approve [--by NAME] [--review PATH]
    orchestrator.py status [--plan P]
    orchestrator.py bind [--plan P]
    orchestrator.py end [--plan P]

State: `.superlite/orchestrator.json` {mode, approved, by, time}, in the folder `state.resolve` finds: the plan's git toplevel
with --plan (the review plan's with `approve --review` and no --plan), else $SUPERLITE_STATE_DIR, the session's binding, ./.superlite.
`set`, `approve` and `bind` bind the session (CLAUDE_CODE_SESSION_ID) to that folder, so the hooks find the same state
whatever directory the session was launched from. `end` closes a run: it moves the run markers (stable.json, prime.md,
prime-haiku.md, pool.json) and the gate files (orchestrator.json, human-replies.jsonl) into `.superlite/runs/<time>/` and
releases the session's binding, so the coordinator guard stops. In human mode `plan_tools lint --stable`, `dispatch`,
`wave0` and `build_prime` refuse to run (exit 4, one line) until `approve` has been recorded; `schedule --insert` and
`prune` stay allowed so the plan can be shown whole with its Gantt. In AI mode nothing is gated. With no file nothing is
gated (existing runs behave as before). `--ruling` on `set ai` also appends a `Ruling:` line to `.superlite/progress.md`
(for a headless run where no human can answer).
In human mode `approve` needs `--review PATH` (the plain-language review plan; refused without it, exit 2; a missing file exit 2)
and evidence of a real human reply: `.superlite/human-replies.jsonl` (written only by the UserPromptSubmit hook, one
{"t": epoch ms, "approves": bool, "text": ...} per human prompt while unapproved) must hold a line with approves true whose t is
later than the review file's modification time, else exit 3 with a BLOCKED line. The path and sha256 are recorded. AI mode never
needs `approve`. `status` and `finish` print the review plan path; `status` also says whether an approving reply exists. Library: gate(plan_or_dir, tool) -> message or None,
require(plan_or_dir, tool) -> exit code (prints the message), read_state, summary_line. Stdlib only.
"""
# Complexity notation:
#   everything here is O(1) file work
import argparse  # O(1)
import hashlib  # O(1)
import json  # O(1)
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
    state.unbind(sd)  # O(d)
    if not present:  # O(1)
        return f"orchestrator: nothing to end in {sd}"  # O(1)
    dest = sd / "runs" / time.strftime("%Y%m%d-%H%M%S")  # O(1)
    while dest.exists():  # two ends in one second | O(1) amortized
        dest = dest.with_name(dest.name + "-1")  # O(1)
    dest.mkdir(parents=True)  # O(1)
    for f in present:  # O(files)
        (sd / f).replace(dest / f)  # O(1)
    return f"orchestrator: run ended; {len(present)} files moved to {dest}"  # O(1)


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
    for p in (s, a_, st, b_, e_):  # O(1)
        p.add_argument("--plan", help="plan path (locates .superlite at its git toplevel); default: the session's binding, else ./.superlite")  # O(1)
    b_.add_argument("--force", action="store_true", help="take over a folder another live session owns")  # O(1)
    a = ap.parse_args(argv)  # O(1)
    review = getattr(a, "review", None)  # O(1)
    sd = state.plan_dir(review) if a.cmd == "approve" and review and not a.plan else sl_dir(a.plan)  # O(d)
    if a.cmd == "bind" and not a.plan:  # bind without a plan targets the launch directory, never the private folder | O(d)
        sd = state.launch_dir() / ".superlite"  # O(d)
    if a.cmd == "end":  # O(1)
        if a.plan and not Path(a.plan).exists():  # a removed worktree's path would walk up to another checkout | O(1)
            print(f"orchestrator: plan not found: {a.plan}; end before removing the worktree", file=sys.stderr)  # O(1)
            return 2  # O(1)
        other = state.live_owner(sd)  # O(d)
        if other:  # O(1)
            print(f"orchestrator: {sd} belongs to session {other}; not ended", file=sys.stderr)  # O(1)
            return 2  # O(1)
        print(end(sd))  # O(files)
        return 0  # O(1)
    if a.cmd in ("bind", "set", "approve"):  # bind first: it refuses another session's folder and brings a pending gate | O(1)
        try:  # O(1)
            bound = state.bind(sd, force=getattr(a, "force", False))  # O(b + d)
        except state.Owned as e:  # O(1)
            print(f"orchestrator: {e}", file=sys.stderr)  # O(1)
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
