#!/usr/bin/env python3
"""sl backlog: status, plan (triage worker proposes batches, or plan --proposal FILE applies a kept or repaired proposal through the same checks, no worker; over-long question texts are shortened and named; a plan clears the ship approval and lists left-out issues), decide (Max's answers; decide --print --batch cuts a lead's question like plan), skip <issue>, plan --jql/--issues reads a Jira backlog through acli, plan --issues also pins GitHub numbers (362,#433), issues an earlier cap left out are ranked first and named in the brief (#433), park <batch> --reason R; a plan refused by planned or parked batches names --reset, and status with no batch open ends with next: sl backlog plan (#369); a plan records its round, status counts the shipped batches of earlier rounds in one line and status --all lists them (#406); start|wait|answer and ship are routed; plan --issues X --add plans an urgent issue next to open batches and keeps running ones and the ship approval (#505); start --note FILE stores a standing note every lead brief carries (#504); tell B --text T messages a running lead (#487); decide --file records who answered (by: user, main or a per-question map, #477) and decide --approve-ship --source prompt records an approval the user's prompt gave; skip also takes an issue out of a parked batch and stops a parked batch's lead once it is empty (#506)."""
# Complexity notation: i = open issues, b = batches, q = questions
import argparse  # O(1)
import copy  # O(1)
import json  # O(1)
import os  # O(1)
import re  # O(1)
import shlex  # O(1)
import shutil  # O(1)
import subprocess  # O(1)
import sys  # O(1)
import time  # O(1)
from datetime import datetime, timezone  # O(1)
from pathlib import Path  # O(1)

TRUSTED = ("OWNER", "MEMBER", "COLLABORATOR")  # O(1)
MAX_BATCHES = 7  # O(1)
ISSUE_LIMIT = 200  # O(1)
ROUTED = ("start", "wait", "answer", "tell")  # O(1)
KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]*-[1-9][0-9]*$")  # O(1)
GH_RE = re.compile(r"^#?[1-9][0-9]*$")  # O(1)
CAP_RE = re.compile(r"^not (?:planned \(cap\)|triaged \(\d+ cap\))$")  # O(1)
ACLI_TIMEOUT = 300  # O(1)
BLOCKS = ("paragraph", "heading", "codeBlock", "blockquote", "listItem", "tableRow", "panel", "rule")  # O(1)
MAX_DEPTH = 100  # O(1)


def _root() -> Path:
    import backlog_state as bs  # O(1)
    return bs.main_root(Path.cwd())  # O(1)


TEST_CMD = Path(".superlite") / "test-cmd.json"  # O(1)


def seed_test_cmd(root: Path, wt: Path) -> bool:
    """Copy the main checkout's .superlite/test-cmd.json into a new lead worktree (#334).

    Only when the main checkout has the file and the worktree has none (a lead's own file is kept).
    A failed copy prints one stderr line and returns False; `backlog start` goes on."""
    src, dst = Path(root) / TEST_CMD, Path(wt) / TEST_CMD  # O(1)
    if not src.is_file() or os.path.lexists(dst):  # O(1)
        return False  # O(1)
    try:  # O(1)
        dst.parent.mkdir(parents=True, exist_ok=True)  # O(1)
        shutil.copyfile(src, dst)  # O(size)
    except OSError as e:  # O(1)
        print(f"test-cmd.json not seeded into {wt}: {e}", file=sys.stderr)  # O(1)
        return False  # O(1)
    return True  # O(1)


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


def _acli(args: list):
    name = " ".join(args[:3])  # O(1)
    try:  # O(1)
        r = subprocess.run(["acli", *args], capture_output=True, text=True, timeout=ACLI_TIMEOUT)  # O(network)
    except FileNotFoundError:  # O(1)
        raise RuntimeError("acli not found: install the Atlassian CLI and run `acli jira auth login`") from None  # O(1)
    except (OSError, ValueError, subprocess.TimeoutExpired) as e:  # O(1) ValueError: output not decodable
        raise RuntimeError(f"acli {name} failed: {e}") from None  # O(1)
    if r.returncode:  # O(1)
        msg = " ".join(re.sub(r"^[✗\s]+", "", (r.stderr or r.stdout or "").strip()).split())[:200]  # O(len)
        raise RuntimeError(f"acli {name} failed: {msg}")  # O(1)
    try:  # O(1)
        return json.loads(r.stdout)  # O(size)
    except (ValueError, RecursionError):  # O(1)
        raise RuntimeError(f"acli {name} gave no JSON") from None  # O(1)


def adf_text(node) -> str:
    """Plain text of an Atlassian Document Format value; iterative, nodes deeper than MAX_DEPTH are dropped."""
    out: list = []  # O(1)
    stack: list = [(node, 0)]  # O(1)
    while stack:  # O(nodes)
        n, depth = stack.pop()  # O(1)
        if isinstance(n, str):  # O(1)
            out.append(n)  # O(1)
            continue  # O(1)
        if not isinstance(n, dict) or depth > MAX_DEPTH:  # O(1)
            continue  # O(1)
        t, at = n.get("type"), n.get("attrs")  # O(1)
        at = at if isinstance(at, dict) else {}  # O(1)
        if t == "text":  # O(1)
            out.append(n.get("text") if isinstance(n.get("text"), str) else "")  # O(1)
        elif t == "hardBreak":  # O(1)
            out.append("\n")  # O(1)
        elif t == "mention":  # O(1)
            out.append(str(at.get("text") or ""))  # O(1)
        elif t == "emoji":  # O(1)
            out.append(str(at.get("text") or at.get("shortName") or ""))  # O(1)
        elif t in ("inlineCard", "blockCard"):  # O(1)
            out.append(str(at.get("url") or ""))  # O(1)
        else:  # O(1)
            kids = n.get("content") if isinstance(n.get("content"), list) else []  # O(1)
            if t in BLOCKS:  # O(1)
                stack.append(("\n", depth))  # O(1)
            stack.extend((k, depth + 1) for k in reversed(kids))  # O(kids)
            if t == "listItem":  # O(1)
                stack.append(("- ", depth))  # O(1)
    return re.sub(r"\n{3,}", "\n\n", "".join(out)).strip()  # O(len)


def jira_keys(text: str) -> list:
    keys: list = []  # O(1)
    for item in re.split(r"[,\s]+", text or ""):  # O(len)
        if not item:  # O(1)
            continue  # O(1)
        if not KEY_RE.fullmatch(item.upper()):  # O(1)
            raise ValueError(f"not a Jira key: {item}")  # O(1)
        if item.upper() not in keys:  # O(keys)
            keys.append(item.upper())  # O(1)
    return keys  # O(1)


def pin_list(text: str) -> tuple:
    """--issues list: (False, [GitHub numbers]) or (True, [Jira keys]); the first item picks the source."""
    items = [x for x in re.split(r"[,\s]+", text or "") if x]  # O(len)
    if not items:  # O(1)
        return False, []  # O(1)
    if GH_RE.fullmatch(items[0]):  # O(1)
        nums: list = []  # O(1)
        for item in items:  # O(len)
            if not GH_RE.fullmatch(item):  # O(1)
                raise ValueError(f"not a GitHub issue number: {item}")  # O(1)
            if int(item.lstrip("#")) not in nums:  # O(nums)
                nums.append(int(item.lstrip("#")))  # O(1)
        return False, nums  # O(1)
    if KEY_RE.fullmatch(items[0].upper()):  # O(1)
        return True, jira_keys(text)  # O(len)
    raise ValueError(f"not a GitHub issue number or Jira key: {items[0]}")  # O(1)


def pinned_issues(issues: list, nums: list) -> list:
    """The fetched issues of nums, in nums order; a number not among them raises."""
    by = {i["number"]: i for i in issues}  # O(i)
    for n in nums:  # O(nums)
        if n not in by:  # O(1)
            raise RuntimeError(f"GitHub issue #{n} not found among the open issues")  # O(1)
    return [by[n] for n in nums]  # O(nums)


def carry_rounds(outside) -> dict:
    """{number: rounds} of the issues an earlier cap left out."""
    out: dict = {}  # O(1)
    for o in outside if isinstance(outside, list) else []:  # O(outside)
        if not isinstance(o, dict) or not isinstance(o.get("reason"), str) or not CAP_RE.fullmatch(o["reason"]):  # O(1)
            continue  # O(1)
        n = o.get("number")  # O(1)
        if isinstance(n, bool) or not isinstance(n, (int, str)):  # O(1)
            continue  # O(1)
        r = o.get("rounds")  # O(1)
        out[n] = r if isinstance(r, int) and not isinstance(r, bool) and r >= 1 else 1  # O(1)
    return out  # O(1)


JIRA_WORD = re.compile(r"(?i)\bjira\b")  # O(1)


def jira_named(root: Path) -> bool:
    """True when root/AGENTS.md or root/CLAUDE.md names Jira (an unreadable file does not)."""
    for f in ("AGENTS.md", "CLAUDE.md"):  # O(1)
        try:  # O(1)
            if JIRA_WORD.search((Path(root) / f).read_text(encoding="utf-8", errors="replace")):  # O(size)
                return True  # O(1)
        except OSError:  # O(1)
            continue  # O(1)
    return False  # O(1)


def remembered_source(source, root: Path) -> tuple:
    """(jql, line, err) of a plain plan: the remembered source, else a refusal when the docs name Jira."""
    if isinstance(source, dict) and source.get("tracker") == "jira":  # O(1)
        jql = source.get("jql")  # O(1)
        if isinstance(jql, str) and jql.strip():  # O(1)
            return jql, f'source: Jira --jql "{jql}" (remembered from the last plan; --github, --jql or --issues picks another)', None  # O(1)
        return None, None, ('BLOCKED: the last plan read Jira issues by key and remembers no JQL; run sl backlog plan --jql "<query>", '
                            '--issues KEYS or --github')  # O(1)
    if isinstance(source, dict) and source.get("tracker") == "github":  # O(1)
        return None, None, None  # O(1)
    if jira_named(root):  # O(1)
        return None, None, ('BLOCKED: no backlog source remembered and AGENTS.md or CLAUDE.md names Jira; run sl backlog plan --jql "<query>" '
                            'for Jira issues or --github for GitHub issues (--issues pins single issues); a plain plan then reuses the choice')  # O(1)
    return None, None, None  # O(1)


def jira_issues(jql, keys) -> list:
    if keys:  # O(1)
        jql = "key in (" + ", ".join(keys) + ")"  # O(keys)
    res = _acli(["jira", "workitem", "search", "--jql", jql, "--fields", "key,summary,description", "--paginate", "--json"])  # O(network)
    if not isinstance(res, list):  # O(1)
        raise RuntimeError("acli search gave no issue list")  # O(1)
    found: list = []  # O(1)
    for it in res:  # O(i)
        key = it.get("key") if isinstance(it, dict) else None  # O(1)
        if not isinstance(key, str) or not KEY_RE.fullmatch(key):  # O(1)
            continue  # O(1)
        f = it.get("fields") if isinstance(it.get("fields"), dict) else {}  # O(1)
        found.append({"number": key, "title": str(f.get("summary") or ""), "body": _body(adf_text(f.get("description")))})  # O(body)
    if not keys:  # O(1)
        return found  # O(1)
    by = {x["number"]: x for x in found}  # O(i)
    for k in keys:  # O(keys)
        if k not in by:  # O(1)
            raise RuntimeError(f"Jira issue {k} not found")  # O(1)
    return [by[k] for k in keys]  # O(keys)


def _key_proposal(prop, keys: list):
    """Copy of prop whose batch issues hold stand-in numbers: trusted key i -> i, any other item -> a number above; returns (copy, back)."""
    pos = {k: n for n, k in enumerate(keys, 1)}  # O(i)
    back = {n: k for k, n in pos.items()}  # O(i)
    odd: dict = {}  # O(1)
    cp = copy.deepcopy(prop)  # O(size)
    bl = cp.get("batches") if isinstance(cp, dict) else None  # O(1)
    for b in bl if isinstance(bl, list) else []:  # O(b * issues)
        its = b.get("issues") if isinstance(b, dict) else None  # O(1)
        if not isinstance(its, list):  # O(1)
            continue  # O(1)
        new = []  # O(1)
        for it in its:  # O(issues)
            k = it.upper() if isinstance(it, str) else None  # O(1)
            if k in pos:  # O(1)
                new.append(pos[k])  # O(1)
                continue  # O(1)
            t = str(it)  # O(1)
            n = odd.setdefault(t, len(keys) + len(odd) + 1)  # O(1)
            back[n] = t  # O(1)
            new.append(n)  # O(1)
        b["issues"] = new  # O(1)
    return cp, back  # O(1)


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


def _triage(sd: Path, root: Path, trusted: list, repo: str, tier: str, timeout_min: int, carry=None, cap=None, open_=None):
    """Run the triage worker; returns (proposal, None) or (None, error line list)."""
    import backlog_brief  # O(1)
    import fleet  # O(1)
    import fleet_io  # O(1)
    import fleet_state  # O(1)
    brief = sd / "briefs" / "triage.md"
    brief.parent.mkdir(parents=True, exist_ok=True)
    brief.write_text(backlog_brief.triage_brief(trusted, {"repo": repo, "max_batches": cap or MAX_BATCHES, "carry": carry or {}, "open": open_ or []}))  # O(i)
    if not fleet_state.is_on(sd):  # O(w)
        fleet.main(["on", "--plan", str(sd)])
    w = fleet.spawn(sd, sd, tier, root, role="research")
    wid = w["id"]
    import herdr_client as hc  # O(1)
    try:  # O(1)
        fleet_io.send_brief(sd, wid, str(brief), "triage")  # O(w)
    except hc.HerdrError as e:  # O(1)
        try:  # O(1)
            fleet.stop(sd, [wid])  # O(w)
        except (Exception, SystemExit):  # O(1)
            pass  # O(1)
        return None, [f"BLOCKED: triage worker {wid} got no brief ({e}); worker stopped"]  # O(1)
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


def _read_proposal(f: str):
    import backlog_checks as bc  # O(1)
    try:  # O(1)
        text = Path(f).read_text(encoding="utf-8-sig")  # O(len)
    except (OSError, ValueError) as e:
        return None, f"BLOCKED: proposal {f} unreadable: {e}"
    try:  # O(1)
        o = json.loads(text)  # O(len)
    except (ValueError, RecursionError):
        o = bc.proposal_from(text)  # O(len)
    if not isinstance(o, dict):
        return None, f"BLOCKED: proposal {f} holds no JSON object"
    return o, None


RESET_HINT = "; sl backlog plan --reset drops them and plans every open issue again (shipped batches stay)"  # O(1) #369
BUSY_HINT = "; --reset is refused too while a batch is running or needs_decision"  # O(1) #369


def open_refusal(open_: list, busy: list) -> str:
    """The plan refusal while batches are open; it names --reset only when only planned or parked batches block (#369)."""
    head = "BLOCKED: backlog has open batches (" + ", ".join(f"{b['id']} {b['state']}" for b in open_) + ")"  # O(b)
    return head + (BUSY_HINT if busy else RESET_HINT)  # O(1)


ADD_HINT = "; --add plans the --issues next to them"  # O(1) #505


def open_batches(data: dict) -> list:
    """The batches not shipped yet as {id, state, files}, in id order."""
    rows = [{"id": b["id"], "state": b["state"], "files": list(b.get("files", []))} for b in data.get("batches", []) if b["state"] != "shipped"]  # O(b * files)
    return sorted(rows, key=lambda b: _num(b["id"]))  # O(b log b)


def overlap_lines(new: list, open_: list) -> list:
    """One line per new batch and open batch that share files; says who holds the files."""
    out = []  # O(1)
    for n in new:  # O(new * open * files)
        for o in open_:  # O(open * files)
            both = sorted(set(n.get("files", [])) & set(o.get("files", [])))  # O(files)
            if not both:  # O(1)
                continue  # O(1)
            shown = ", ".join(both[:3]) + (f" (+{len(both) - 3} more)" if len(both) > 3 else "")  # O(1)
            tail = f"start holds {n['id']} until {o['id']} ships" if o["state"] in ("running", "needs_decision") else "whichever starts first holds the files"  # O(1)
            out.append(f"overlap: {n['id']} shares {shown} with {o['id']} ({o['state']}): {tail}")  # O(1)
    return out  # O(1)


def _left_out(n, title: str, why: str, carry: dict) -> dict:
    """An outside[] entry for a left-out issue; a cap entry seen before counts its rounds."""
    e = {"number": n, "title": title, "reason": why}  # O(1)
    if CAP_RE.fullmatch(why) and carry.get(n, 0) + 1 >= 2:  # O(1)
        e["rounds"] = carry.get(n, 0) + 1  # O(1)
    return e  # O(1)


def cmd_plan(a) -> int:
    import backlog_checks as bc  # O(1)
    import backlog_state as bs  # O(1)
    proposal = getattr(a, "proposal", None)
    root = _root()
    sd, p = root / ".superlite", bs.path(root)
    d = bs.load(p)
    open_ = [b for b in d["batches"] if b["state"] != "shipped"]
    busy = [b for b in open_ if b["state"] in ("running", "needs_decision")]  # O(b) --reset never drops these
    add = bool(getattr(a, "add", False))  # O(1)
    if add and getattr(a, "issues", None) is None:  # O(1)
        print("BLOCKED: --add needs --issues")  # O(1)
        return 2  # O(1)
    if add and a.reset:  # O(1)
        print("BLOCKED: --add and --reset exclude each other")  # O(1)
        return 2  # O(1)
    add = add and bool(open_)  # O(1) without open batches it is a plain pinned plan
    if open_ and not add and (not a.reset or busy):  # O(1)
        print(open_refusal(open_, busy) + (ADD_HINT if getattr(a, "issues", None) is not None else ""))  # O(b)
        return 2
    prop = None
    if proposal is not None:
        prop, perr = _read_proposal(proposal)
        if perr:
            print(perr)
            return 2
    jql, keys, pin, pin_jira = getattr(a, "jql", None), None, None, False  # O(1)
    cap = getattr(a, "max_batches", None)  # O(1)
    if cap is not None and not 1 <= cap <= 20:  # O(1)
        print("BLOCKED: --max-batches: 1 to 20")  # O(1)
        return 2  # O(1)
    github = bool(getattr(a, "github", False))  # O(1)
    if getattr(a, "issues", None) is not None:
        try:
            pin_jira, pin = pin_list(a.issues)  # O(len)
        except ValueError as e:
            print(f"BLOCKED: --issues: {e}")
            return 2
        if not pin:
            print("BLOCKED: --issues is empty")
            return 2
        for n in pin:  # O(pin * skipped)
            if n in d["skipped"]:  # O(skipped)
                print(f"BLOCKED: --issues: {'#' + str(n) if isinstance(n, int) else n} is skipped")  # O(1)
                return 2  # O(1)
        keys = pin if pin_jira else None  # O(1)
        if add:  # O(1)
            for b in open_:  # O(b * issues * pin)
                hit = next((n for n in pin if n in b.get("issues", [])), None)  # O(issues * pin)
                if hit is not None:  # O(1)
                    print(f"BLOCKED: --issues: {bs.ref(hit)} is in {b['id']} ({b['state']})")  # O(1)
                    return 2  # O(1)
    if jql is not None and not jql.strip():
        print("BLOCKED: --jql is empty")
        return 2
    line = None  # O(1)
    if jql is None and getattr(a, "issues", None) is None and not github:  # O(1) a plain plan reuses the remembered source
        jql, line, err = remembered_source(d.get("source"), root)  # O(1)
        if err:  # O(1)
            print(err)  # O(1)
            return 2  # O(1)
    if line:  # O(1)
        print(line)  # O(1)
    cap = cap or MAX_BATCHES  # O(1)
    jira = jql is not None or keys is not None
    info = _gh(["repo", "view", "--json", "nameWithOwner,visibility"])
    if jira:
        issues = jira_issues(jql, keys)
    else:
        issues = _gh(["api", "--paginate", "repos/{owner}/{repo}/issues?state=open&per_page=100", "--jq", ISSUES_JQ])
        if pin is not None:  # O(1)
            try:  # O(1)
                issues = pinned_issues(issues, pin)  # O(i)
            except RuntimeError as e:  # O(1)
                print(f"BLOCKED: {e}")  # O(1)
                return 3  # O(1)
    carry = carry_rounds(d["outside"])  # O(outside)
    issues = sorted(issues, key=lambda i: -carry.get(i["number"], 0))  # O(i log i)
    rest = issues[ISSUE_LIMIT:]
    issues = issues[:ISSUE_LIMIT]
    admitted, skipped = set(d["admitted"]), set(d["skipped"])
    public = not jira and info.get("visibility") == "PUBLIC"
    trusted, outside = [], []
    for i in issues:  # O(i)
        n = i["number"]
        if n in skipped:
            continue
        if not public or i.get("authorAssociation") in TRUSTED or n in admitted:
            trusted.append({"number": n, "title": i.get("title", ""), "body": _body(i.get("body"))})
        else:
            outside.append({"number": n, "title": i.get("title", ""), "author": _author(i)})
    if proposal is None:
        prop, err = _triage(sd, root, trusted, info["nameWithOwner"], a.tier, a.timeout_min, carry, cap, **({"open_": open_batches(d)} if add else {}))  # O(i)
        if err:
            print("\n".join(err))
            return 3
    cuts = bc.cut_lines(bc.fit_proposal(prop))  # O(q)
    if jira:
        cp, back = _key_proposal(prop, [t["number"] for t in trusted])
        batches, errs = bc.check_proposal(cp, set(range(1, len(trusted) + 1)))
        errs = [re.sub(r"(?:(?<=unknown issue )|^)#(\d+)(?= is in |$)", lambda m: back.get(int(m.group(1)), m.group(0)), e).replace("list of numbers", "list of Jira keys") for e in errs]  # O(errs)
    else:
        batches, errs = bc.check_proposal(prop, {t["number"] for t in trusted})
    if errs:
        why = " ".join(re.sub(r"[\x00-\x1f\x7f]", " ", str(prop.get("summary", ""))).split())[:300]
        kept = sd / "backlog-proposal.json"
        try:
            kept.write_text(json.dumps(prop, indent=2), encoding="utf-8")
            where = f"\nproposal kept: {kept}"
        except (OSError, TypeError, ValueError, RecursionError):
            where = ""
        nb = len(prop["batches"]) if isinstance(prop.get("batches"), list) else 0  # O(1)
        held = f" (the proposal holds {nb} batch{'' if nb == 1 else 'es'})"  # O(1)
        print("BLOCKED: proposal rejected\n" + "\n".join(errs[:5]) + where + ("" if proposal is not None else f"\ntriage worker {prop.get('status', '?')}: {why or 'no summary'}{held}"))
        if nb == 0:  # O(1) an empty proposal: name the way out
            reasons = bc.left_out_reasons(prop, {t["number"] for t in trusted})  # O(q)
            groups: dict = {}  # O(1)
            for t in trusted:  # O(i)
                groups.setdefault(f"not planned (triage: {reasons[t['number']]})" if t["number"] in reasons else "not planned (triage)", []).append(bs.ref(t["number"]))  # O(1)
            print("\n".join(f"{r}: {' '.join(ns)}" for r, ns in groups.items()))  # O(i)
            print("nothing to plan: sl backlog skip <issue> keeps an issue out of every later plan")  # O(1)
        if cuts:
            print("\n".join(cuts))
        return 3
    batches = bc.separate(batches)
    if jira:
        for b in batches:
            b["issues"] = [back[n] for n in b["issues"]]
    planned = {n for b in batches for n in b["issues"]}
    why_out = "not planned (cap)" if len(prop["batches"]) >= cap else "not planned (triage)"  # O(1)
    reasons = bc.left_out_reasons(prop, {t["number"] for t in trusted})  # O(q)
    outside += [_left_out(t["number"], t["title"], f"not planned (triage: {reasons[t['number']]})" if t["number"] in reasons else why_out, carry)
                for t in trusted if t["number"] not in planned]  # O(i)
    outside += [_left_out(i["number"], i.get("title", ""), f"not triaged ({ISSUE_LIMIT} cap)", carry)
                for i in rest if i["number"] not in skipped]  # O(i)
    shown = {}

    def apply(data):
        if add:  # O(1) open batches stay; only a pinned issue now in one of them refuses
            clash = next(((n, b) for b in data["batches"] if b["state"] != "shipped" for n in pin if n in b.get("issues", [])), None)  # O(b * pin)
            if clash:  # O(1)
                raise RuntimeError("backlog changed while " + ("the proposal was checked" if proposal else "triage ran") + f" ({bs.ref(clash[0])} is in {clash[1]['id']} {clash[1]['state']})")
            was = open_batches(data)  # O(b)
            data["titles"] = {**(data.get("titles") or {}), **{str(t["number"]): t["title"] for t in trusted}}  # O(i)
            data["outside"] = outside + [o for o in data["outside"] if not (isinstance(o, dict) and o.get("number") in pin)]  # O(outside * pin)
            done = {n for b in data["batches"] if b["state"] == "shipped" for n in b.get("issues", [])}  # O(b * issues)
            data["outside"] = [o for o in data["outside"] if not isinstance(o, dict) or o.get("number") not in done]  # O(outside)
            new = _renumber(copy.deepcopy(batches), data["batches"])  # O(b)
            data["batches"] += new  # O(b)
            data["round"] = (data["round"] if isinstance(data.get("round"), list) else [b["id"] for b in was]) + [x["id"] for x in new]  # O(b)
            shown["lines"] = bs.status_lines(data) + overlap_lines(new, was)  # O(b)
            return
        live = [b for b in data["batches"] if b["state"] != "shipped" and (not a.reset or b["state"] in ("running", "needs_decision"))]
        if live:  # a batch changed while the triage worker ran: never overwrite it
            raise RuntimeError("backlog changed while " + ("the proposal was checked" if proposal else "triage ran") + " (" + ", ".join(f"{b['id']} {b['state']}" for b in live) + ")")
        data["batches"] = [b for b in data["batches"] if b["state"] == "shipped"]
        data["repo"] = info["nameWithOwner"]
        data["titles"] = {str(t["number"]): t["title"] for t in trusted}
        data["outside"] = outside + ([o for o in data["outside"] if isinstance(o, dict) and isinstance(o.get("number"), (int, str))
                                     and o["number"] not in pin and isinstance(o["number"], str) == pin_jira] if pin else [])  # O(outside * pin)
        done = {n for b in data["batches"] if b["state"] == "shipped" for n in b.get("issues", [])}  # O(b * issues)
        data["outside"] = [o for o in data["outside"] if not isinstance(o, dict) or o.get("number") not in done]  # O(outside)
        data["approved_ship"] = None
        prev = data.get("source")  # O(1)
        if jql is not None:  # O(1)
            data["source"] = {"tracker": "jira", "jql": jql}  # O(1)
        elif keys is not None:  # O(1)
            old = prev.get("jql") if isinstance(prev, dict) and prev.get("tracker") == "jira" else None  # O(1)
            data["source"] = {"tracker": "jira", "jql": old} if isinstance(old, str) and old.strip() else {"tracker": "jira"}  # O(1)
        else:  # O(1)
            data["source"] = {"tracker": "github"}  # O(1)
        data["max_batches"] = cap  # O(1)
        new = _renumber(copy.deepcopy(batches), data["batches"])  # O(b)
        data["batches"] += new  # O(b)
        data["round"] = [x["id"] for x in new]  # O(b)
        shown["lines"] = bs.status_lines(data)
    bs.update(p, apply)
    print("\n".join(shown["lines"] + cuts))
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
    if a.approve_ship:
        if a.source is None:
            print("BLOCKED: --approve-ship needs --source prompt")
            return 2
        res = {}

        def approve(data):
            try:
                res["msg"] = bs.approve_ship(data, a.source, _now())
            except ValueError as e:
                res["err"] = str(e)
        bs.update(p, approve)
        if "err" in res:
            print(f"refused: {res['err']}")
            return 2
        print(res["msg"])
        return 0
    if a.print:
        if not a.batch:
            print(json.dumps({"questions": bs.open_questions(d)}, indent=2))
            return 0
        try:
            b = bs.batch(d, a.batch)
            q = json.loads((Path(b["worktree"]) / ".superlite" / "question.json").read_text())
        except (KeyError, TypeError, OSError, ValueError, RecursionError) as e:
            print(f"BLOCKED: {a.batch} question.json unreadable: {e}")
            return 3
        cuts = bc.fit_question(q)  # O(q)
        errs = bc.check_question(q)
        if errs:
            print(f"BLOCKED: {a.batch} question.json invalid: " + "; ".join(errs[:5]))
            return 3
        print(json.dumps(bc.clean_question(q), indent=2))
        for line in bc.cut_lines(cuts):  # O(q)
            print(line, file=sys.stderr)
        return 0
    if not a.file:
        print("BLOCKED: decide needs --print or --file")
        return 2
    try:
        obj = json.loads(Path(a.file).read_text())
        answers = obj["answers"]
        assert isinstance(answers, dict)
    except (OSError, ValueError, KeyError, AssertionError):
        print(f"BLOCKED: {a.file} is not {{\"answers\": {{question: answer}}}}")
        return 2
    by, err = bc.answer_by(obj, answers)
    if err:
        print(f"BLOCKED: {err}")
        return 2
    res = {}

    def apply(data):
        c = copy.deepcopy(data)
        errs = bs.answer(c, answers, by, _now())
        res["errs"] = errs
        if not errs:
            data.clear()
            data.update(c)
        res["open"] = len(bs.open_questions(data))
    bs.update(p, apply)
    if res["errs"]:
        print("\n".join(res["errs"]))
        return 2
    ruled = sum(1 for v in by.values() if v == "main")
    print(f"recorded {len(answers)} answers" + (f" ({ruled} ruled by main)" if ruled else "") + f", {res['open']} open")
    return 0


NOTE_HELP = "  --note FILE  standing note: FILE's text (at most 2000 characters) goes into every lead brief from now on; an empty file clears it (backlog.py)"  # O(1) #504


def _start(argv: list) -> int:
    """Route start: strip --note FILE, store it, hand the note and the open batches' files to the lead brief, then run it."""
    import backlog_brief  # O(1)
    import backlog_run  # O(1)
    import backlog_state as bs  # O(1)
    rest, f, i = [], None, 0  # O(1)
    while i < len(argv):  # O(args)
        x = argv[i]  # O(1)
        if x == "--note":  # O(1)
            if i + 1 >= len(argv):  # O(1)
                print("BLOCKED: --note needs a FILE")  # O(1)
                return 2  # O(1)
            f, i = argv[i + 1], i + 2  # O(1)
            continue  # O(1)
        if x.startswith("--note="):  # O(1)
            f, i = x[7:], i + 1  # O(1)
            continue  # O(1)
        rest.append(x)  # O(1)
        i += 1  # O(1)
    p = bs.path(_root())  # O(1)
    if f is not None and not os.environ.get("SUPERLITE_FLEET_WORKER"):  # O(1)
        try:  # O(1)
            text = bs.read_note(f)  # O(len)
        except ValueError as e:  # O(1)
            print(f"BLOCKED: {e}")  # O(1)
            return 2  # O(1)
        src, res = str(Path(f).resolve()), {}  # O(1)
        bs.update(p, lambda d: res.update(msg=bs.set_note(d, text, src, _now())))  # O(1)
        print(res["msg"])  # O(1)
        if text:  # O(1)
            for b in bs.load(p)["batches"]:  # O(b)
                if b["state"] in bs.ACTIVE and b.get("lead"):  # O(1)
                    print(f"note: {b['id']} lead {b['lead']} started before this note; sl backlog tell {b['id']} --text \"$(cat {shlex.quote(src)})\" tells it")  # O(1)
    data = bs.load(p)  # O(1)
    nt = data.get("note")  # O(1)
    backlog_brief.STANDING = {"note": nt["text"] if isinstance(nt, dict) and isinstance(nt.get("text"), str) else "", "owned": open_batches(data)}  # O(b)
    try:  # O(1)
        return backlog_run.main(["start"] + rest)  # O(start)
    except SystemExit:  # O(1)
        if any(x in ("-h", "--help") for x in rest):  # O(args)
            print(NOTE_HELP)  # O(1)
        raise  # O(1)


def _main_only(name: str, fn) -> int:
    import backlog_state as bs  # O(1)
    if os.environ.get("SUPERLITE_FLEET_WORKER"):
        print(f"refused: sl backlog {name} runs only in the main session")
        return 2
    res = {}
    try:
        bs.update(bs.path(_root()), lambda data: res.update(msg=fn(bs, data)))
    except (ValueError, KeyError) as e:
        print(f"refused: {e.args[0]}")
        return 2
    print(res["msg"])
    return 0


def cmd_skip(a) -> int:
    seen = {}  # O(1)

    def fn(bs, d):
        hit = next((b for b in d.get("batches", []) if a.issue in b.get("issues", [])), None)  # O(b * issues)
        msg = bs.skip_issue(d, a.issue)  # O(b)
        if hit is not None and hit["state"] == "parked" and hit.get("lead") and not any(b["id"] == hit["id"] for b in d["batches"]):  # O(b)
            seen.update(bid=hit["id"], lead=hit["lead"], repo=d.get("repo", ""))  # O(1)
        return msg  # O(1)
    rc = _main_only("skip", fn)
    if rc == 0 and seen:  # O(1) an emptied parked batch: its lead and ship lock go too
        import fleet  # O(1)
        try:  # O(1)
            fleet.stop(_root() / ".superlite", [seen["lead"]])  # O(w)
            print(f"{seen['bid']} lead {seen['lead']} stopped")  # O(1)
        except (Exception, SystemExit) as e:  # O(1)
            print(f"{seen['bid']} lead {seen['lead']} not stopped: {e}; sl fleet stop {seen['lead']}")  # O(1)
        try:  # O(1)
            import ship_lock  # O(1)
            ship_lock.release(ship_lock.lock_path(seen["repo"]), seen["bid"])  # O(1)
        except (OSError, ValueError):  # O(1)
            pass  # O(1)
    return rc  # O(1)


def cmd_park(a) -> int:
    return _main_only("park", lambda bs, d: bs.park(d, a.batch, a.reason))


def cmd_status(a) -> int:
    import backlog_state as bs  # O(1)
    d = bs.load(bs.path(_root()))  # O(size)
    lines = bs.status_lines(d, all_=getattr(a, "all", False))  # O(b)
    if all(b["state"] == "shipped" for b in d["batches"]):  # O(b) no batch yet, or every batch shipped (#369)
        lines.append("next: sl backlog plan")  # O(1)
    print("\n".join(lines))  # O(lines)
    return 0  # O(1)


def _issue_arg(s: str):
    if s.isdigit():  # O(1)
        return int(s)  # O(1)
    if KEY_RE.fullmatch(s.upper()):  # O(1)
        return s.upper()  # O(1)
    raise argparse.ArgumentTypeError(f"not an issue number or Jira key: {s}")  # O(1)


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "start":
        return _start(argv[1:])
    if argv and argv[0] in ROUTED:
        import backlog_run  # O(1)
        return backlog_run.main(argv)
    if argv and argv[0] == "ship":
        import backlog_ship  # O(1)
        return backlog_ship.main(argv[1:])
    ap = argparse.ArgumentParser(prog="sl backlog")
    sub = ap.add_subparsers(dest="cmd", required=True)
    st = sub.add_parser("status")  # O(1)
    st.add_argument("--all", action="store_true", help="list every batch, also the shipped batches of earlier plan rounds (#406)")  # O(1)
    st.set_defaults(fn=cmd_status)  # O(1)
    pl = sub.add_parser("plan")
    pl.add_argument("--tier", default="sonnet")
    pl.add_argument("--timeout-min", type=int, default=60)
    pl.add_argument("--reset", action="store_true", help="drop the planned and parked batches and plan every open issue again; "
                    "shipped batches stay; refused while a batch is running or needs_decision")  # O(1) #369
    pl.add_argument("--add", action="store_true", help="with --issues: plan those issues as new batches next to the open batches; "
                    "running batches and the ship approval stay")  # O(1) #505
    pl.add_argument("--proposal", metavar="FILE")
    src = pl.add_mutually_exclusive_group()
    src.add_argument("--jql", metavar="QUERY")
    src.add_argument("--github", action="store_true", help="read GitHub issues and remember GitHub as the source")  # O(1)
    pl.add_argument("--max-batches", type=int, metavar="N", help="batches one plan round holds, 1 to 20 (default 7)")  # O(1)
    src.add_argument("--issues", metavar="LIST", help="pin the plan to these issues: GitHub numbers (362,#433) or Jira keys (PIX-1,PIX-2); the first item picks the source")  # O(1)
    pl.set_defaults(fn=cmd_plan)
    de = sub.add_parser("decide")
    de.add_argument("--print", action="store_true")
    de.add_argument("--batch")
    de.add_argument("--file")
    de.add_argument("--approve-ship", action="store_true", help="record a ship approval the user's prompt gave (needs --source prompt)")
    de.add_argument("--source")
    de.set_defaults(fn=cmd_decide)
    sk = sub.add_parser("skip")
    sk.add_argument("issue", type=_issue_arg)
    sk.set_defaults(fn=cmd_skip)
    pk = sub.add_parser("park")
    pk.add_argument("batch")
    pk.add_argument("--reason", required=True)
    pk.set_defaults(fn=cmd_park)
    a = ap.parse_args(argv)
    try:
        return a.fn(a)
    except RuntimeError as e:
        print(f"BLOCKED: {e}")
        return 3


if __name__ == "__main__":
    sys.exit(main())
