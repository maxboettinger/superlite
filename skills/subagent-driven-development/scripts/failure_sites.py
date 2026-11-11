#!/usr/bin/env python3
"""Where did an xcodebuild test fail: (file, line, context) sites from the run's output.

    failure_sites.failures(text, root, paths, names) -> [(file, line, context)]

Reads Swift Testing issue lines (`✘ Test NAME recorded an issue at FILE:L:C: MSG`), XCTest error lines
(`FILE:L: error: -[Module.Class method] : MSG`), parallel-testing lines (`Test case 'Suite/name()' failed on ...`)
and the runner's own failed `names` (a crash has none of the others). `file` is relative to `root`, found by
basename (the `paths` the run was limited to win a tie); a site that no file explains is `("-", 0, context)`.
Known issues (`━`) are not failures. Stdlib only; the Swift type scan is testcmd's.
"""
# Complexity notation:
#   o = output lines, f = Swift files under root (bounded), n = bytes read
from __future__ import annotations

import os  # O(1)
import re  # O(1)
import sys  # O(1)
from pathlib import Path  # O(1)

sys.path.insert(0, str(Path(__file__).resolve().parent))  # O(path list)

import testcmd  # noqa: E402  # O(1) module load

ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")  # O(1)
ISSUE = re.compile(r"^✘ Test (.+?) recorded an issue(?: with .+?)? at (.+?):(\d+):\d+: (.*)$")  # O(1)
XCT = re.compile(r"^(.+?):(\d+): error: -\[(\S+) (\S+)\] : (.*)$")  # O(1)
PARALLEL = re.compile(r"^Test case '(.+)' failed on ")  # O(1)
XCODE_LINE = re.compile(r"^(Test Suite '|Test Case '|Test case '|◇ Test|✔ Test|✘ Test|Failing tests:|\*\* TEST)")  # O(1)
CLASS_METHOD = re.compile(r"^[A-Za-z_]\w*\.[A-Za-z_]\w*(\(\))?$")  # O(1)
MAX_FILES = 20000  # O(1)


def _clean(text: str) -> list[str]:  # lines without ANSI colours and zero-width spaces | O(o)
    return [ANSI.sub("", ln).replace("​", "").strip() for ln in text.splitlines()]  # O(o)


def _swift_files(root: str, paths: list[str]) -> list[str]:  # root-relative .swift files, the run's own paths first | O(f)
    out: list[str] = [p.replace("\\", "/") for p in paths if p.endswith(".swift")]  # O(p)
    seen = set(out)  # O(p)
    base = Path(root)  # O(1)
    if not base.is_dir():  # O(1)
        return out  # O(1)
    for dirpath, dirs, files in os.walk(base):  # O(f)
        dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d not in testcmd.NO_SCAN)  # O(d)
        for f in sorted(files):  # O(files)
            if f.endswith(".swift"):  # O(1)
                rel = (Path(dirpath) / f).relative_to(base).as_posix()  # O(len)
                if rel not in seen and len(seen) < MAX_FILES:  # O(1)
                    seen.add(rel)  # O(1)
                    out.append(rel)  # O(1)
    return out  # O(1)


class _Tree:  # the Swift files under root, each read and scanned once | O(f)
    def __init__(self, root: str, paths: list[str]):  # O(f)
        self.root = Path(root)  # O(1)
        self.paths = {p.replace("\\", "/") for p in paths}  # O(p)
        self._files: list[str] | None = None  # walked on the first lookup | O(1)
        self._cache: dict[str, tuple[list[str], list[tuple[str, int, int]]]] = {}  # O(1)

    @property
    def files(self) -> list[str]:  # the walk happens only when a site needs a file | O(f)
        if self._files is None:  # O(1)
            self._files = _swift_files(str(self.root), sorted(self.paths))  # O(f)
        return self._files  # O(1)

    def read(self, rel: str):  # (lines, swift_types) of one file, ([], []) when unreadable | O(n)
        if rel not in self._cache:  # O(1)
            try:  # O(1)
                text = (self.root / rel).read_text(encoding="utf-8", errors="replace")  # O(n)
            except OSError:  # O(1)
                text = ""  # O(1)
            self._cache[rel] = (text.splitlines(), testcmd.swift_types(text))  # O(n)
        return self._cache[rel]  # O(1)

    def enclosing(self, rel: str, line: int) -> list[str]:  # names of the types around a line, outermost first | O(t)
        return [n for n, a, b in self.read(rel)[1] if a <= line <= b]  # O(t)

    def pick(self, written: str, line: int, base: str, suite: str) -> str | None:  # the file a path as printed means | O(f)
        want = written.replace("\\", "/").split("/")  # O(len)
        best, best_key = None, None  # O(1)
        for rel in self.files:  # O(f)
            got = rel.split("/")  # O(len)
            if got[-1] != want[-1]:  # O(1)
                continue  # O(1)
            tail = 0  # O(1)
            while tail < min(len(got), len(want)) and got[-1 - tail] == want[-1 - tail]:  # O(len)
                tail += 1  # O(1)
            lines, types = self.read(rel)  # O(n)
            has = any(re.search(rf"\bfunc\s+{re.escape(base)}\s*\(", ln) for ln in lines) if base else False  # O(n)
            has_suite = any(n == suite for n, _, _ in types) if suite else False  # O(t)
            key = (rel in self.paths, has_suite, has, tail)  # O(1)
            if best_key is None or key > best_key:  # O(1)
                best, best_key = rel, key  # O(1)
        return best  # O(1)

    def find_func(self, base: str, suite: str):  # (file, line, suite path) of `func base(` inside suite, None when absent | O(n*f)
        pat = re.compile(rf"\bfunc\s+{re.escape(base)}\s*\(")  # O(1)
        for rel in sorted(self.files, key=lambda r: r not in self.paths):  # the run's own files first | O(f log f)
            lines, _ = self.read(rel)  # O(n)
            for i, ln in enumerate(lines):  # O(n)
                if pat.search(ln):  # O(1)
                    around = self.enclosing(rel, i + 1)  # O(t)
                    if not suite or (around and around[-1] == suite):  # O(1)
                        return rel, i + 1, around  # O(1)
        return None  # O(1)


def _base(name: str) -> str:  # the comparable form of a test name: no (), no ' with N test cases', no ' (crashed)', no Class. | O(len)
    n = re.sub(r" \(crashed\)$", "", name.strip())  # O(len)
    n = re.sub(r" with \d+ test cases?$", "", n)  # O(len)
    if not n.startswith('"') and "." in n.split("(")[0]:  # XCTest Class.method | O(len)
        n = n.split("(")[0].rsplit(".", 1)[-1] + n[len(n.split("(")[0]):]  # O(len)
    return n[:-2] if n.endswith("()") else n  # O(1)


def _failing_block(lines: list[str]) -> dict[str, str]:  # name() -> suite from the `Failing tests:` block | O(o)
    out: dict[str, str] = {}  # O(1)
    on = False  # O(1)
    for ln in lines:  # O(o)
        if ln == "Failing tests:":  # O(1)
            on = True  # O(1)
        elif on and ln and re.match(r"^[\w$.]+\(.*\)$|^[\w$.]+$", ln):  # O(1)
            suite, _, fn = ln.rpartition(".")  # O(len)
            out.setdefault(_base(fn), suite.rsplit(".", 1)[-1])  # O(1)
        elif on:  # O(1)
            on = False  # O(1)
    return out  # O(1)


def failures(text: str, root: str, paths: list[str], names: list[str]) -> list[tuple[str, int, str]]:  # (file, line, context) per failed test | O(o + f*n)
    lines = _clean(text)  # O(o)
    tree = _Tree(root, list(paths))  # O(f)
    out: list[tuple[str, int, str]] = []  # O(1)
    seen: list[tuple[str, str]] = []  # (suite, name) of tests that already have a site; suite "" = unknown | O(1)

    def dup(suite: str, base: str) -> bool:  # an unknown suite matches any suite | O(s)
        return any(b == base and (not s or not suite or s == suite) for s, b in seen)  # O(s)

    def add(site: tuple[str, int, str]) -> None:  # keeps first-seen order, no duplicates | O(s)
        if site not in out:  # O(s)
            out.append(site)  # O(1)

    for ln in lines:  # O(o)
        m = ISSUE.match(ln)  # O(1)
        if m:  # Swift Testing issue line | O(1)
            name, written, num, msg = m.group(1), m.group(2), int(m.group(3)), m.group(4)  # O(1)
            rel = tree.pick(written, num, _base(name), "")  # O(f)
            path = tree.enclosing(rel, num) if rel else []  # O(t)
            if dup(path[-1] if path else "", _base(name)):  # first issue per test | O(s)
                continue  # O(1)
            add((rel or "-", num if rel else 0, "/".join(path + [name]) + ": " + msg))  # O(1)
            seen.append((path[-1] if path else "", _base(name)))  # O(1)
            continue  # O(1)
        m = XCT.match(ln)  # O(1)
        if m:  # XCTest error line | O(1)
            written, num, cls, meth, msg = m.group(1), int(m.group(2)), m.group(3).rsplit(".", 1)[-1], m.group(4), m.group(5)  # O(1)
            if dup(cls, meth):  # first issue per test | O(s)
                continue  # O(1)
            rel = tree.pick(written, num, meth, cls)  # O(f)
            add((rel or "-", num if rel else 0, f"{cls}/{meth}: {msg}"))  # O(1)
            seen.append((cls, meth))  # O(1)
    for ln in lines:  # parallel testing prints no issue lines, only the verdict per test | O(o)
        m = PARALLEL.match(ln)  # O(1)
        if m:  # O(1)
            ident = m.group(1)  # O(1)
            parts = ident.split("/") if "/" in ident else ident.split(".")  # Swift Testing joins with /, XCTest with . | O(len)
            fn, suite = parts[-1], parts[:-1]  # O(1)
            if dup(suite[-1] if suite else "", _base(fn)):  # O(s)
                continue  # O(1)
            seen.append((suite[-1] if suite else "", _base(fn)))  # O(1)
            hit = tree.find_func(_base(fn), suite[-1] if suite else "")  # O(f*n)
            add((hit[0], hit[1], "/".join(hit[2] + [fn]) + ": failed") if hit else ("-", 0, "/".join(suite + [fn]) + ": failed"))  # O(1)
    if not any(XCODE_LINE.match(ln) for ln in lines):  # not xcodebuild output: names stay as the runner printed them | O(o)
        for name in names:  # O(names)
            add(("-", 0, f"{name}: failed"))  # O(1)
        return out  # O(1)
    hints = _failing_block(lines)  # O(o)
    for name in names:  # names the runner counted that no line explained: crashes, lost output | O(names)
        base = _base(name)  # O(len)
        why = "crashed" if name.endswith(" (crashed)") else "failed"  # O(1)
        shown = re.sub(r" \(crashed\)$", "", name)  # O(len)
        shown = re.sub(r" with \d+ test cases?$", "", shown)  # O(len)
        suite = hints.get(base, "")  # O(1)
        if CLASS_METHOD.match(shown):  # Class.method | O(len)
            suite, shown = shown.split("(")[0].rsplit(".", 1)[0].rsplit(".", 1)[-1], base  # O(len)
        if dup(suite, base):  # O(s)
            continue  # O(1)
        seen.append((suite, base))  # O(1)
        hit = None if shown.startswith('"') else tree.find_func(base, suite)  # O(f*n)
        if hit is None and suite:  # the hint may name a type the source nests elsewhere | O(1)
            hit = tree.find_func(base, "")  # O(f*n)
        add((hit[0], hit[1], "/".join(hit[2] + [shown]) + f": {why}") if hit else ("-", 0, "/".join(([suite] if suite else []) + [shown]) + f": {why}"))  # O(1)
    return out  # O(1)
