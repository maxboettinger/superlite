#!/usr/bin/env python3
"""sl backlog: status, plan (triage worker proposes batches), decide (Max's answers); start|wait|answer and ship are routed."""
# Complexity notation: i = open issues, b = batches, q = questions
import argparse  # O(1)
import copy  # O(1)
import json  # O(1)
import os  # O(1)
import re  # O(1)
import subprocess  # O(1)
import sys  # O(1)
import time  # O(1)
from datetime import datetime, timezone  # O(1)
from pathlib import Path  # O(1)

TRUSTED = ("OWNER", "MEMBER", "COLLABORATOR")  # O(1)
MAX_BATCHES = 7  # O(1)
ROUTED = ("start", "wait", "answer")  # O(1)


def _root() -> Path:
    import backlog_state as bs  # O(1)
    return bs.main_root(Path.cwd())  # O(1)


ISSUES_JQ = (".[] | select(has(\"pull_request\") | not) | {number, title, body, author: {login: .user.login}, "
             "authorAssociation: .author_association}")
BODY_LIMIT = 4000  # characters of one issue body kept in the triage brief


def _body(s) -> str:
    s = str(s or "")
    return s if len(s) <= BODY_LIMIT else s[:BODY_LIMIT] + "\n[truncated]"


def _gh(args: list):
    try:  # O(1)
        r = subprocess.run(["gh", *args], capture_output=True, text=True, timeout=120)  # O(network)
        if r.returncode:  # O(1)
            raise RuntimeError(f"gh {' '.join(args[:2])} failed: {(r.stderr or '').strip()[:200]}")  # O(1)
        if "--paginate" in args:  # O(1): --jq output is one JSON object per line
            return [json.loads(x) for x in r.stdout.splitlines() if x.strip()]  # O(size)
        return json.loads(r.stdout)  # O(size)
    except (OSError, ValueError, subprocess.TimeoutExpired) as e:  # O(1)
        raise RuntimeError(f"gh {' '.join(args[:2])} failed: {e}") from None  # O(1)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")  # O(1)


def _num(bid: str) -> int:
    return int(re.sub(r"\D", "", bid) or 0)  # O(1)


def _renumber(new: list, kept: list) -> list:
    base = max([_num(b["id"]) for b in kept], default=0)  # O(b)
    ids = {b["id"]: f"B{base + n}" for n, b in enumerate(new, 1)}  # O(b)
    for b in new:  # O(b * deps)
        b["id"] = ids[b["id"]]
        b["depends"] = [ids.get(d, d) for d in b["depends"]]
    return new


def _author(i: dict) -> str:
    a = i.get("author")
    return (a.get("login", "") if isinstance(a, dict) else str(a or ""))  # O(1)


def _triage(sd: Path, root: Path, trusted: list, repo: str, tier: str, timeout_min: int):
    """Run the triage worker; returns (proposal, None) or (None, error line list)."""
    import backlog_brief  # O(1)
    import fleet  # O(1)
    import fleet_io  # O(1)
    import fleet_state  # O(1)
    brief = sd / "briefs" / "triage.md"
    brief.parent.mkdir(parents=True, exist_ok=True)
    brief.write_text(backlog_brief.triage_brief(trusted, {"repo": repo, "max_batches": MAX_BATCHES}))  # O(i)
    if not fleet_state.is_on(sd):  # O(w)
        fleet.main(["on", "--plan", str(sd)])
    w = fleet.spawn(sd, sd, tier, root, role="research")
    wid = w["id"]
    fleet_io.send_brief(sd, wid, str(brief), "triage")
    deadline = time.time() + timeout_min * 60
    while True:  # O(timeout)
        if fleet_io.wait(sd, [wid], 540000):
            break
        if time.time() >= deadline:
            return None, [f"BLOCKED: triage worker {wid} did not finish in {timeout_min} minutes"]
    import backlog_checks as bc  # O(1)
    rp = sd / "fleet" / "reports" / "triage.md"
    try:
        text = rp.read_text()  # O(size)
    except OSError:
        text = ""
    prop = bc.proposal_from(text)
    if prop is None:
        return None, ["BLOCKED: no proposal block in the triage report"]
    return prop, None


def cmd_plan(a) -> int:
    import backlog_checks as bc  # O(1)
    import backlog_state as bs  # O(1)
    root = _root()
    sd, p = root / ".superlite", bs.path(root)
    d = bs.load(p)
    open_ = [b for b in d["batches"] if b["state"] != "shipped"]
    if open_ and (not a.reset or any(b["state"] in ("running", "needs_decision") for b in open_)):
        print("BLOCKED: backlog has open batches (" + ", ".join(f"{b['id']} {b['state']}" for b in open_) + ")")
        return 2
    info = _gh(["repo", "view", "--json", "nameWithOwner,visibility"])
    issues = _gh(["api", "--paginate", "repos/{owner}/{repo}/issues?state=open&per_page=100", "--jq", ISSUES_JQ])[:200]
    admitted, skipped = set(d["admitted"]), set(d["skipped"])
    public = info.get("visibility") == "PUBLIC"
    trusted, outside = [], []
    for i in issues:  # O(i)
        n = i["number"]
        if n in skipped:
            continue
        if not public or i.get("authorAssociation") in TRUSTED or n in admitted:
            trusted.append({"number": n, "title": i.get("title", ""), "body": _body(i.get("body"))})
        else:
            outside.append({"number": n, "title": i.get("title", ""), "author": _author(i)})
    prop, err = _triage(sd, root, trusted, info["nameWithOwner"], a.tier, a.timeout_min)
    if err:
        print("\n".join(err))
        return 3
    batches, errs = bc.check_proposal(prop, {t["number"] for t in trusted})
    if errs:
        why = " ".join(re.sub(r"[\x00-\x1f\x7f]", " ", str(prop.get("summary", ""))).split())[:300]
        print("BLOCKED: proposal rejected\n" + "\n".join(errs[:5]) + f"\ntriage worker {prop.get('status', '?')}: {why or 'no summary'}")
        return 3
    batches = bc.separate(batches)
    shown = {}

    def apply(data):
        live = [b for b in data["batches"] if b["state"] != "shipped" and (not a.reset or b["state"] in ("running", "needs_decision"))]
        if live:  # a batch changed while the triage worker ran: never overwrite it
            raise RuntimeError("backlog changed while triage ran (" + ", ".join(f"{b['id']} {b['state']}" for b in live) + ")")
        data["batches"] = [b for b in data["batches"] if b["state"] == "shipped"]
        data["repo"] = info["nameWithOwner"]
        data["titles"] = {str(t["number"]): t["title"] for t in trusted}
        data["outside"] = outside
        data["batches"] += _renumber(copy.deepcopy(batches), data["batches"])
        shown["lines"] = bs.status_lines(data)
    bs.update(p, apply)
    print("\n".join(shown["lines"]))
    return 0


def cmd_decide(a) -> int:
    import backlog_checks as bc  # O(1)
    import backlog_state as bs  # O(1)
    if os.environ.get("SUPERLITE_FLEET_WORKER"):  # only Max's session records answers; never a lead or worker
        print("refused: sl backlog decide runs only in the main session")
        return 2
    root = _root()
    p = bs.path(root)
    d = bs.load(p)
    if a.print:
        if not a.batch:
            print(json.dumps({"questions": bs.open_questions(d)}, indent=2))
            return 0
        try:
            b = bs.batch(d, a.batch)
            q = json.loads((Path(b["worktree"]) / ".superlite" / "question.json").read_text())
        except (KeyError, TypeError, OSError, ValueError) as e:
            print(f"BLOCKED: {a.batch} question.json unreadable: {e}")
            return 3
        errs = bc.check_question(q)
        if errs:
            print(f"BLOCKED: {a.batch} question.json invalid: " + "; ".join(errs[:5]))
            return 3
        print(json.dumps(bc.clean_question(q), indent=2))
        return 0
    if not a.file:
        print("BLOCKED: decide needs --print or --file")
        return 2
    try:
        answers = json.loads(Path(a.file).read_text())["answers"]
        assert isinstance(answers, dict)
    except (OSError, ValueError, KeyError, AssertionError):
        print(f"BLOCKED: {a.file} is not {{\"answers\": {{question: answer}}}}")
        return 2
    res = {}

    def apply(data):
        c = copy.deepcopy(data)
        errs = bs.answer(c, answers, "AskUserQuestion", _now())
        res["errs"] = errs
        if not errs:
            data.clear()
            data.update(c)
        res["open"] = len(bs.open_questions(data))
    bs.update(p, apply)
    if res["errs"]:
        print("\n".join(res["errs"]))
        return 2
    print(f"recorded {len(answers)} answers, {res['open']} open")
    return 0


def cmd_status(a) -> int:
    import backlog_state as bs  # O(1)
    print("\n".join(bs.status_lines(bs.load(bs.path(_root())))))
    return 0


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in ROUTED:
        import backlog_run  # O(1)
        return backlog_run.main(argv)
    if argv and argv[0] == "ship":
        import backlog_ship  # O(1)
        return backlog_ship.main(argv[1:])
    ap = argparse.ArgumentParser(prog="sl backlog")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status").set_defaults(fn=cmd_status)
    pl = sub.add_parser("plan")
    pl.add_argument("--tier", default="sonnet")
    pl.add_argument("--timeout-min", type=int, default=60)
    pl.add_argument("--reset", action="store_true")
    pl.set_defaults(fn=cmd_plan)
    de = sub.add_parser("decide")
    de.add_argument("--print", action="store_true")
    de.add_argument("--batch")
    de.add_argument("--file")
    de.set_defaults(fn=cmd_decide)
    a = ap.parse_args(argv)
    try:
        return a.fn(a)
    except RuntimeError as e:
        print(f"BLOCKED: {e}")
        return 3


if __name__ == "__main__":
    sys.exit(main())
