#!/usr/bin/env python3
"""Superlite's own feedback inbox: friction agents hit while using superlite, triaged into issues later.

    feedback.py add [TEXT | --file PATH|-] [--kind K] [--plan P]
                                                   log one finding (what, where, expected) and carry on; the text
                                                   comes from TEXT, a file, or stdin (`-`)
    feedback.py triage [--host H]... [--all] [--issues FILE | --repo OWNER/NAME]
                                                   untriaged entries of this machine and the listed hosts, duplicates
                                                   grouped, ranked by count, each matched against the open issues
    feedback.py mark ID...                         record entries as triaged (filed, merged or dropped)

Files: `$SUPERLITE_HOME/feedback.jsonl` (default `~/.superlite/`), append-only, one per machine;
`feedback-triaged.json` there holds the triaged ids; `feedback-hosts` there lists other machines (one ssh host per
line, `#` comments) whose inbox triage reads over ssh (`$SUPERLITE_SSH` replaces the ssh command). Text is scrubbed
when logged: home paths become `~`, e-mail addresses `<email>`, tokens `<secret>`. Stdlib only.

Library: `add_auto(tool, reason, target, version) -> bool` logs one machine-found stop as an entry of kind `auto` (`finish`
calls it per distinct stop, #140). Triage lists an auto group (signature = tool + reason, the target left out) only from
two entries on, and matches entry ids against the open issues and those closed within 30 days (#182).
"""
# Complexity notation:
#   i = inbox entries (all hosts), w = width of one entry, g = groups, t = open issues, h = hosts, x = triaged ids
import argparse  # O(1)
import hashlib  # O(1)
import json  # O(1)
import os  # O(1)
import re  # O(1)
import shlex  # O(1)
import socket  # O(1)
import subprocess  # O(1)
import sys  # O(1)
import time  # O(1)
from pathlib import Path  # O(1)

sys.path.insert(0, str(Path(__file__).resolve().parent))  # O(1)
from incident import append  # locked append with fsync | O(1)

KINDS = ("bug", "slow", "unclear", "repeat", "idea", "other", "auto")  # `auto`: logged by `add_auto` | O(1)
MAX_TEXT = 500  # O(1)
CLOSED_DAYS = 30  # triage matches entry ids against issues closed within this many days | O(1)
AUTO_MIN = 2  # an auto group is listed from this many entries on | O(1)
PLUGIN_ROOT = Path(__file__).resolve().parents[3]  # O(1)
SCRUB = [(re.compile(r"[A-Za-z]:(?:\\{1,2}|/)Users(?:\\{1,2}|/)[^\\/\s]+"), "~"),  # O(1)
         (re.compile(r"/(?:Users|home)/[^/\s]+|/root\b"), "~"),
         (re.compile(r"\b(?:gh[pousr]_|github_pat_|glpat-|sk-|xox[abpr]-)[A-Za-z0-9_-]{10,}"), "<secret>"),
         (re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"), "<secret>"),
         (re.compile(r"\beyJ[A-Za-z0-9_-]{8,}(?:\.[A-Za-z0-9_-]+){0,2}"), "<secret>"),
         (re.compile(r"(?i)\b(bearer|token|password|api[_-]?key)([\s:=]+)\S{8,}"), r"\1\2<secret>"),
         (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "<email>")]
STOP = {"the", "and", "for", "with", "this", "that", "from", "when", "again", "its", "was", "are", "not", "but",  # O(1)
        "into", "then", "than", "after", "before", "has", "had", "have", "does", "did", "should"}
HARNESS_ENV = [("CLAUDECODE", "claude-code"), ("CODEX_THREAD_ID", "codex"), ("CODEX_SANDBOX", "codex"),  # O(1)
               ("GEMINI_CLI", "gemini")]


def home() -> Path:  # O(1)
    return Path(os.environ.get("SUPERLITE_HOME") or Path.home() / ".superlite")  # O(1)


def scrub(text: str) -> str:  # O(w)
    text = " ".join(text.split())  # O(w)
    for rx, repl in SCRUB:  # O(1) iterations (7)
        text = rx.sub(repl, text)  # O(w)
    return text if len(text) <= MAX_TEXT else text[:MAX_TEXT - 1] + "…"  # O(w)


def version() -> str:  # O(size of package.json)
    try:  # O(1)
        return json.loads((PLUGIN_ROOT / "package.json").read_text(encoding="utf-8"))["version"]  # O(size)
    except (OSError, ValueError, KeyError):  # O(1)
        return "unknown"  # O(1)


def harness() -> str:  # O(1)
    if os.environ.get("SUPERLITE_HARNESS"):  # O(1)
        return os.environ["SUPERLITE_HARNESS"]  # O(1)
    return next((name for var, name in HARNESS_ENV if os.environ.get(var)), "unknown")  # O(1)


def project(start=None) -> str:  # O(depth of cwd)
    """The repository's folder name (a linked worktree's main repository), else the working folder's name."""
    cwd = Path(start or os.getcwd()).resolve()  # O(depth)
    for d in (cwd, *cwd.parents):  # O(depth) iterations
        git = d / ".git"  # O(1)
        if git.is_dir():  # O(1)
            return d.name  # O(1)
        if git.is_file():  # O(1)
            m = re.match(r"gitdir:\s*(.+)", git.read_text(encoding="utf-8", errors="replace").strip())  # O(1)
            gd = (d / m.group(1)).resolve() if m else None  # relative with worktree.useRelativePaths | O(depth)
            return gd.parents[2].name if gd and gd.parent.name == "worktrees" else d.name  # O(1)
    return cwd.name  # O(1)


def read_lines(text: str) -> list:  # O(i*w)
    out = []  # O(1)
    for ln in text.splitlines():  # O(i) iterations
        try:  # O(1)
            e = json.loads(ln)  # O(w)
        except ValueError:  # O(1)
            continue  # O(1)
        if isinstance(e, dict) and all(isinstance(e.get(k), str) and e[k] for k in ("id", "text")):  # O(1)
            out.append(e)  # O(1)
    return out  # O(1)


def local_entries() -> list:  # O(i*w)
    f = home() / "feedback.jsonl"  # O(1)
    return read_lines(f.read_text(encoding="utf-8", errors="replace")) if f.is_file() else []  # O(i*w)


def triaged() -> set:  # O(x)
    f = home() / "feedback-triaged.json"  # O(1)
    try:  # O(1)
        return set(json.loads(f.read_text(encoding="utf-8")).get("ids", []))  # O(x)
    except (OSError, ValueError, AttributeError):  # O(1)
        return set()  # O(1)


def hosts(given) -> list:  # O(h)
    if given:  # O(1)
        return list(given)  # O(h)
    f = home() / "feedback-hosts"  # O(1)
    if not f.is_file():  # O(1)
        return []  # O(1)
    lines = (ln.split("#", 1)[0].strip() for ln in f.read_text(encoding="utf-8").splitlines())  # O(h)
    return [ln for ln in lines if ln]  # O(h)


def remote_entries(host: str) -> list:  # O(i*w) + one ssh process (network)
    raw = os.environ.get("SUPERLITE_SSH") or "ssh -o BatchMode=yes -o ConnectTimeout=5"  # O(1)
    ssh = [raw] if os.path.isfile(raw) else shlex.split(raw, posix=os.name != "nt")  # a file path may hold spaces | O(1)
    cmd = ssh + [host, "cat .superlite/feedback.jsonl 2>/dev/null || true"]  # O(1)
    try:  # O(1)
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",  # O(i*w) + spawn
                           stdin=subprocess.DEVNULL, timeout=30)
    except (OSError, ValueError, subprocess.TimeoutExpired) as e:  # O(1)
        print(f"feedback: host {host} unreachable ({e}), skipped", file=sys.stderr)  # O(1)
        return []  # O(1)
    if r.returncode != 0:  # O(1)
        print(f"feedback: host {host} unreachable (exit {r.returncode}), skipped", file=sys.stderr)  # O(1)
        return []  # O(1)
    return read_lines(r.stdout)  # O(i*w)


def tokens(text: str) -> set:  # O(w)
    return {t for t in re.findall(r"[a-z0-9_]+", text.lower()) if len(t) >= 3 and t not in STOP}  # O(w)


def auto_sig(e: dict):  # O(1)
    """(tool, reason) of an auto entry, else None: the target is left out, so one stop on many files is one group."""
    tool, reason = e.get("tool"), e.get("reason")  # O(1)
    return (tool, reason) if e.get("kind") == "auto" and isinstance(tool, str) and tool and isinstance(reason, str) else None  # O(1)


def group(entries: list) -> list:  # O(i*g*w)
    """Greedy grouping by word overlap (Jaccard >= 0.5 with a group's first entry); largest, then latest, first.
    Auto entries group by `auto_sig` instead, and a group of fewer than AUTO_MIN of them is left out (a one-off waits)."""
    groups, by_sig = [], {}  # O(1)
    for e in sorted(entries, key=lambda e: e.get("date", "")):  # O(i log i) sort, then O(i) iterations
        sig = auto_sig(e)  # O(1)
        if sig:  # O(1)
            if sig not in by_sig:  # O(1)
                by_sig[sig] = {"tokens": set(), "entries": [], "auto": True}  # O(1)
                groups.append(by_sig[sig])  # O(1)
            by_sig[sig]["entries"].append(e)  # O(1)
            continue  # O(1)
        tk = tokens(e["text"])  # O(w)
        for g in groups:  # O(g) iterations
            if g.get("auto"):  # an auto group takes only its own signature | O(1)
                continue  # O(1)
            union = tk | g["tokens"]  # O(w)
            if union and len(tk & g["tokens"]) / len(union) >= 0.5:  # O(w)
                g["entries"].append(e)  # O(1)
                break  # O(1)
        else:  # O(1)
            groups.append({"tokens": tk, "entries": [e]})  # O(1)
    groups = [g for g in groups if not g.get("auto") or len(g["entries"]) >= AUTO_MIN]  # O(g)
    return sorted(groups, key=lambda g: (len(g["entries"]), g["entries"][-1].get("date", "")), reverse=True)  # O(g log g)


def match_issue(tk: set, issues: list):  # O(t*w)
    """The open issue whose title shares at least two words and 60 % of the shorter word set, best first."""
    best, score = None, 0.0  # O(1)
    for iss in issues:  # O(t) iterations
        it = tokens(str(iss.get("title", "")))  # O(w)
        common = len(tk & it)  # O(w)
        s = common / min(len(tk), len(it)) if common >= 2 else 0.0  # O(1)
        if s >= 0.6 and s > score:  # O(1)
            best, score = iss, s  # O(1)
    return best  # O(1)


def filed(entries: list, issues: list) -> dict:  # O(i*t*w)
    """{entry id: issue number} for every entry whose id appears in an issue's body or a comment's body."""
    out = {}  # O(1)
    for iss in issues:  # O(t) iterations
        cs = iss.get("comments") if isinstance(iss.get("comments"), list) else []  # O(1)
        blob = "\n".join(str(x) for x in [iss.get("body")] + [c.get("body") for c in cs if isinstance(c, dict)] if x)  # O(w)
        toks = set(re.findall(r"[0-9A-Za-z]+", blob))  # O(w) whole alphanumeric tokens: no match inside a longer string
        for e in entries:  # O(i) iterations
            if e["id"] not in out and e["id"] in toks:  # O(1)
                out[e["id"]] = iss.get("number")  # O(1)
    return out  # O(1)


def origin_repo(folder):  # O(1) + one git process
    """OWNER/NAME of the GitHub origin of `folder` (a checkout of superlite first, then the working folder)."""
    try:  # O(1)
        url = subprocess.run(["git", "-C", str(folder), "remote", "get-url", "origin"], capture_output=True,  # O(1) + spawn
                             text=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL, timeout=10).stdout
    except (OSError, subprocess.TimeoutExpired):  # O(1)
        return None  # O(1)
    m = re.search(r"github\.com[:/]([^/\s]+/[^/\s]+?)(?:\.git)?\s*$", url)  # O(len url)
    return m.group(1) if m else None  # O(1)


def _repo(a):  # O(1) + up to two git processes, once per run
    """OWNER/NAME for gh: --repo, else the origin of superlite's checkout, else of the working folder (kept on `a`)."""
    if not a.repo:  # O(1)
        a.repo = origin_repo(PLUGIN_ROOT) or origin_repo(Path.cwd())  # O(1) + spawns
    return a.repo  # O(1)


def open_issues(a):  # O(t) + up to two git processes and one gh process (network)
    """Open issues as [{number, title}], or None when they could not be read (matching is then unknown, not new)."""
    if a.issues:  # O(1)
        try:  # O(1)
            data = json.loads(Path(a.issues).read_text(encoding="utf-8"))  # O(t)
        except (OSError, ValueError) as e:  # O(1)
            print(f"feedback: cannot read --issues {a.issues} ({e}), issues not matched", file=sys.stderr)  # O(1)
            return None  # O(1)
        return [i for i in data if isinstance(i, dict)] if isinstance(data, list) else None  # O(t)
    repo = _repo(a)  # O(1) + spawns
    if not repo:  # O(1)
        print("feedback: no GitHub repository (pass --repo), issues not matched", file=sys.stderr)  # O(1)
        return None  # O(1)
    print(f"feedback: matching against open issues of {repo}", file=sys.stderr)  # O(1)
    cmd = ["gh", "issue", "list", "--repo", repo, "--state", "open", "--json", "number,title,body,comments", "--limit", "300"]  # O(1)
    try:  # O(1)
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",  # O(t) + spawn
                           stdin=subprocess.DEVNULL, timeout=60)
        if r.returncode == 0:  # O(1)
            return json.loads(r.stdout)  # O(t)
        err = (r.stderr.strip().splitlines() or [f"exit {r.returncode}"])[-1]  # O(len stderr)
    except (OSError, subprocess.TimeoutExpired, ValueError) as e:  # O(1)
        err = str(e)  # O(1)
    print(f"feedback: gh issue list failed for {repo} ({err}), issues not matched", file=sys.stderr)  # O(1)
    return None  # O(1)


def closed_issues(a) -> list:  # O(t) + one gh process (network)
    """Issues closed within CLOSED_DAYS days as [{number, title, body, comments}], so an entry filed in a fixed issue is still
    found (#182). A --issues file is the whole list already; a failing gh gives [] with one stderr line (open ones still match)."""
    repo = None if a.issues else _repo(a)  # O(1)
    if not repo:  # O(1)
        return []  # O(1)
    since = time.strftime("%Y-%m-%d", time.gmtime(time.time() - CLOSED_DAYS * 86400))  # O(1)
    cmd = ["gh", "issue", "list", "--repo", repo, "--state", "closed", "--search", f"closed:>={since}",  # O(1)
           "--json", "number,title,body,comments", "--limit", "300"]
    try:  # O(1)
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",  # O(t) + spawn
                           stdin=subprocess.DEVNULL, timeout=60)
        if r.returncode == 0:  # O(1)
            data = json.loads(r.stdout)  # O(t)
            return [i for i in data if isinstance(i, dict)] if isinstance(data, list) else []  # O(t)
        err = (r.stderr.strip().splitlines() or [f"exit {r.returncode}"])[-1]  # O(len stderr)
    except (OSError, subprocess.TimeoutExpired, ValueError) as e:  # O(1)
        err = str(e)  # O(1)
    print(f"feedback: gh issue list (closed) failed for {repo} ({err}), closed issues not matched", file=sys.stderr)  # O(1)
    return []  # O(1)


def new_entry(kind: str, text: str, plan: str = "", ver: str = "", **extra) -> dict:  # O(w)
    """One inbox entry for already scrubbed text: id, date, host and the run's context; `extra` adds fields."""
    date = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())  # O(1)
    host = socket.gethostname().split(".")[0]  # O(1)
    eid = hashlib.sha1(f"{host}|{date}|{text}|{time.time_ns()}".encode("utf-8")).hexdigest()[:12]  # O(w)
    return {"v": 1, "id": eid, "date": date, "host": host, "kind": kind, "text": text, "version": ver or version(),  # O(w)
            "harness": harness(), "project": project(),
            "session": os.environ.get("SUPERLITE_SESSION_ID") or os.environ.get("CLAUDE_CODE_SESSION_ID")
            or os.environ.get("CODEX_THREAD_ID") or "",
            "plan": Path(plan).name if plan else "", **extra}


def add_auto(tool: str, reason: str, target: str, version: str) -> bool:  # O(w) + locked append
    """Log one machine-found stop as an entry of kind `auto`, scrubbed like `add` (home paths, e-mail addresses, tokens).
    Called again with the same tool and reason it writes a second entry: triage groups them. False when the tool is empty
    or the inbox cannot be written; never raises."""
    tool, reason, target = scrub(str(tool)), scrub(str(reason)), scrub(str(target))  # O(w)
    if not tool:  # O(1)
        return False  # O(1)
    text = scrub(f"{tool} {reason}" + (f": {target}" if target else ""))  # O(w)
    entry = new_entry("auto", text, ver=scrub(str(version)), tool=tool, reason=reason, target=target)  # O(w)
    try:  # O(1)
        append(home() / "feedback.jsonl", [entry])  # O(w) + fsync
    except OSError:  # O(1)
        return False  # O(1)
    return True  # O(1)


def cmd_add(a) -> int:  # O(i*w) + locked append
    if a.file is not None and a.text is not None:  # O(1)
        print("error: give the text or --file, not both", file=sys.stderr)  # O(1)
        return 2  # O(1)
    if a.file is not None:  # O(1)
        try:  # O(1)
            raw = sys.stdin.read() if a.file == "-" else Path(a.file).read_text(encoding="utf-8")  # O(w)
        except (OSError, ValueError) as e:  # O(1)
            print(f"error: cannot read {a.file} ({e})", file=sys.stderr)  # O(1)
            return 2  # O(1)
    else:  # O(1)
        raw = a.text or ""  # O(w)
    text = scrub(raw)  # O(w)
    if not text:  # O(1)
        print("error: feedback text is empty", file=sys.stderr)  # O(1)
        return 2  # O(1)
    entry = new_entry(a.kind, text, a.plan or "")  # O(w)
    eid = entry["id"]  # O(1)
    append(home() / "feedback.jsonl", [entry])  # O(w) + fsync
    done = triaged()  # O(x)
    left = sum(1 for e in local_entries() if e["id"] not in done)  # O(i*w)
    print(f"feedback logged: {eid} ({left} untriaged on this machine)")  # O(1)
    return 0  # O(1)


def _vals(entries, key) -> str:  # O(i)
    return ", ".join(sorted({str(e.get(key) or "?") for e in entries})) or "?"  # O(i log i)


def cmd_triage(a) -> int:  # O(i*g*w + g*t*w) + h ssh processes + one gh process
    seen, entries = set(), []  # O(1)
    for e in local_entries() + [e for h in hosts(a.host) for e in remote_entries(h)]:  # O(i) iterations
        if e["id"] not in seen:  # O(1)
            seen.add(e["id"])  # O(1)
            entries.append(e)  # O(1)
    done = set() if a.all else triaged()  # O(x)
    entries = [e for e in entries if e["id"] not in done]  # O(i)
    total = len(entries)  # O(1)
    if not entries:  # O(1)
        print(f"feedback triage: 0 {'' if a.all else 'untriaged '}entries, 0 groups")  # O(1)
        return 0  # O(1)
    issues = open_issues(a)  # O(t) + spawn
    known = (issues or []) + (closed_issues(a) if issues is not None else [])  # open and recently closed: an id in either is filed | O(t) + spawn
    by_id = filed(entries, known) if known else {}  # O(i*t*w)
    entries = [e for e in entries if e["id"] not in by_id]  # O(i)
    groups = group(entries)  # O(i*g*w)
    print(f"feedback triage: {total} {'' if a.all else 'untriaged '}entries, {len(groups) + len({by_id[k] for k in by_id})} groups")  # O(1)
    if by_id:  # O(1)
        for num in sorted(set(by_id.values())):  # O(t) iterations
            ids = [k for k in by_id if by_id[k] == num]  # O(i)
            print(f"\n## filed: #{num}\n- ids: " + " ".join(ids))  # O(i)
        print("\nfiled already: `sl feedback mark " + " ".join(by_id) + "`")  # O(i)
    for n, g in enumerate(groups, 1):  # O(g) iterations
        es = g["entries"]  # O(1)
        texts = list(dict.fromkeys(scrub(e["text"]) for e in es))  # O(i*w) scrub again: older or remote entries
        iss = match_issue(set().union(*(tokens(t) for t in texts)), issues or [])  # O(t*w)
        print(f"\n## {n}. ×{len(es)} {_vals(es, 'kind')}: {texts[0]}")  # O(w)
        print(f"- seen: {es[0].get('date', '?')[:10]}..{es[-1].get('date', '?')[:10]} · versions {_vals(es, 'version')}"  # O(i)
              f" · harness {_vals(es, 'harness')} · projects {_vals(es, 'project')} · hosts {_vals(es, 'host')}")
        if issues is None:  # O(1)
            print("- issue: unmatched (open issues not read): check before filing")  # O(1)
        else:  # O(1)
            print(f"- issue: maybe #{iss.get('number')} {iss.get('title', '')}" if iss else "- issue: none (new)")  # O(1)
        if len(texts) > 1:  # O(1)
            print("- also: " + "; ".join(f'"{t}"' for t in texts[1:3]))  # O(w)
        print("- ids: " + " ".join(e["id"] for e in es))  # O(i)
    print("\nnext: draft one issue per new group (a comment on a matched one), ask Max to approve the batch, "  # O(1)
          "file it with gh, then `sl feedback mark <ids>` for every group filed, merged or dropped")
    return 0  # O(1)


def cmd_mark(a) -> int:  # O(x + n)
    f = home() / "feedback-triaged.json"  # O(1)
    ids = sorted(triaged() | set(a.ids))  # O((x + n) log(x + n))
    f.parent.mkdir(parents=True, exist_ok=True)  # O(1)
    tmp = f.with_suffix(".tmp")  # O(1)
    tmp.write_text(json.dumps({"ids": ids}) + "\n", encoding="utf-8")  # O(x + n)
    tmp.replace(f)  # O(1) atomic replace
    print(f"feedback marked: {len(a.ids)} ({len(ids)} triaged in total)")  # O(1)
    return 0  # O(1)


def main(argv=None) -> int:  # O(1) + the subcommand
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])  # O(1)
    sub = ap.add_subparsers(dest="cmd", required=True)  # O(1)
    p = sub.add_parser("add", help="log one finding")  # O(1)
    p.add_argument("text", nargs="?")  # O(1)
    p.add_argument("--file", help="read the text from PATH, or from stdin with -")  # O(1)
    p.add_argument("--kind", choices=KINDS, default="other")  # O(1)
    p.add_argument("--plan")  # O(1)
    p = sub.add_parser("triage", help="group and rank untriaged entries")  # O(1)
    p.add_argument("--host", action="append", help="ssh host whose inbox to read (default: feedback-hosts)")  # O(1)
    p.add_argument("--all", action="store_true", help="include triaged entries")  # O(1)
    p.add_argument("--issues", help="JSON file of open issues (number, title) instead of gh")  # O(1)
    p.add_argument("--repo", help="OWNER/NAME for gh (default: origin of superlite's checkout, else of the working folder)")  # O(1)
    p = sub.add_parser("mark", help="record entries as triaged")  # O(1)
    p.add_argument("ids", nargs="+")  # O(1)
    a = ap.parse_args(argv)  # O(1)
    sys.stdout.reconfigure(encoding="utf-8")  # O(1)
    return {"add": cmd_add, "triage": cmd_triage, "mark": cmd_mark}[a.cmd](a)  # O(1) + the subcommand


if __name__ == "__main__":  # O(1)
    sys.exit(main())  # O(1)
