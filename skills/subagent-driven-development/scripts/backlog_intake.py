#!/usr/bin/env python3
"""Pure intake helpers for the backlog plan step: shipped issues, files an issue names, the pinned brief rule, blocked-reason check."""
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


def _clean(s: object) -> str:
    return " ".join(CTRL_RE.sub(" ", str(s)).split())  # O(len)


def _ref(n: object) -> str:
    return f"#{n}" if isinstance(n, int) else _clean(n)  # O(1)


def _plain(n: object) -> str:
    return str(n) if isinstance(n, int) else _clean(n)  # O(1)


def merged_refs(lines: list, jira: bool) -> dict:
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


def split_shipped(trusted: list, batches: list, merged: dict, pin: list) -> tuple:
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
        if n in shipped:  # O(1)
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


def named_files(body: str, tracked: list) -> list:
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
    p = [int(x) for x in v.split(".")]  # O(1)
    return tuple(p + [0] * (3 - len(p)))  # O(1)


def blocked_lines(prop: dict, pin: list, version: object) -> list:
    """One check line per pinned issue left out as blocked without naming a missing thing, or naming a version already reached."""
    reasons = bc.left_out_reasons(prop, set(pin))
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


def pinned_rule(head: object, version: object) -> str:
    at = ", ".join(x for x in (f"at {head}" if head else "", f"version {version}" if version else "") if x)  # O(1)
    where = f" ({at})" if at else ""  # O(1)
    return ("Pinned: main chose these issues with --issues; plan each one. Leave a pinned issue out only as an umbrella or tracking issue, "
            "or as blocked with the missing commit, version or issue named in its left_out reason (e.g. \"needs 1.6.0 first\"); "
            f"work already on the default branch{where} is not missing.")  # O(1)


def insert_before_rules(brief: str, lines: list) -> str:
    """Put lines before the first `Rules: ` line, else at the end before the final newline."""
    nl = brief.endswith("\n")
    parts = brief.split("\n")[:-1] if nl else brief.split("\n")  # O(len)
    i = next((k for k, x in enumerate(parts) if x.startswith("Rules: ")), len(parts))  # O(len)
    parts[i:i] = list(lines)
    return "\n".join(parts) + ("\n" if nl else "")  # O(len)
