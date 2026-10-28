#!/usr/bin/env python3
"""Superlite's own feedback inbox: friction agents hit while using superlite, triaged into issues later.

    feedback.py add TEXT [--kind K] [--plan P]     log one finding (what, where, expected) and carry on
    feedback.py triage [--host H]... [--all] [--issues FILE | --repo OWNER/NAME]
                                                   untriaged entries of this machine and the listed hosts, duplicates
                                                   grouped, ranked by count, each matched against the open issues
    feedback.py mark ID...                         record entries as triaged (filed, merged or dropped)

Files: `$SUPERLITE_HOME/feedback.jsonl` (default `~/.superlite/`), append-only, one per machine;
`feedback-triaged.json` there holds the triaged ids; `feedback-hosts` there lists other machines (one ssh host per
line, `#` comments) whose inbox triage reads over ssh (`$SUPERLITE_SSH` replaces the ssh command). Text is scrubbed
when logged: home paths become `~`, e-mail addresses `<email>`, tokens `<secret>`. Stdlib only.
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

KINDS = ("bug", "slow", "unclear", "repeat", "idea", "other")  # O(1)
MAX_TEXT = 500  # O(1)
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


def group(entries: list) -> list:  # O(i*g*w)
    """Greedy grouping by word overlap (Jaccard >= 0.5 with a group's first entry); largest, then latest, first."""
    groups = []  # O(1)
    for e in sorted(entries, key=lambda e: e.get("date", "")):  # O(i log i) sort, then O(i) iterations
        tk = tokens(e["text"])  # O(w)
        for g in groups:  # O(g) iterations
            union = tk | g["tokens"]  # O(w)
            if union and len(tk & g["tokens"]) / len(union) >= 0.5:  # O(w)
                g["entries"].append(e)  # O(1)
                break  # O(1)
        else:  # O(1)
            groups.append({"tokens": tk, "entries": [e]})  # O(1)
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


def origin_repo(folder):  # O(1) + one git process
    """OWNER/NAME of the GitHub origin of `folder` (a checkout of superlite first, then the working folder)."""
    try:  # O(1)
        url = subprocess.run(["git", "-C", str(folder), "remote", "get-url", "origin"], capture_output=True,  # O(1) + spawn
                             text=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL, timeout=10).stdout
    except (OSError, subprocess.TimeoutExpired):  # O(1)
        return None  # O(1)
    m = re.search(r"github\.com[:/]([^/\s]+/[^/\s]+?)(?:\.git)?\s*$", url)  # O(len url)
    return m.group(1) if m else None  # O(1)


def open_issues(a):  # O(t) + up to two git processes and one gh process (network)
    """Open issues as [{number, title}], or None when they could not be read (matching is then unknown, not new)."""
    if a.issues:  # O(1)
        try:  # O(1)
            data = json.loads(Path(a.issues).read_text(encoding="utf-8"))  # O(t)
        except (OSError, ValueError) as e:  # O(1)
            print(f"feedback: cannot read --issues {a.issues} ({e}), issues not matched", file=sys.stderr)  # O(1)
            return None  # O(1)
        return [i for i in data if isinstance(i, dict)] if isinstance(data, list) else None  # O(t)
    repo = a.repo or origin_repo(PLUGIN_ROOT) or origin_repo(Path.cwd())  # O(1) + spawns
    if not repo:  # O(1)
        print("feedback: no GitHub repository (pass --repo), issues not matched", file=sys.stderr)  # O(1)
        return None  # O(1)
    print(f"feedback: matching against open issues of {repo}", file=sys.stderr)  # O(1)
    cmd = ["gh", "issue", "list", "--repo", repo, "--state", "open", "--json", "number,title", "--limit", "300"]  # O(1)
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


def cmd_add(a) -> int:  # O(i*w) + locked append
    text = scrub(a.text)  # O(w)
    if not text:  # O(1)
        print("error: feedback text is empty", file=sys.stderr)  # O(1)
        return 2  # O(1)
    date = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())  # O(1)
    host = socket.gethostname().split(".")[0]  # O(1)
    eid = hashlib.sha1(f"{host}|{date}|{text}|{time.time_ns()}".encode("utf-8")).hexdigest()[:12]  # O(w)
    entry = {"v": 1, "id": eid, "date": date, "host": host, "kind": a.kind, "text": text, "version": version(),  # O(w)
             "harness": harness(), "project": project(),
             "session": os.environ.get("SUPERLITE_SESSION_ID") or os.environ.get("CLAUDE_CODE_SESSION_ID")
             or os.environ.get("CODEX_THREAD_ID") or "",
             "plan": Path(a.plan).name if a.plan else ""}
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
    groups = group(entries)  # O(i*g*w)
    print(f"feedback triage: {len(entries)} {'' if a.all else 'untriaged '}entries, {len(groups)} groups")  # O(1)
    if not groups:  # O(1)
        return 0  # O(1)
    issues = open_issues(a)  # O(t) + spawn
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
    p.add_argument("text")  # O(1)
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
