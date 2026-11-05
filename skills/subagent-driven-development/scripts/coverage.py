#!/usr/bin/env python3
"""Decision coverage for brainstorming's pass: the category list, the `## Coverage` table check, the skeleton.

    coverage.py [--root DIR]                  print the skeleton table, every row open
    coverage.py check FILE [--root DIR]       print the COVERAGE: and NOTE: lines lint would; exit 1 on a COVERAGE: line

Library, used by `plan_tools lint` and the review packet: categories, coverage_off, section_span, check, skeleton.
Stdlib only.
"""
# Complexity notation:
#   L = text lines, K = categories, R = table rows, c = cells per row
import argparse  # O(1)
import re  # O(1)
import sys  # O(1)
from pathlib import Path  # O(1)

sys.path.insert(0, str(Path(__file__).resolve().parent))  # O(1)
from plan_tools import scan_fences  # noqa: E402 | O(1)

SOURCE = Path(__file__).resolve().parents[2] / "brainstorming" / "coverage.md"  # O(1)
STATES = ("settled", "ruled", "n/a", "spike", "open")  # O(1)
OFF_RE = re.compile(r"^\*\*Coverage:\*\*\s*off\b", re.IGNORECASE)  # O(1)
HEADING_RE = re.compile(r"^(#{1,6})\s")  # O(1)
COVERAGE_RE = re.compile(r"^##\s+coverage", re.IGNORECASE)  # O(1)
SPLIT_RE = re.compile(r"(?<!\\)\|")  # O(1)
NOTE = ("NOTE: no ## Coverage section; brainstorming's coverage pass writes it "  # O(1)
        "(sl coverage prints the table), or set **Coverage:** off")  # O(1)


def norm(s: str) -> str:  # O(len s)
    return re.sub(r"\s+", " ", s.replace("*", "").replace("`", "")).strip().lower()  # O(len s)


def split_row(line: str) -> list[str]:  # O(len line)
    s = line.strip()  # O(len line)
    if s.startswith("|"):  # O(1)
        s = s[1:]  # O(len line)
    if s.endswith("|") and not s.endswith("\\|"):  # O(1)
        s = s[:-1]  # O(len line)
    return [c.strip().replace("\\|", "|") for c in SPLIT_RE.split(s)]  # O(len line)


def table_rows(lines: list[str], flags: list[bool]) -> list[list[str]]:  # O(L + R*c)
    rows = []  # O(1)
    for ln, fenced in zip(lines, flags):  # O(L) iterations
        if fenced or not ln.lstrip().startswith("|"):  # O(len line)
            continue  # O(1)
        if re.fullmatch(r"[\s|:-]*", ln):  # separator | O(len line)
            continue  # O(1)
        cells = split_row(ln)  # O(len line)
        if norm(cells[0]) == "category":  # header | O(len cell)
            continue  # O(1)
        rows.append(cells)  # O(1) amortized
    return rows  # O(1)


def read_lines(text: str) -> list[str]:  # O(len text)
    return text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n").split("\n")  # O(len text)


def categories(root: Path | None = None, source: Path | None = None) -> list[tuple[str, str]]:  # O(L + K)
    src = Path(source) if source else SOURCE  # O(1)
    out: list[tuple[str, str]] = []  # O(1)
    if src.is_file():  # O(1)
        lines = read_lines(src.read_text(encoding="utf-8"))  # O(L)
        flags, _ = scan_fences(lines)  # O(L)
        start = next((i for i, ln in enumerate(lines) if not flags[i] and ln.strip().lower() == "## categories"), None)  # O(L)
        if start is not None:  # O(1)
            end = next((i for i in range(start + 1, len(lines)) if not flags[i] and re.match(r"#{1,2}\s", lines[i])), len(lines))  # O(L)
            for cells in table_rows(lines[start + 1:end], flags[start + 1:end]):  # O(R) iterations
                if len(cells) >= 2 and cells[0] and cells[1]:  # O(1)
                    out.append((cells[0], cells[1]))  # O(1) amortized
    extra = Path(root if root is not None else Path.cwd()) / ".superlite" / "coverage.md"  # O(1)
    if out and extra.is_file():  # O(1)
        lines = read_lines(extra.read_text(encoding="utf-8"))  # O(L)
        flags, _ = scan_fences(lines)  # O(L)
        seen = {norm(n) for n, _ in out}  # O(K)
        for cells in table_rows(lines, flags):  # O(R) iterations
            if len(cells) >= 2 and cells[0] and norm(cells[0]) not in seen:  # O(1)
                out.append((cells[0], cells[1]))  # O(1) amortized
                seen.add(norm(cells[0]))  # O(1)
    return out  # O(1)


def coverage_off(text: str) -> bool:  # O(L)
    lines = read_lines(text)  # O(L)
    flags, _ = scan_fences(lines)  # O(L)
    return any(not f and OFF_RE.match(ln) for ln, f in zip(lines, flags))  # O(L)


def section_span(lines: list[str]) -> tuple[int, int] | None:  # O(L)
    flags, _ = scan_fences(lines)  # O(L)
    start = next((i for i, ln in enumerate(lines) if not flags[i] and COVERAGE_RE.match(ln)), None)  # O(L)
    if start is None:  # O(1)
        return None  # O(1)
    for i in range(start + 1, len(lines)):  # O(L) iterations
        m = HEADING_RE.match(lines[i])  # O(len line)
        if not flags[i] and m and len(m.group(1)) <= 2:  # O(1)
            return (start, i)  # O(1)
    return (start, len(lines))  # O(1)


def check(text: str, task_ids: set[str] | None = None, root: Path | None = None,
          source: Path | None = None) -> tuple[list[str], list[str]]:  # O(L + K*R)
    if coverage_off(text):  # O(L)
        return [], []  # O(1)
    lines = read_lines(text)  # O(L)
    span = section_span(lines)  # O(L)
    if span is None:  # O(1)
        return [], [NOTE]  # O(1)
    cats = categories(root, source)  # O(L + K)
    if not cats:  # O(1)
        return [f"COVERAGE: category list not found: {Path(source) if source else SOURCE}"], []  # O(1)
    flags, _ = scan_fences(lines)  # O(L)
    rows = table_rows(lines[span[0] + 1:span[1]], flags[span[0] + 1:span[1]])  # O(L)
    first: dict[str, list[str]] = {}  # O(1)
    for cells in rows:  # O(R) iterations
        first.setdefault(norm(cells[0]), cells)  # O(len cell)
    issues = []  # O(1)
    for name, _ in cats:  # O(K) iterations
        cells = first.get(norm(name))  # O(len name)
        if cells is None:  # O(1)
            issues.append(f"COVERAGE: no row for '{name}'; add it as settled, ruled, n/a, spike or open")  # O(1)
            continue  # O(1)
        raw = cells[1] if len(cells) > 1 else ""  # O(1)
        basis = cells[2].strip() if len(cells) > 2 else ""  # O(1)
        state = norm(raw)  # O(len raw)
        if state not in STATES:  # O(1)
            issues.append(f"COVERAGE: '{name}' has state '{raw}'; use settled, ruled, n/a, spike or open")  # O(1)
        elif state == "open":  # O(1)
            issues.append(f"COVERAGE: '{name}' is open; ask it or rule it ({basis})")  # O(1)
        elif not basis:  # O(1)
            issues.append(f"COVERAGE: '{name}' is {state} but gives no basis")  # O(1)
        elif state == "spike" and task_ids is not None and not set(re.findall(r"[\w.-]+", basis)) & set(task_ids):  # O(len basis + ids)
            issues.append(f"COVERAGE: '{name}' is spike but names no task of this plan")  # O(1)
    return issues, []  # O(1)


def skeleton(root: Path | None = None, source: Path | None = None) -> str:  # O(L + K)
    out = ["| Category | State | Basis |", "|---|---|---|"]  # O(1)
    for name, asks in categories(root, source):  # O(K) iterations
        out.append(f"| {name} | open | {asks.replace('|', chr(92) + '|')} |")  # O(len asks)
    return "\n".join(out) + "\n"  # O(K)


def main(argv: list[str] | None = None) -> int:  # O(L + K*R)
    ap = argparse.ArgumentParser(prog="coverage", description="Decision coverage table and check.")  # O(1)
    ap.add_argument("--root", default=None)  # O(1)
    ap.add_argument("rest", nargs="*")  # O(1)
    a = ap.parse_args(argv)  # O(len argv)
    root = Path(a.root) if a.root else None  # O(1)
    if not a.rest:  # O(1)
        sys.stdout.write(skeleton(root))  # O(L + K)
        return 0  # O(1)
    if a.rest[0] != "check" or len(a.rest) != 2:  # O(1)
        print("usage: coverage [--root DIR] | coverage check FILE [--root DIR]", file=sys.stderr)  # O(1)
        return 2  # O(1)
    f = Path(a.rest[1])  # O(1)
    if not f.is_file():  # O(1)
        print(f"coverage: not found: {a.rest[1]}", file=sys.stderr)  # O(1)
        return 2  # O(1)
    issues, notes = check(f.read_text(encoding="utf-8"), None, root)  # O(L + K*R)
    for m in issues + notes:  # O(K) iterations
        print(m)  # O(len m)
    return 1 if issues else 0  # O(1)


if __name__ == "__main__":  # O(1)
    sys.exit(main())  # O(1)
