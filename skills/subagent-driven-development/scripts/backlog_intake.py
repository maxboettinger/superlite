#!/usr/bin/env python3
"""Pure intake helpers for the backlog plan step: shipped issues, files an issue names, blocked-reason check (the `Pinned:` brief line is backlog_brief.pinned_line, #622)."""
import re
from collections import defaultdict

import backlog_checks as bc

TRAIL_RE = re.compile(r"\s*\(#(\d+)\)\s*$")
GH_RE = re.compile(r"(?<![\w#&])#([1-9][0-9]*)(?![\w])")
JIRA_RE = re.compile(r"(?<![A-Za-z0-9_-])([A-Z][A-Z0-9_]*-[1-9][0-9]*)(?![A-Za-z0-9_-])")
FILE_RE = re.compile(r"[A-Za-z0-9_.][A-Za-z0-9_./-]*")
BLOCK_RE = re.compile(r"\b(needs?|needed|blocked|blocks|waits?|waiting|after|depends?|dependency|requires?|required|first|until|prerequisite|missing)\b", re.I)
VER_RE = re.compile(r"(?<![\w.])(\d+\.\d+(?:\.\d+)?)(?![\w])")
COMMIT_RE = re.compile(r"\b[0-9a-fA-F]{7,40}\b")
REF_RE = re.compile(r"#\d+|\b[A-Z][A-Z0-9_]*-[1-9][0-9]*\b|\bB\d+\b")
CTRL_RE = re.compile(r"[\x00-\x1f\x7f]")
COMMENTS_MAX = 3
COMMENT_LIMIT = 2000
CHUNK = 50
TRUSTED = ("OWNER", "MEMBER", "COLLABORATOR")
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def _clean(s: object) -> str:
    return " ".join(CTRL_RE.sub(" ", str(s)).split())  # O(len)


def _ref(n: object) -> str:
    return f"#{n}" if isinstance(n, int) else _clean(n)  # O(1)


def _plain(n: object) -> str:
    return str(n) if isinstance(n, int) else _clean(n)  # O(1)


def merged_refs(lines: list[str], jira: bool) -> dict:
    """{issue: "PR #N" | "commit <sha>"} from `<sha>\\t<subject>` lines; the first subject naming an issue wins."""
    out: dict = {}
    for line in lines:  # O(lines * len)
        sha, tab, subj = line.partition("\t")  # O(len)
        if not tab or subj.startswith("Merge pull request #"):  # O(1)
            continue
        m = TRAIL_RE.search(subj)  # O(len)
        what = f"PR #{m.group(1)}" if m else f"commit {sha.strip()}"  # O(1)
        body = subj[:m.start()] if m else subj  # O(1)
        refs: list = [int(x) for x in GH_RE.findall(body)]  # O(len)
        if jira:
            refs += JIRA_RE.findall(body)  # O(len)
        for r in refs:  # O(refs)
            out.setdefault(r, what)  # O(1)
    return out


def split_shipped(trusted: list[dict], batches: list[dict], merged: dict, pin: list) -> tuple[list[dict], list[dict], list[str]]:
    """(kept, dropped, lines): trusted issues that are not shipped, the merged-subject ones dropped, and one line per decision."""
    shipped: dict = {}
    for b in batches:  # O(batches * issues)
        if b.get("state") == "shipped":
            for n in b.get("issues") or []:  # O(issues)
                shipped.setdefault(n, b)  # O(1)
    kept, dropped, lines = [], [], []
    for it in trusted:  # O(trusted)
        n = it["number"]
        r, p = _ref(n), _plain(n)  # O(1)
        if it.get("reopened") and (n in shipped or n in merged):  # O(1)
            kept.append(it)
            if n in shipped:  # O(1)
                b = shipped[n]
                pr = f" (PR #{_clean(b['pr'])})" if b.get("pr") else ""  # O(1)
                lines.append(f"reopened: {r} was shipped in {_clean(b.get('id'))}{pr}: planned again")  # O(1)
            else:
                lines.append(f"reopened: {r} named by merged {merged[n]}: planned again")  # O(1)
        elif it.get("reopened"):  # O(1)
            kept.append(it)
        elif n in shipped:  # O(1)
            b = shipped[n]
            pr = f" (PR #{_clean(b['pr'])})" if b.get("pr") else ""  # O(1)
            lines.append(f"already shipped: {r} in {_clean(b.get('id'))}{pr}: not planned again")  # O(1)
        elif n in merged and n in pin:  # O(pin)
            kept.append(it)
            lines.append(f"already shipped?: {r} named by merged {merged[n]}: planned anyway (pinned); sl backlog skip {p} drops it")  # O(1)
        elif n in merged:  # O(1)
            dropped.append({"number": n, "title": _clean(it.get("title", "")), "reason": f"not planned (shipped: {merged[n]})"})  # O(1)
            lines.append(f"already shipped: {r} named by merged {merged[n]}: not planned; close it, or sl backlog skip {p} keeps it out")  # O(1)
        else:
            kept.append(it)
    return kept, dropped, lines


def _cut(body: object) -> str:
    b = str(body or "")  # O(len)
    return b[:COMMENT_LIMIT] + "\n[truncated]" if len(b) > COMMENT_LIMIT else b  # O(len)


def _gh_chunk(owner: str, name: str, nums: list, public: bool) -> dict:
    import backlog
    aliases = "".join(f"i{n}:issue(number:{n}){{stateReason comments(last:10){{nodes{{authorAssociation author{{login}} body}}}}}}" for n in nums)  # O(chunk)
    q = f'query{{repository(owner:"{owner}",name:"{name}"){{{aliases}}}}}'  # O(chunk)
    res = backlog._gh(["api", "graphql", "-f", "query=" + q])
    repo = ((res if isinstance(res, dict) else {}).get("data") or {}).get("repository") or {}  # O(1)
    out = {}
    for n in nums:  # O(chunk * comments)
        node = repo.get(f"i{n}") or {}  # O(1)
        nodes = ((node.get("comments") or {}).get("nodes")) or []  # O(1)
        keep = [c for c in nodes if c and (not public or c.get("authorAssociation") in TRUSTED)]  # O(nodes)
        cs = [{"author": (c.get("author") or {}).get("login") or "ghost", "body": _cut(c.get("body"))} for c in keep[-COMMENTS_MAX:]]  # O(1)
        out[n] = (cs, node.get("stateReason") == "REOPENED")  # O(1)
    return out


def with_comments(trusted: list[dict], repo: str, public: bool, jira: bool = False) -> tuple[list[dict], list[str]]:
    """(items, lines): each trusted issue plus its latest comments (oldest first) and reopened=True when GitHub reports a reopen; lines name every read that failed."""
    if not trusted:  # O(1)
        return [], []
    import backlog
    lines: list[str] = []
    if jira:
        out = []
        for it in trusted:  # O(trusted)
            key = it["number"]
            try:
                res = backlog._acli(["jira", "workitem", "comment", "list", "--key", str(key), "--json", "--limit", str(COMMENTS_MAX), "--order", "-created"])
                cs = []
                for c in reversed((res if isinstance(res, dict) else {}).get("comments") or []):  # O(comments)
                    body = c.get("body")
                    body = backlog.adf_text(body) if isinstance(body, dict) else body  # O(len)
                    a = c.get("author")
                    a = (a.get("displayName") or a.get("name")) if isinstance(a, dict) else a  # O(1)
                    cs.append({"author": _clean(a or "ghost"), "body": _cut(body)})  # O(len)
                out.append({**it, "comments": cs[-COMMENTS_MAX:]})  # O(1)
            except RuntimeError as e:
                out.append({**it, "comments": []})
                lines.append(f"comments: not read for {_clean(key)} ({_clean(e)[:120]})")  # O(1)
        return out, lines
    if not REPO_RE.match(repo or ""):  # O(len)
        return [{**it, "comments": []} for it in trusted], [f"comments: not read (bad repo name {_clean(repo)}); triage sees the issue bodies only"]  # O(trusted)
    owner, name = repo.split("/", 1)  # O(1)
    got: dict = {}
    for i in range(0, len(trusted), CHUNK):  # O(trusted)
        part = trusted[i:i + CHUNK]  # O(chunk)
        try:
            got.update(_gh_chunk(owner, name, [it["number"] for it in part], public))
        except RuntimeError as e:
            lines.append(f"comments: not read ({_clean(e)[:120]}); triage sees the issue bodies only")  # O(1)
    out = []
    for it in trusted:  # O(trusted)
        cs, reopened = got.get(it["number"], ([], False))  # O(1)
        out.append({**it, "comments": cs, **({"reopened": True} if reopened else {})})  # O(1)
    return out, lines


def named_files(body: str, tracked: list[str]) -> list[str]:
    """Tracked files an issue body names by path or unique basename; sorted, unique."""
    by_base: dict = defaultdict(list)
    for t in tracked:  # O(tracked)
        by_base[t.rsplit("/", 1)[-1]].append(t)
    tset, out = set(tracked), set()
    for tok in FILE_RE.findall(body):  # O(len)
        if tok.startswith("./"):
            tok = tok[2:]
        tok = tok.rstrip(".,/")  # O(len)
        if not tok or ("." not in tok and "/" not in tok):  # O(1)
            continue
        if tok in tset:  # O(1)
            out.add(tok)
            continue
        cands = [t for t in by_base.get(tok.rsplit("/", 1)[-1], []) if t.endswith("/" + tok)]  # O(cands)
        if len(cands) == 1:
            out.add(cands[0])
    return sorted(out)


def _vt(v: str) -> tuple:
    m = re.match(r"\d+(?:\.\d+){0,2}", str(v).lstrip("vV"))  # O(1)
    p = [int(x) for x in m.group(0).split(".")] if m else []  # O(1)
    return tuple(p + [0] * (3 - len(p)))  # O(1)


def blocked_lines(prop: dict, pin: list, version: str | None) -> list[str]:
    """One check line per pinned issue left out as blocked without naming a missing thing, or naming a version already reached."""
    reasons = bc.left_out_reasons(prop, set(pin))
    version = _clean(version) if version else None  # O(len)
    if version and not re.match(r"[vV]?\d", version):  # O(1)
        version = None
    out = []
    for n in pin:  # O(pin * len)
        r = reasons.get(n)
        if r is None or not BLOCK_RE.search(r):  # O(len)
            continue
        vers = VER_RE.findall(r)  # O(len)
        other = [c for c in COMMIT_RE.findall(r) if re.search(r"\d", c) and re.search(r"[a-fA-F]", c)] + REF_RE.findall(r)  # O(len)
        ref, p = _ref(n), _plain(n)
        tail = f"sl backlog plan --issues {p} --add plans it again"
        if not vers and not other:  # O(1)
            out.append(f'check: {ref} left out as "{r}" without naming the missing commit or version; {tail}')  # O(1)
        elif version and any(_vt(v) <= _vt(version) for v in vers):  # O(vers)
            out.append(f'check: {ref} left out as "{r}" but the repository is at {version}; {tail}')  # O(1)
    return out
