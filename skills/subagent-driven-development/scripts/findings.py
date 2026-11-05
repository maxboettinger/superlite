#!/usr/bin/env python3
"""Turn reviewer findings into fixer briefs: one brief per owning task, at the highest tier of its findings.

    findings.py route --plan P REPORT.json ...      (as `sl findings route --plan P REPORT.json ...`)

Reads the report JSON files `fleet wait` wrote (`<sd>/fleet/reports/<id>.json`), groups every finding by the plan task that
owns its file (a file in no Owns joins the plan's last task), numbers them `F-<Tn>-<n>` (continuing after the ids already
in `<sd>/fixes/` and `<sd>/briefs/`), writes `<sd>/briefs/fix-<first id>.md` and prints one line per brief:

    fixer tier=<sonnet|sonnet-high|opus> brief=<abs path> files=<a,b> task=<Tn>

No findings: `findings: none`. An unreadable report or plan prints `error: ...` to stderr and exits 2.
Library: route, main. Stdlib only.
"""
# Complexity notation:
#   r = reports, k = findings overall, n = plan tasks, o = owned paths overall, f = files in <sd>/fixes and <sd>/briefs
import argparse  # O(1)
import json  # O(1)
import re  # O(1)
import sys  # O(1)
from pathlib import Path  # O(1)

sys.path.insert(0, str(Path(__file__).resolve().parent))  # O(1)
import next_tasks as nt  # noqa: E402 | O(1)
import plan_tools as pt  # noqa: E402 | O(1)
import state  # noqa: E402 | O(1)

TIERS = {1: "sonnet", 2: "sonnet-high", 3: "opus"}  # finding tier -> fixer tier name | O(1)
RULING = "final-review fix outside every Owns"  # the --claim ruling for a file no task owns | O(1)


class ReportError(Exception):  # O(1)
    """A report file that cannot be read or is not a JSON object."""


def load_report(path: str) -> dict:  # O(file)
    try:  # O(1)
        data = json.loads(Path(path).read_text(encoding="utf-8"))  # O(file)
    except (OSError, ValueError) as exc:  # O(1)
        raise ReportError(path) from exc  # O(1)
    if not isinstance(data, dict):  # O(1)
        raise ReportError(path)  # O(1)
    return data  # O(1)


def rel(file: str, root: Path) -> str:  # O(s)
    """A finding path as the plan writes it: no `./`, an absolute path made relative to the root (symlinks resolved)."""
    s = str(file).strip().replace("\\", "/")  # O(s)
    while s.startswith("./"):  # O(s)
        s = s[2:]  # O(s)
    if Path(s).is_absolute():  # O(1)
        p = Path(s).resolve()  # O(d) stat I/O
        try:  # O(1)
            return p.relative_to(root).as_posix()  # O(d)
        except ValueError:  # outside the root: keep it as given | O(1)
            return p.as_posix()  # O(1)
    return s  # O(1)


def one_line(s) -> str:  # O(s)
    return " ".join(str(s).split())  # O(s)


def collect(reports: list[str], root: Path) -> list[dict]:  # O(r + k log k)
    """Findings of all reports, normalized and deduped on (file, line, problem); the first report wins."""
    seen, out = set(), []  # O(1)
    for rp in reports:  # O(r) iterations
        data = load_report(rp)  # O(file)
        label = str(data.get("label") or Path(rp).stem)  # O(1)
        items = data.get("findings")  # O(1)
        for it in items if isinstance(items, list) else []:  # O(k_r) iterations
            if not isinstance(it, dict) or not it.get("file"):  # O(1)
                continue  # O(1)
            try:  # O(1)
                line = int(it.get("line") or 0)  # O(1)
            except (TypeError, ValueError):  # O(1)
                line = 0  # O(1)
            try:  # O(1)
                tier = min(3, max(1, int(it.get("tier") or 1)))  # O(1)
            except (TypeError, ValueError):  # O(1)
                tier = 1  # O(1)
            f = {"file": rel(it["file"], root), "line": line, "problem": one_line(it.get("problem", "")),  # O(s)
                 "fix": one_line(it.get("fix", "")), "tier": tier, "label": label}  # O(s)
            key = (f["file"], f["line"], f["problem"])  # O(1)
            if key not in seen:  # O(1)
                seen.add(key)  # O(1)
                out.append(f)  # O(1)
    return out  # O(1)


def last_n(sd: Path, tid: str) -> int:  # O(f)
    """The highest n of an `F-<tid>-<n>` id in the names of <sd>/fixes and <sd>/briefs and in the heading of a brief."""
    pat = re.compile(rf"(?<![A-Za-z0-9])F-{re.escape(tid)}-(\d+)(?!\d)")  # O(1)
    top = 0  # O(1)
    for sub in ("fixes", "briefs"):  # O(1) iterations (2)
        d = sd / sub  # O(1)
        if not d.is_dir():  # O(1)
            continue  # O(1)
        for p in d.iterdir():  # O(f) iterations
            top = max([top, *(int(m) for m in pat.findall(p.name))])  # O(s)
            if sub == "briefs" and p.name.startswith("fix-") and p.suffix == ".md":  # a brief heading lists all its ids | O(1)
                try:  # O(1)
                    with p.open(encoding="utf-8") as fh:  # O(1)
                        head = fh.readline()  # O(line)
                except OSError:  # O(1)
                    continue  # O(1)
                top = max([top, *(int(m) for m in pat.findall(head))])  # O(line)
    return top  # O(1)


def brief_text(sl_path: str, plan: Path, task, items: list[dict], tier: int) -> str:  # O(k + o)
    ids = ", ".join(i["id"] for i in items)  # O(k)
    owns = task.owns  # O(o)
    outside = sorted({i["file"] for i in items if not nt.owns_match(i["file"], owns)})  # files no Owns of this task lists | O(k)
    lines = [f"# Fix {ids} · tier {tier} · task {task.id}",  # O(1)
             f"sl (type it literally in every command): {sl_path}",  # O(1)
             f"PLAN={plan}",  # O(1)
             f"Task: {task.id} · Owns: {', '.join(owns)}",  # O(o)
             "", "Findings:"]  # O(1)
    lines += [f"- {i['id']} {i['file']}:{i['line']} - {i['problem']} - {i['fix']} (tier {i['tier']}, from {i['label']})"  # O(k)
              for i in items]  # O(k)
    lines += ["",  # O(1)
              "Per finding: read `.superlite/fixes/<id>.md` first if it exists, and rewrite it when you finish (fixing.md format). "  # O(1)
              "Fix only these findings, one regression test each.",  # O(1)
              "",  # O(1)
              f"Verify: `{sl_path} run_tests --fast <the test files you touched> --background`, then the printed "  # O(1)
              "`run_tests --wait <path>` line.",  # O(1)
              f"Commit: `{sl_path} commit_task {task.id} --plan {plan}`"]  # O(1)
    for f in outside:  # O(k) iterations
        lines.append(f"Before committing {f} (outside {task.id}'s Owns): "  # O(1)
                     f"`{sl_path} commit_task {task.id} --claim {f} --ruling \"{RULING}\" --plan {plan}`")  # O(1)
    return "\n".join(lines) + "\n"  # O(k)


def route(sd: Path, plan: Path, reports: list[str], sl_path: str) -> list[str]:  # O(r + k log k + n*o + f)
    """Write one fixer brief per owning task; return the `fixer ...` lines in plan task order."""
    sd = Path(sd).resolve()  # O(d)
    root = Path(state.git_root(sd) or sd.parent)  # the project root, as fleet.py does | O(d)
    plan = Path(plan).resolve()  # O(d)
    tasks = pt.Plan.load(str(plan)).tasks  # O(C+L)
    if not tasks:  # O(1)
        raise pt.PlanError(f"plan has no tasks: {plan}")  # O(1)
    def owner_of(path):  # the first task whose Owns match (file, directory or glob), else the last task | O(o)
        return next((t for t in tasks if nt.owns_match(path, t.owns)), tasks[-1])  # O(o)
    groups = {t.id: [] for t in tasks}  # O(n)
    for f in collect(reports, root):  # O(k) iterations
        groups[owner_of(f["file"]).id].append(f)  # a file in no Owns belongs to the last task | O(1)
    lines = []  # O(1)
    for t in tasks:  # O(n) iterations
        items = sorted(groups[t.id], key=lambda f: (f["file"], f["line"]))  # O(k_t log k_t)
        if not items:  # O(1)
            continue  # O(1)
        n = last_n(sd, t.id)  # O(f)
        for i, f in enumerate(items, n + 1):  # O(k_t) iterations
            f["id"] = f"F-{t.id}-{i}"  # O(1)
        tier = max(f["tier"] for f in items)  # O(k_t)
        brief = sd / "briefs" / f"fix-{items[0]['id']}.md"  # O(1)
        brief.parent.mkdir(parents=True, exist_ok=True)  # O(1) I/O
        brief.write_text(brief_text(sl_path, plan, t, items, tier), encoding="utf-8")  # O(k_t) I/O
        files = ",".join(sorted({f["file"] for f in items}))  # O(k_t log k_t)
        lines.append(f"fixer tier={TIERS[tier]} brief={brief} files={files} task={t.id}")  # O(1)
    return lines  # O(n)


def main(argv=None) -> int:  # O(d + route)
    ap = argparse.ArgumentParser(description=__doc__.split(chr(10))[0])  # O(1)
    sub = ap.add_subparsers(dest="cmd", required=True)  # O(1)
    r = sub.add_parser("route", help="write one fixer brief per owning task and print the fixer lines")  # O(1)
    r.add_argument("--plan", required=True)  # O(1)
    r.add_argument("reports", nargs="+", metavar="REPORT.json")  # O(1)
    a = ap.parse_args(argv)  # O(1)
    sl_path = str(Path(__file__).resolve().parent / "sl")  # O(1)
    try:  # O(1)
        lines = route(state.resolve(a.plan), Path(a.plan), a.reports, sl_path)  # O(route)
    except ReportError as exc:  # O(1)
        print(f"error: cannot read report {exc}", file=sys.stderr)  # O(1)
        return 2  # O(1)
    except pt.PlanError as exc:  # O(1)
        print(f"error: {exc}", file=sys.stderr)  # O(1)
        return 2  # O(1)
    print("\n".join(lines) if lines else "findings: none")  # O(n)
    return 0  # O(1)


if __name__ == "__main__":  # O(1)
    sys.exit(main())  # O(1)
