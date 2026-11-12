#!/usr/bin/env python3
"""Backlog runner (phase 3): start batch leads, wait for them, answer an escalated lead.

    backlog_run.py start [B ...] [--cap 2] [--model opus]
    backlog_run.py wait [--timeout 21600] [--poll 10]
    backlog_run.py answer B --file F        (F = {"answers": {question: answer}, "by": "user"|"main"|{question: ...}})
    backlog_run.py tell B --text T          (send main's text to the running lead of B)

`start` takes several ids: each refusal prints BLOCKED, the others start. A lead that does not start prints `BLOCKED: B lead did not start; ...` after its spawn's own line, sets exit 2 and the batches after it still start (#551). Each lead worktree gets a copy of the main
checkout's `.superlite/test-cmd.json` before its brief, unless it already has one (#334); the copied bytes are recorded in `.superlite/test-cmd.seeded` so an unedited copy follows the main checkout's file, and a lead brief gets one `Test command:` line when the copy and the main file differ (#638). A lead whose stop text holds no
Status line is re-prompted once (`reprompted`), then parked. A question.json is cut to the limits (header, label,
description; each cut is reported as `shortened:`); one still invalid is sent back to the lead once
(`question_reprompted`), then parked. A stop record whose transcript lags (blank, or
without the status its `last` holds) is re-read for fleet_io.READ_MS, then parked "(transcript unread)".
A lead whose brief Herdr refuses (after send_brief's one resend on a stall) is stopped and its batch keeps its state (BLOCKED line, exit 2).
A resumed batch's lead brief ends with the worktree state (commits, uncommitted files, answers already given).
`wait` tells a live lead once when the Herdr panes of its fleet workers stay gone for GONE_MS (a crash), and flags it.
`answer` takes one answer rule (backlog_answer, #586): a label, a label plus a note, or free text up to 2000 characters. `_shipped` also runs for a batch without lead or worktree (`ship B done` on a planned batch, #585).
`remove_worktree` is the git-only worktree and branch removal (a PR head gets `-D`, #589); `_shipped(push=False)` uses it, never maxapp. A failed cleanup line carries git's error and the core.bare cause and is stored as the batch's `cleanup_owed`. `start` blocks a batch whose worktree.ensure raises or gives the main checkout.
Exit 0 done, 2 refused, 3 BLOCKED. Fleet modules are imported inside functions so tests can swap them.
"""
# Complexity notation: b = batches, w = workers, m = lines of metrics.jsonl
import argparse  # O(1)
import json  # O(1)
import re  # O(1)
import subprocess  # O(1)
import sys  # O(1)
import os  # O(1)
import time  # O(1)
from pathlib import Path  # O(1)

HERE = Path(__file__).resolve().parent  # O(1)
sys.path.insert(0, str(HERE))  # O(1)
import backlog_answer as ba  # noqa: E402 | O(1)
import backlog_checks as bc  # noqa: E402 | O(1)
import backlog_state as bs  # noqa: E402 | O(1)
import testcmd  # noqa: E402 | O(1)

ACTIVE = ("running", "needs_decision")
STATUS = re.compile(r"\bStatus:\s*\**\s*(DONE_WITH_CONCERNS|DONE|NEEDS_DECISION|NEEDS_CONTEXT|BLOCKED)\b", re.I)
REPROMPT = ("superlite: your last turn ended without a status line. Go on with the batch; end your turn only with "
            "Status: DONE, DONE_WITH_CONCERNS, NEEDS_CONTEXT or BLOCKED, or write .superlite/question.json and end with "
            "Status: NEEDS_DECISION.")
QUESTION_FIX = ("superlite: your .superlite/question.json is invalid: {errs}. Limits: 1 to 4 distinct questions, each question 1 to 300 "
                "characters, a header of 1 to 12, 2 to 4 options with distinct labels of 1 to 60 and descriptions up to 200 "
                "(an over-long header, label or description is cut for you). Rewrite the file and end your turn with "
                "Status: NEEDS_DECISION.")

ANSWER_MAIN = ("Main answered your question as AI orchestrator, not Max: read {af}; its by map names who answered each question "
               "(user: Max's decision, main: main's ruling); record each that way, then go on with the batch.")
ANSWERS_LINE = ("- Answers given mid-run: {names} in .superlite/ (also under Max's decisions or main's rulings above; each file's by "
                "names who answered; never ask them again)")
TELL = "superlite: main says (sl backlog tell): {text}"

CLEANUP = Path(".superlite") / "cleanup-cmd.json"  # O(1)
CLEANUP_TIMEOUT = 600  # O(1)
GONE_MS = 30000  # O(1)
GONE = ("superlite: the Herdr panes of your fleet workers {ids} are gone (a crash?), so their tasks will never report. "
        "Run `{sl} fleet stop {ids} --plan .superlite`, then dispatch their unfinished tasks again.")


def _root() -> Path:
    return bs.main_root(Path.cwd())  # O(1) + spawn


def _now_ms() -> int:
    return int(time.time() * 1000)  # O(1)


def _run(cmd, cwd):
    try:  # O(1)
        r = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)  # O(cmd)
    except OSError as e:  # O(1)
        return 127, str(e)  # O(1)
    return r.returncode, (r.stdout + r.stderr).strip()  # O(out)


def _ctrl(s: str) -> bool:
    return any(_bad(c) for c in s)  # O(len)


def _bad(c: str) -> bool:  # O(1)
    return (ord(c) < 32 and c not in "\n\t") or ord(c) == 127  # O(1)


def _clean(t: str) -> str:  # O(len)
    return "".join("?" if _bad(c) else c for c in t)[:120]  # O(len)


def _resume_state(batch: dict, wt: Path, branch: str) -> list:
    cut = _clean  # O(1)
    rc, ref = _run(["git", "symbolic-ref", "--short", "refs/remotes/origin/HEAD"], wt)  # O(cmd)
    base = ref.split("/", 1)[1] if rc == 0 and "/" in ref else "main"  # O(1)
    out = [f"Previous lead {batch['lead']}: parked ({_clean(' '.join(str(batch['reason']).split()))}); its work stays in this worktree. "
           "Read it before you plan; keep, finish or drop each part on purpose:"]  # O(1)
    rc, log = _run(["git", "log", "--format=%h %s", f"origin/{base}..HEAD"], wt)  # O(cmd)
    lines = [cut(x) for x in log.splitlines() if x.strip()] if rc == 0 else []  # O(lines)
    more = f" (+{len(lines) - 5} more)" if len(lines) > 5 else ""  # O(1)
    head = f"- Commits on {branch} not on origin/{base}: "  # O(1)
    out.append(head + (f"{len(lines)}" + (": " + "; ".join(lines[:5]) + more if lines else "") if rc == 0 else "unknown (git log failed)"))  # O(1)
    rc, st = _run(["git", "status", "--short"], wt)  # O(cmd)
    files = [cut(x.strip()) for x in st.splitlines() if x.strip()] if rc == 0 else []  # O(lines)
    more = f" (+{len(files) - 10} more)" if len(files) > 10 else ""  # O(1)
    out.append("- Uncommitted files: " + (f"{len(files)}" + (": " + ", ".join(files[:10]) + more if files else "") if rc == 0 else "unknown (git status failed)"))  # O(1)
    names = [x.name for x in sorted((wt / ".superlite").glob("answer-*.json"))]  # O(a log a)
    if names:  # O(1)
        out.append(ANSWERS_LINE.format(names=", ".join(names)))  # O(a)
    return out  # O(1)


def _gone(p, sd, b: dict, states: dict) -> list:
    import fleet_io
    import fleet_state
    lsd, bid = Path(b["worktree"]) / ".superlite", b["id"]  # O(1)
    old = b.get("gone_seen") or {}  # O(1)
    done = list(b.get("gone_workers") or [])  # O(1)
    now = _now_ms()  # O(1)
    seen = {}  # O(1)
    for wid, w in fleet_state.load(lsd).get("workers", {}).items():  # O(w)
        if w.get("state") in ("stopped", "starting") or w.get("role") == "layer" or wid in done:  # O(1)
            continue  # O(1)
        if fleet_state.name_of(lsd, wid, w) not in states:  # O(1)
            seen[wid] = old.get(wid, now)  # O(1)
    due = [wid for wid, t in seen.items() if now - t >= GONE_MS]  # O(w)
    keep = {wid: t for wid, t in seen.items() if wid not in due}  # O(w)
    if keep != old or due:  # O(1)
        bs.update(p, lambda d: bs.batch(d, bid).update({"gone_seen": keep, "gone_workers": done + due}))  # O(size)
    if not due:  # O(1)
        return []  # O(1)
    ids = " ".join(due)  # O(w)
    rc = fleet_io.main(["send", b["lead"], "--text", GONE.format(ids=ids, sl=HERE / "sl"), "--plan", str(sd)])  # O(w)
    return [f"{bid} worker panes gone: {ids}; lead {b['lead']} " + ("not told (send failed)" if rc else "told")]  # O(1)


def _stop(sd, lead):  # O(w)
    import fleet
    try:  # O(1)
        fleet.stop(sd, [lead])  # O(w)
    except (Exception, SystemExit):  # O(1)
        pass  # O(1)


def _unanswered(b: dict) -> bool:
    return any(not b.get("answers", {}).get(q["question"]) for d in b.get("decisions", []) for q in d.get("questions", []))  # O(q)


def _refuse(msg: str, code: int = 2) -> int:
    print(f"BLOCKED: {msg}")  # O(1)
    return code  # O(1)


def _pick(data: dict, bids: list, cap: int, live: dict) -> tuple:
    """-> (ids to start, refusal messages); a passed id counts as active for the later ids."""
    active = [x for x in data["batches"] if x["state"] in ACTIVE]  # O(b)
    ids, msgs = [], []  # O(1)
    for bid in (list(dict.fromkeys(bids)) if bids else bs.startable(data, cap)):  # O(ids * b * files)
        try:  # O(1)
            b = bs.batch(data, bid)  # O(b)
        except KeyError:  # O(1)
            msgs.append(f"unknown batch {bid}")  # O(1)
            continue  # O(1)
        if b["state"] not in ("planned", "parked"):  # O(1)
            msgs.append(f"{bid} is {b['state']}")  # O(1)
            continue  # O(1)
        wait = next((d for d in b.get("depends", []) if not any(x["id"] == d and x["state"] == "shipped" for x in data["batches"])), None)  # O(depends * b)
        if wait:  # O(1)
            msgs.append(f"{bid} waits for {wait}")  # O(1)
            continue  # O(1)
        other = next((o for o in active if set(b.get("files", [])) & set(o.get("files", []))), None)  # O(b * files)
        if other:  # O(1)
            msgs.append(f"{bid} shares files with running {other['id']}")  # O(1)
            continue  # O(1)
        if _unanswered(b):  # O(q)
            msgs.append(f"{bid} has open decisions (sl backlog decide --print)")  # O(1)
            continue  # O(1)
        if len(active) >= cap:  # O(1)
            msgs.append(f"no free slot for {bid} (cap {cap})")  # O(1)
            continue  # O(1)
        if b.get("agent") and b["agent"] in live:  # O(1)
            msgs.append(f"{bid} lead {b.get('lead', '')} is still running (sl backlog wait)")  # O(1)
            continue  # O(1)
        ids.append(bid)  # O(1)
        active.append(b)  # O(1)
    return ids, msgs  # O(ids)


MACHINE = [("runner offline", re.compile(r"runner offline|offline runner", re.I)), ("GUI session", re.compile(r"GUI session", re.I)),  # O(1)
           ("login session", re.compile(r"login session", re.I)), ("WindowServer", re.compile(r"WindowServer", re.I))]  # O(1)


def machine_park_line(lines: list):  # O(lines * patterns)
    """One `machine: ...` line naming the batches a round parked for a machine reason, else None."""
    by, ids = {}, []  # O(1)
    for ln in lines:  # O(lines)
        m = re.match(r"(\S+) parked: (.*)", str(ln))  # O(len)
        label = m and next((n for n, r in MACHINE if r.search(m.group(2))), None)  # O(patterns)
        if label:  # O(1)
            by.setdefault(label, []).append(m.group(1))  # O(1)
            ids.append(m.group(1))  # O(1)
    if not by:  # O(1)
        return None  # O(1)
    parts = "; ".join(f"{n} parks {', '.join(v)}" for n, v in by.items())  # O(lines)
    return f"machine: {parts}; fix the machine first, then sl backlog start {' '.join(ids)}"  # O(lines)


def cmd_start(a) -> int:
    import fleet
    import machine_load
    import fleet_io
    import fleet_lead
    import fleet_state
    import worktree
    import backlog
    import backlog_brief
    if os.environ.get("SUPERLITE_FLEET_WORKER"):  # only Max's session runs this; never a lead or worker
        return _refuse("sl backlog_run start runs only in the main session")  # O(1)
    root = _root()  # O(1)
    sd, p = root / ".superlite", bs.path(root)  # O(1)
    data = bs.load(p)  # O(size)
    if not data.get("approved_ship"):  # O(1)
        return _refuse("no ship approval yet (sl backlog decide --print)")  # O(1)
    try:  # O(1)
        live = fleet.hc.agent_states()  # O(w)
    except fleet.hc.HerdrError as e:  # O(1)
        return _refuse(f"Herdr not reachable ({e})", 3)  # O(1)
    ids, msgs = _pick(data, a.batch, a.cap, live)  # O(b log b)
    for m in msgs:  # O(msgs)
        _refuse(m)  # O(1)
    if not ids and not msgs:  # O(1)
        print("no startable batch")  # O(1)
        return 0  # O(1)
    code = 2 if msgs else 0  # O(1)
    summaries = []  # O(1)
    for b in data["batches"]:  # O(b)
        f = sd / "backlog" / f"{b['id']}.md"  # O(1)
        if b["state"] == "shipped" and f.is_file():  # O(1)
            summaries.append(str(f))  # O(1)
    fleet_on = False  # O(1)
    deadline = time.monotonic() + a.machine_wait  # one budget for the whole call | O(1)
    for bid in ids:  # O(ids)
        busy = machine_load.gate(f"backlog start {bid}", max(0.0, deadline - time.monotonic()), a.over_limit)  # O(wait)
        if busy:  # O(1)
            print(f"BLOCKED: {bid} not started: {busy}; rerun sl backlog start {bid}, or --over-limit")  # O(1)
            code = 2  # O(1)
            continue  # O(1)
        batch = bs.batch(data, bid)  # O(b)
        try:  # O(1)
            wt, state = worktree.ensure(f"{bid.lower()}-{batch['topic']}", root)  # O(w) + spawns
        except (worktree.BareCheckout, worktree.Taken, worktree.BadBranch, RuntimeError) as e:  # O(1)
            print(f"BLOCKED: {bid} not started: {e}")  # O(1)
            code = 2  # O(1)
            continue  # O(1)
        wt = Path(wt)  # O(1)
        linked = wt.resolve() != Path(root).resolve() and (Path(root) / worktree.PARENT).resolve() in wt.resolve().parents  # O(1)
        if state not in ("created", "exists") or not linked:  # O(1)
            cause = worktree.bare_flag(root)  # O(1) + spawn
            print(f"BLOCKED: {bid} not started: worktree ensure gave {wt} ({state}), not a linked worktree under {root}/.claude/worktrees" + (f"; cause: {cause}" if cause else ""))  # O(1)
            code = 2  # O(1)
            continue  # O(1)
        if backlog.seed_test_cmd(root, wt):  # main's .superlite/test-cmd.json before the brief (#334), recorded so it can follow main (#638) | O(size)
            testcmd.record_seed(wt)  # O(size)
        branch = "superlite/" + wt.name.replace("superlite-", "", 1)  # O(1)
        ctx = {"sl": str(HERE / "sl"), "backlog_md": str(HERE.parent / "backlog.md"), "repo": data.get("repo", ""),
               "approved": data.get("approved_ship"), "titles": data.get("titles", {}), "summaries": summaries,
               "resume": batch["state"] == "parked" and bool(batch.get("worktree"))}  # O(1)
        brief = wt / ".superlite" / "briefs" / "lead.md"  # O(1)
        brief.parent.mkdir(parents=True, exist_ok=True)  # O(1)
        text = backlog_brief.lead_brief(batch, ctx)  # O(size)
        if ctx["resume"]:  # O(1)
            text = text.rstrip("\n") + "\n" + "\n".join(_resume_state(batch, wt, branch)) + "\n"  # O(size) + spawns
        note = testcmd.seed_note(wt)  # O(size) + spawn
        if note:  # O(1)
            text = text.rstrip("\n") + "\nTest command: " + note + "\n"  # O(size)
        brief.write_text(text, encoding="utf-8")  # O(size)
        if not fleet_on and not fleet_state.is_on(sd):  # O(w)
            fleet.main(["on", "--plan", str(sd)])  # O(w)
        fleet_on = True  # O(1)
        try:  # O(1)
            rec = fleet_lead.spawn_lead(sd, wt, a.model)  # O(1) + spawns
        except SystemExit:  # O(1)
            print(f"BLOCKED: {bid} lead did not start; {bid} keeps its state, rerun sl backlog start {bid}")  # O(1)
            code = 2  # O(1)
            continue  # O(1)
        try:  # O(1)
            fleet_io.send_brief(sd, rec["id"], str(brief), bid)  # O(w)
        except fleet.hc.HerdrError as e:  # O(1)
            _stop(sd, rec["id"])  # O(w)
            print(f"BLOCKED: {bid} lead {rec['id']} got no brief ({e}); lead stopped, rerun sl backlog start {bid}")  # O(1)
            code = 2  # O(1)
            continue  # O(1)

        def mark(d, bid=bid, rec=rec, wt=wt, branch=branch):  # O(b)
            x = bs.batch(d, bid)
            x.update({"state": "running", "lead": rec["id"], "agent": rec["name"], "worktree": str(wt), "branch": branch,
                      "since": _now_ms(), "reason": "", "ship_runs": 0, "ship_waits": 0, "reprompted": False, "question_reprompted": False,
                      "gone_seen": {}, "gone_workers": []})
        bs.update(p, mark)  # O(size)
        print(f"{bid} running lead={rec['id']} worktree={wt}")  # O(1)
    return code  # O(1)


def _lags(text, last) -> bool:
    return not STATUS.search(text) and (not text.strip() or bool(STATUS.search(last)))  # O(len)


def _stop_text(rec) -> str:
    import fleet_io
    text = ""  # O(1)
    if rec.get("transcript"):  # O(1)
        try:  # O(1)
            text = str(fleet_io.report_text(rec["transcript"]) or "")  # O(size)
        except Exception:  # O(1)
            text = ""  # O(1)
    return text or str(rec.get("last") or "")  # O(len)


def _park(p, sd, repo, b, reason, out):  # O(size)
    import fleet  # noqa: F401
    import ship_lock
    bid, lead = b["id"], b["lead"]  # O(1)

    def mark(d):  # O(b)
        x = bs.batch(d, bid)
        x["state"], x["reason"] = "parked", reason
    bs.update(p, mark)  # O(size)
    try:  # O(1)
        ship_lock.release(ship_lock.lock_path(repo), bid)  # O(1)
    except (OSError, ValueError):  # O(1)
        pass  # O(1)
    _stop(sd, lead)  # O(w)
    out.append(f"{bid} parked: {reason}")  # O(1)


def cleanup_cmd(root: Path):  # O(size)
    f = Path(root) / CLEANUP  # O(1)
    if not f.is_file():  # O(1)
        return None  # O(1)
    try:  # O(1)
        d = json.loads(f.read_text())  # O(size)
    except (OSError, ValueError) as e:  # O(1)
        print(f"cleanup-cmd.json ignored: {e}", file=sys.stderr)  # O(1)
        return None  # O(1)
    c = d.get("cleanup") if isinstance(d, dict) else None  # O(1)
    if not isinstance(c, str) or not c.strip():  # O(1)
        print('cleanup-cmd.json ignored: needs a JSON object with a "cleanup" command', file=sys.stderr)  # O(1)
        return None  # O(1)
    return c  # O(1)


def project_cleanup(root: Path, wt: Path, branch: str, bid: str):  # O(cmd)
    if str(wt) in ("", "."):  # O(1)
        return None  # O(1)
    try:  # Xcode build folders in the worktree's session scratchpads; best effort (#614) | O(files)
        import trees  # O(1) lazy
        n, freed = trees.sweep_scratch_builds(wt)  # O(files)
        if n:  # O(1)
            print(f"{bid} scratch builds: removed {n} folder(s), {freed / 1024 ** 3:.1f} GB")  # O(1)
    except Exception:  # O(1)
        pass  # O(1)
    cmd = cleanup_cmd(root)  # O(size)
    if not cmd:  # O(1)
        return None  # O(1)
    import shlex
    cmd = cmd.replace("{worktree}", shlex.quote(str(wt)))  # O(len)
    cmd = cmd.replace("{branch}", shlex.quote(branch))  # O(len)
    env = {**os.environ, "SUPERLITE_WORKTREE": str(wt), "SUPERLITE_BRANCH": branch, "SUPERLITE_BATCH": bid}  # O(env)
    try:  # O(1)
        r = subprocess.run(["/bin/sh", "-c", cmd], cwd=str(wt), env=env, capture_output=True, text=True, timeout=CLEANUP_TIMEOUT)  # O(cmd)
    except subprocess.TimeoutExpired:  # O(1)
        return f"{bid} project cleanup: timed out after {CLEANUP_TIMEOUT} s"  # O(1)
    except OSError as e:  # O(1)
        return f"{bid} project cleanup: {e}"  # O(1)
    if r.returncode == 0:  # O(1)
        return None  # O(1)
    lines = [x for x in (r.stdout + r.stderr).splitlines() if x.strip()]  # O(out)
    return f"{bid} project cleanup: exit {r.returncode}" + (f": {lines[-1].strip()[:120]}" if lines else "")  # O(1)


def drop_worktree(root: Path, b: dict) -> list:  # O(cmd)
    bid, wt, br = b.get("id", "?"), b.get("worktree"), b.get("branch") or ""  # O(1)
    if not wt or not Path(wt).is_dir():  # O(1)
        return []  # O(1)
    if Path(wt).resolve() == Path(root).resolve():  # O(1)
        return [f"{bid} worktree {wt} kept: it is the main checkout"]  # O(1)
    out = []  # O(1)
    if b.get("lead"):  # O(1)
        _stop(Path(root) / ".superlite", b["lead"])  # O(w)
    fail = project_cleanup(root, Path(wt), br, bid)  # O(cmd)
    if fail:  # O(1)
        out.append(fail)  # O(1)
    return out + remove_worktree(root, Path(wt), br, bid)  # O(cmd)


def _git_err(msg: str) -> str:  # the last fatal:/error: line of git's output, else ""
    ls = [x.strip() for x in msg.splitlines() if x.strip().startswith(("fatal:", "error:"))]  # O(out)
    return ls[-1][:200] if ls else ""  # O(1)


def remove_worktree(root: Path, wt: Path, branch: str, bid: str, head: str | None = None) -> list:  # O(cmd)
    rc, msg = _run(["git", "worktree", "remove", str(wt)], root)  # O(cmd)
    if rc:  # O(1)
        last = _git_err(msg) or ([x for x in msg.splitlines() if x.strip()] or ["failed"])[-1].strip()[:200]  # O(out)
        return [f"{bid} worktree {wt} kept: {last}"]  # O(1)
    line = f"{bid} worktree {wt} removed"  # O(1)
    if branch:  # O(1)
        rc, _ = _run(["git", "branch", "-d", branch], root)  # O(cmd)
        if rc and head:  # O(1)
            rc2, tip = _run(["git", "rev-parse", branch], root)  # O(cmd)
            if rc2 == 0 and tip.strip() == head and _run(["git", "branch", "-D", branch], root)[0] == 0:  # O(cmd)
                return [line + f", branch {branch} deleted (PR head)"]  # O(1)
        line += f", branch {branch} deleted" if rc == 0 else f", branch {branch} kept (not merged)"  # O(1)
    return [line]  # O(1)


def _shipped(p, sd, root, b, wt, push: bool = True, head: str | None = None) -> list:  # O(size)
    bid = b["id"]
    bs.update(p, lambda d: bs.batch(d, bid).__setitem__("state", "shipped"))  # O(size)
    if b.get("lead"):  # O(1)
        _stop(sd, b["lead"])  # O(w)
    pr = f" PR #{b['pr']}" if b.get("pr") else ""
    ver = f" {b['version']}" if b.get("version") else ""
    fu, un = list(b.get("followups") or []), list(b.get("undone") or [])  # O(k)
    cnt = (f" followups={len(fu)}" if fu else "") + (f" undone={len(un)}" if un else "")  # O(1)
    out = [f"{bid} shipped{pr}{ver} summary={sd / 'backlog' / (bid + '.md')}{cnt}"]
    out.extend(f"{bid} follow-up: {t}" for t in fu)  # O(k)
    out.extend(f"{bid} left undone: {t}" for t in un)  # O(k)
    if b.get("open_issues"):  # O(k)
        out.append(f"{bid} OPEN " + " ".join(bs.ref(n) for n in b["open_issues"]))  # O(k)
    if not b.get("cleaned") and b.get("worktree"):  # O(1)
        fail = project_cleanup(root, Path(b["worktree"]), b.get("branch") or "", bid)  # O(cmd)
        if fail:  # O(1)
            out.append(fail)  # O(1)
    if not b.get("worktree") or wt is None:  # O(1)
        return out  # O(1)
    if push:  # O(1)
        rc, msg = _run(["maxapp", "ship", "-C", str(wt)], root)  # O(cmd)
        if rc:  # O(1)
            line = f"{bid} cleanup: {([x for x in msg.splitlines() if x.strip()] or ['failed'])[-1].strip()[:120]}"  # O(out)
            git_err = _git_err(msg)  # O(out)
            if git_err and git_err not in line:  # O(1)
                line += f": {git_err}"  # O(1)
            import worktree
            cause = worktree.bare_flag(root)  # O(1) + spawn
            out.append(line + (f"; cause: {cause}" if cause else ""))  # O(1)
        owed = out[-1] if rc else None  # O(1)
    else:  # O(1)
        lines = remove_worktree(root, Path(wt), b.get("branch") or "", bid, head)  # O(cmd)
        out.extend(lines)  # O(1)
        owed = lines[0] if " kept: " in lines[0] else None  # O(1)

    def mark(d):  # O(b)
        x = bs.batch(d, bid)
        if owed:
            x["cleanup_owed"] = owed
        else:
            x.pop("cleanup_owed", None)
    bs.update(p, mark)  # O(size)
    return out


def _round(root, sd, p, states) -> list:
    import fleet_io
    import fleet
    import ship_lock
    data = bs.load(p)  # O(size)
    out = []  # O(1)
    for b in [x for x in data["batches"] if x["state"] == "parked" and x.get("agent") and x.get("lead")]:  # O(b)
        if states.get("v") is None:  # O(1)
            try:  # O(1)
                states["v"] = fleet.hc.agent_states()  # O(w)
            except fleet.hc.HerdrError:  # O(1)
                states["v"] = False  # O(1)
        if states["v"] is not False and b["agent"] in states["v"]:  # the lead parked the batch itself and still lives
            try:  # O(1)
                ship_lock.release(ship_lock.lock_path(data.get("repo", "")), b["id"])  # O(1)
            except (OSError, ValueError):  # O(1)
                pass  # O(1)
            _stop(sd, b["lead"])  # O(w)
            out.append(f"{b['id']} parked: {' '.join(str(b.get('reason') or 'parked by its lead').split())[:120]}")  # O(len)
    for b in [x for x in data["batches"] if x["state"] == "running"]:  # O(b)
        bid, wt, since = b["id"], Path(b.get("worktree") or ""), b.get("since", 0)  # O(1)
        rec = fleet_io.latest_stop(sd, b["lead"], since)  # O(m)
        if rec is None:  # O(1)
            if states.get("v") is None:  # O(1)
                try:  # O(1)
                    states["v"] = fleet.hc.agent_states()  # O(w)
                except fleet.hc.HerdrError:  # O(1)
                    states["v"] = False  # O(1)
            if states["v"] is not False and b.get("agent") not in states["v"]:  # O(1)
                if b.get("merged"):  # PR is merged: the lead's pane ending is the normal end
                    out.extend(_shipped(p, sd, root, b, wt))  # O(size)
                    continue  # O(1)
                _park(p, sd, data.get("repo", ""), b, "lead pane gone", out)  # O(size)
            elif isinstance(states["v"], dict) and b.get("agent") in states["v"] and b.get("worktree"):  # O(1)
                out.extend(_gone(p, sd, b, states["v"]))  # O(w)
            continue  # O(1)
        q = wt / ".superlite" / "question.json"  # O(1)
        try:  # O(1)
            fresh = q.stat().st_mtime * 1000 >= since  # O(1)
        except OSError:  # O(1)
            fresh = False  # O(1)
        if fresh:  # O(1)
            try:  # O(1)
                obj = json.loads(q.read_text(encoding="utf-8"))  # O(size)
                cuts = bc.fit_question(obj)  # O(size)
                errs = bc.check_question(obj)  # O(size)
            except (OSError, ValueError, RecursionError):  # O(1)
                cuts, errs = [], ["not JSON"]  # O(1)
            reason = f"invalid question.json: {'; '.join(errs)}"  # O(1)
            if errs and b.get("question_reprompted"):  # O(1)
                _park(p, sd, data.get("repo", ""), b, reason, out)  # O(size)
            elif errs:  # O(1)
                bs.update(p, lambda d, bid=bid: bs.batch(d, bid).update({"question_reprompted": True, "since": _now_ms()}))  # O(size)
                if fleet_io.main(["send", b["lead"], "--text", QUESTION_FIX.format(errs="; ".join(errs[:5])), "--plan", str(sd)]):  # O(w)
                    _park(p, sd, data.get("repo", ""), b, reason, out)  # O(size)
            else:  # O(1)
                bs.update(p, lambda d, bid=bid: bs.batch(d, bid).__setitem__("state", "needs_decision"))  # O(size)
                out.append(f"{bid} needs_decision question={q}")  # O(1)
                out.extend(bc.cut_lines(cuts, f"{bid} "))  # O(c)
            continue  # O(1)
        if b.get("merged"):  # O(1)
            out.extend(_shipped(p, sd, root, b, wt))  # O(size)
            continue  # O(1)
        if rec.get("transcript"):  # O(1)
            try:  # O(1)
                text = str(fleet_io.report_text(rec["transcript"]) or "")  # O(size)
            except Exception:  # O(1)
                text = ""  # O(1)
            lastc = " ".join(str(rec.get("last") or "lead stopped").split())[:120]  # O(len)
            if _lags(text, str(rec.get("last") or "")):  # O(len)
                if _now_ms() - rec.get("t", 0) < fleet_io.READ_MS:  # O(1)
                    continue  # O(1)
                if STATUS.search(str(rec.get("last") or "")):  # O(len)
                    _park(p, sd, data.get("repo", ""), b, f"{lastc} (transcript unread)", out)  # O(size)
                    continue  # O(1)
        if STATUS.search(_stop_text(rec)):  # O(len)
            last = " ".join(str(rec.get("last") or "lead stopped").split())[:120]  # O(len)
            _park(p, sd, data.get("repo", ""), b, last, out)  # O(size)
            continue  # O(1)
        cut = " ".join(str(rec.get("last") or "").split())[:120] or "-"  # O(len)
        reason = f"no status in stop text: {cut}"  # O(1)
        if b.get("reprompted"):  # O(1)
            _park(p, sd, data.get("repo", ""), b, reason, out)  # O(size)
            continue  # O(1)
        bs.update(p, lambda d, bid=bid: bs.batch(d, bid).update({"reprompted": True, "since": _now_ms()}))  # O(size)
        if fleet_io.main(["send", b["lead"], "--text", REPROMPT, "--plan", str(sd)]):  # O(w)
            _park(p, sd, data.get("repo", ""), b, reason, out)  # O(size)
    return out  # O(b)


def cmd_wait(a) -> int:
    root = _root()  # O(1)
    sd, p = root / ".superlite", bs.path(root)  # O(1)
    if not any(b["state"] == "running" or (b["state"] == "parked" and b.get("lead")) for b in bs.load(p)["batches"]):  # O(b)
        print("no running batch")  # O(1)
        return 0  # O(1)
    deadline = time.monotonic() + a.timeout  # O(1)
    while True:  # O(timeout / poll)
        lines = _round(root, sd, p, {})  # O(b * m)
        if lines:  # O(1)
            mline = machine_park_line(lines)  # O(lines)
            print("\n".join(([mline] if mline else []) + lines))  # O(lines)
            return 0  # O(1)
        if not any(b["state"] == "running" for b in bs.load(p)["batches"]):  # O(b)
            print("no running batch")  # O(1)
            return 0  # O(1)
        if time.monotonic() >= deadline:  # O(1)
            print("TIMEOUT")  # O(1)
            return 0  # O(1)
        time.sleep(a.poll)  # O(poll)


def _answers(f, questions=()) -> tuple:  # -> (answers, by map, error)
    try:  # O(1)
        obj = json.loads(Path(f).read_text(encoding="utf-8"))  # O(size)
    except (OSError, ValueError) as e:  # O(1)
        return None, {}, f"cannot read {f}: {e}"  # O(1)
    ans = obj.get("answers") if isinstance(obj, dict) else None  # O(1)
    if not isinstance(ans, dict) or not 1 <= len(ans) <= 4:  # O(1)
        return None, {}, "answers: 1 to 4 entries"  # O(1)
    out = {}  # O(1)
    for k, v in ans.items():  # O(4 * len)
        if not isinstance(k, str) or _ctrl(k):  # O(len)
            return None, {}, f"bad answer for {_clean(str(k))[:60]}"  # O(len)
        q = next((x for x in questions if isinstance(x, dict) and x.get("question") == k), {})  # O(q)
        text, why = ba.answer_text(v, ba.labels_of(q), False)  # O(len)
        if text is None:  # O(1)
            return None, {}, f"bad answer for {_clean(k)[:60]}: {why}"  # O(len)
        out[k] = text  # O(1)
    by, err = bc.answer_by(obj, out)  # O(4)
    return (out, by, "") if not err else (None, {}, err)  # O(1)


def cmd_answer(a) -> int:
    import fleet_io
    if os.environ.get("SUPERLITE_FLEET_WORKER"):  # only Max's session runs this; never a lead or worker
        return _refuse("sl backlog_run answer runs only in the main session")  # O(1)
    root = _root()  # O(1)
    sd, p = root / ".superlite", bs.path(root)  # O(1)
    try:  # O(1)
        b = bs.batch(bs.load(p), a.batch)  # O(b)
    except KeyError:  # O(1)
        return _refuse(f"unknown batch {a.batch}")  # O(1)
    if b["state"] != "needs_decision":  # O(1)
        return _refuse(f"{a.batch} is {b['state']}, not waiting for an answer")  # O(1)
    ed = Path(b["worktree"]) / ".superlite"  # O(1)
    q = ed / "question.json"  # O(1)
    try:  # O(1)
        qs = json.loads(q.read_text(encoding="utf-8")).get("questions") or []  # O(size)
    except (OSError, ValueError, AttributeError):  # O(1)
        qs = []  # O(1)
    ans, by, err = _answers(a.file, qs)  # O(size)
    if ans is None:  # O(1)
        return _refuse(err)  # O(1)
    n = int(b.get("questions", 0)) + 1  # O(1)
    if q.is_file():  # O(1)
        q.replace(ed / f"question-{n}.json")  # O(1)
    af = ed / f"answer-{n}.json"  # O(1)
    af.write_text(json.dumps({"answers": ans, "by": by}, indent=2), encoding="utf-8")  # O(size)

    def mark(d):  # O(b)
        x = bs.batch(d, a.batch)
        x.setdefault("answers", {}).update(ans)
        x.setdefault("answered_by", {}).update(by)
        x.update({"questions": n, "state": "running", "since": _now_ms(), "reprompted": False, "question_reprompted": False})
    bs.update(p, mark)  # O(size)
    if "main" in by.values():  # O(4)
        msg = ANSWER_MAIN.format(af=af)  # O(1)
    else:  # O(1)
        msg = f"Max answered your question: read {af} (record it as a Ruling), then go on with the batch."  # O(1)
    rc = fleet_io.main(["send", b["lead"], "--text", msg, "--plan", str(sd)])  # O(w)
    if rc:  # O(1)
        bs.update(p, lambda d: bs.batch(d, a.batch).__setitem__("state", "needs_decision"))  # O(size)
        return 3  # O(1)
    print(f"{a.batch} answered: {af.name} sent to {b['lead']}")  # O(1)
    return 0  # O(1)


def cmd_tell(a) -> int:
    import fleet_io
    if os.environ.get("SUPERLITE_FLEET_WORKER"):  # only Max's session runs this; never a lead or worker
        return _refuse("sl backlog tell runs only in the main session")  # O(1)
    root = _root()  # O(1)
    sd, p = root / ".superlite", bs.path(root)  # O(1)
    try:  # O(1)
        b = bs.batch(bs.load(p), a.batch)  # O(b)
    except KeyError:  # O(1)
        return _refuse(f"unknown batch {a.batch}")  # O(1)
    if b["state"] == "needs_decision":  # O(1)
        return _refuse(f"{a.batch} waits for an answer: sl backlog answer {a.batch} --file F")  # O(1)
    if b["state"] != "running" or not b.get("lead"):  # O(1)
        return _refuse(f"{a.batch} is {b['state']}; only a running batch has a lead to tell")  # O(1)
    if not a.text.strip() or len(a.text) > 2000 or _ctrl(a.text):  # O(len)
        return _refuse("--text: 1 to 2000 characters, no control characters")  # O(1)
    if fleet_io.main(["send", b["lead"], "--text", TELL.format(text=a.text), "--plan", str(sd)]):  # O(w)
        return _refuse(f"{a.batch} lead {b['lead']} not told (fleet send failed)", 3)  # O(1)
    print(f"{a.batch} told lead {b['lead']}")  # O(1)
    return 0  # O(1)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="backlog_run")  # O(1)
    sub = ap.add_subparsers(dest="cmd", required=True)  # O(1)
    s = sub.add_parser("start")  # O(1)
    s.add_argument("batch", nargs="*")  # O(1)
    s.add_argument("--cap", type=int, default=2)  # O(1)
    s.add_argument("--model", default="opus")  # O(1)
    s.add_argument("--machine-wait", type=float, default=100)  # O(1)
    s.add_argument("--over-limit", action="store_true")  # O(1)
    w = sub.add_parser("wait")  # O(1)
    w.add_argument("--timeout", type=int, default=21600)  # O(1)
    w.add_argument("--poll", type=int, default=10)  # O(1)
    an = sub.add_parser("answer")  # O(1)
    an.add_argument("batch")  # O(1)
    an.add_argument("--file", required=True)  # O(1)
    t = sub.add_parser("tell")  # O(1)
    t.add_argument("batch")  # O(1)
    t.add_argument("--text", required=True)  # O(1)
    a = ap.parse_args(argv)  # O(1)
    return {"start": cmd_start, "wait": cmd_wait, "answer": cmd_answer, "tell": cmd_tell}[a.cmd](a)  # O(1)


if __name__ == "__main__":
    sys.exit(main())
