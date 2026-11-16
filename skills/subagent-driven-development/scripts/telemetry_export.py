#!/usr/bin/env python3
"""Backfill of the local event log: rebuild contract lines from the existing ledgers (`sl telemetry export`).

    telemetry_export.py is reached through `sl telemetry export --since YYYY-MM-DD [--root DIR]... [--out FILE]`

`rebuild(since, roots, home) -> list[dict]`: `agent_stop` per `<home>/history.jsonl` row, `run_start` and `run_end` per run
archive `<root>/.superlite/runs/*/`, `dispatch` per archived `metrics.jsonl` launch row, `tests` per archived
`test-summary-*.json`, `batch` per `<root>/.superlite/batch-costs.jsonl` row, `feedback` per `<home>/feedback.jsonl` entry; every
line carries `backfill: true`, sorted by `t`. Free text of the sources (`desc`, `last`, `text`, failure names) is never copied.
`main(a)` prints the lines, or writes `--out` whole; a bad date exits 2. Never writes `events.jsonl`. Stdlib only.
"""
# Complexity notation:
#   R = rows of the ledgers, A = run archives, F = files of one archive
import argparse  # O(1)
import json  # O(1)
import re  # O(1)
import subprocess  # O(1)
import sys  # O(1)
from datetime import date, datetime, timezone  # O(1)
from pathlib import Path  # O(1)

sys.path.insert(0, str(Path(__file__).resolve().parent))  # O(1)
import telemetry  # noqa: E402 | O(1)

TASK_RE = re.compile(r"\b([A-Z]{1,2}\d+[a-z]?)\b")  # a task id inside a launch description; the rest is never read | O(1)


def _rows(path):  # the JSON objects of a JSONL file; bad lines skipped | O(R)
    try:  # O(1)
        text = Path(path).read_text(encoding="utf-8", errors="replace")  # O(size)
    except OSError:  # O(1)
        return []  # O(1)
    out = []  # O(1)
    for raw in text.splitlines():  # O(R)
        try:  # O(1)
            row = json.loads(raw)  # O(len)
        except ValueError:  # O(1)
            continue  # O(1)
        if isinstance(row, dict):  # O(1)
            out.append(row)  # O(1)
    return out  # O(R)


def _json(path):  # a JSON object file, {} when missing or bad | O(size)
    try:  # O(1)
        data = json.loads(Path(path).read_text(encoding="utf-8", errors="replace"))  # O(size)
    except (OSError, ValueError):  # O(1)
        return {}  # O(1)
    return data if isinstance(data, dict) else {}  # O(1)


def _utc(dt):  # a datetime as UTC; a naive one is local time | O(1)
    return (dt.astimezone() if dt.tzinfo is None else dt).astimezone(timezone.utc)  # O(1)


def _stamp(dt) -> str:  # O(1)
    return _utc(dt).strftime("%Y-%m-%dT%H:%M:%S.") + f"{_utc(dt).microsecond // 1000:03d}Z"  # O(1)


def _when(v):  # epoch seconds or ms, ISO text or YYYY-MM-DD, as a UTC datetime; None when unreadable | O(1)
    try:  # O(1)
        if isinstance(v, bool):  # O(1)
            return None  # O(1)
        if isinstance(v, (int, float)):  # O(1)
            return datetime.fromtimestamp(v / 1000 if v > 1e11 else v, timezone.utc)  # O(1)
        if isinstance(v, str) and re.fullmatch(r"\d{4}-\d\d-\d\d", v):  # O(1)
            return datetime.fromisoformat(v).replace(tzinfo=timezone.utc)  # O(1)
        if isinstance(v, str):  # O(1)
            return _utc(datetime.fromisoformat(v.replace("Z", "+00:00")))  # O(1)
    except (ValueError, OverflowError, OSError):  # O(1)
        return None  # O(1)
    return None  # O(1)


def _line(kind, when, **fields) -> dict:  # one validated-shape line, or a dict the caller drops | O(k)
    line = {"v": 1, "t": _stamp(when), "kind": kind}  # O(1)
    for k in telemetry.COMMON[3:]:  # O(1)
        line[k] = fields.pop(k, None)  # O(1)
    for k in telemetry.KINDS[kind]:  # O(k)
        line[k] = fields.get(k)  # O(1)
    line["backfill"] = True  # O(1)
    return line  # O(1)


def _num(v):  # a number or None | O(1)
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None  # O(1)


def _str(v):  # a short string or None | O(1)
    return v if isinstance(v, str) and v else None  # O(1)


def _history(home):  # O(R)
    for row in _rows(Path(home) / "history.jsonl"):  # O(R)
        when = _when(row.get("date"))  # O(1)
        if when is None:  # O(1)
            continue  # O(1)
        tok = row.get("tokens")  # O(1)
        tok = {k: tok.get(k) for k in ("in", "out", "cache_read", "cache_write")} if isinstance(tok, dict) else None  # O(1)
        yield _line("agent_stop", when, run=_str(row.get("run")), task=_str(row.get("task")), role=None,
                    model=_str(row.get("model")), duration_s=_num(row.get("duration_s")), tokens=tok,
                    cost_usd=_num(row.get("cost_usd")), tool_calls=_num(row.get("tool_calls")))  # O(1)


def _feedback(home):  # O(R)
    for e in _rows(Path(home) / "feedback.jsonl"):  # O(R)
        when = _when(e.get("date"))  # O(1)
        if when is not None:  # O(1)
            yield _line("feedback", when, fkind=_str(e.get("kind")))  # reason and text are free text | O(1)


def _batches(root):  # O(R)
    for row in _rows(Path(root) / ".superlite" / "batch-costs.jsonl"):  # O(R)
        when = _when(row.get("t"))  # O(1)
        if when is None:  # O(1)
            continue  # O(1)
        lead = row.get("lead") if isinstance(row.get("lead"), dict) else {}  # O(1)
        yield _line("batch", when, repo_root=str(root), batch=_str(row.get("batch")), state=_str(row.get("end")),
                    lead_model=_str(lead.get("model")), pr=row.get("pr") if isinstance(row.get("pr"), (int, str)) else None)  # O(1)


def _archive(d):  # the lines of one run archive | O(F + R)
    man, rep = _json(d / "run.json"), _json(d / "build-report.json")  # O(size)
    run = _str(man.get("run_id")) or d.name  # O(1)
    root = str(d.parent.parent.parent)  # <root>/.superlite/runs/<archive> | O(1)
    log = [r for r in _rows(d / "lint-log.jsonl") if _when(r.get("time"))]  # O(R)
    first = _when(log[0]["time"]) if log else None  # O(1)
    ended = _when(man.get("ended"))  # O(1)
    m = re.match(r"(\d{8})-(\d{6})", d.name)  # O(1)
    named = _when(f"{m[1][:4]}-{m[1][4:6]}-{m[1][6:]}T{m[2][:2]}:{m[2][2:4]}:{m[2][4:]}") if m else None  # local time | O(1)
    start = first or named or ended  # O(1)
    stable = max((r["stable"] for r in log if isinstance(r.get("stable"), int)), default=None)  # O(R)
    tasks = len(rep["tasks"]) if isinstance(rep.get("tasks"), list) else stable  # O(1)
    plan = man.get("plan")  # O(1)
    if start is not None:  # O(1)
        yield _line("run_start", start, run=run, repo_root=root, plan=Path(plan).name if isinstance(plan, str) and plan else None,
                    tasks=tasks, branch=_str(man.get("branch")))  # O(1)
    end = ended or (_when(log[-1]["time"]) if log else None) or start  # O(1)
    head = rep.get("headline") if isinstance(rep.get("headline"), dict) else {}  # O(1)
    qual = rep.get("quality") if isinstance(rep.get("quality"), dict) else {}  # O(1)
    tests = qual.get("tests") if isinstance(qual.get("tests"), dict) else {}  # O(1)

    def pick(group, key):  # O(1)
        g = head.get(group)  # O(1)
        return _num(g.get(key)) if isinstance(g, dict) else None  # O(1)
    cp = rep.get("critical_path") if isinstance(rep.get("critical_path"), dict) else {}  # O(1)
    wall = pick("wall_min", "actual")  # O(1)
    if end is not None:  # O(1)
        yield _line("run_end", end, run=run, repo_root=root, outcome="done", wall_s=round(wall * 60, 3) if wall is not None else None,
                    cost_usd=pick("cost_usd_agents", "actual"), tasks=tasks, first_time_pass=_num(qual.get("first_time_pass")),
                    fix_rounds=_num(qual.get("rework_dispatches")), agents=pick("agents", "actual"),
                    tests_passed=_num(tests.get("passed")), tests_failed=_num(tests.get("failed")),
                    projected_min=pick("wall_min", "projected"), critical_path_min=_num(cp.get("projected_min")))  # O(1)
    for row in _rows(d / "metrics.jsonl"):  # O(R)
        when = _when(row.get("t"))  # O(1)
        if row.get("ev") != "launch" or when is None:  # O(1)
            continue  # O(1)
        found = TASK_RE.search(row["desc"]) if isinstance(row.get("desc"), str) else None  # only the id leaves the text | O(len)
        yield _line("dispatch", when, run=run, repo_root=root, task=found[1] if found else None, agent_type=_str(row.get("type")),
                    model=_str(row.get("model")))  # O(1)
    for p in sorted(d.glob("test-summary-*.json")):  # O(F)
        s = _json(p)  # O(size)
        if not s:  # O(1)
            continue  # O(1)
        try:  # O(1)
            when = _when(s.get("started")) or datetime.fromtimestamp(p.stat().st_mtime, timezone.utc)  # O(1)
        except OSError:  # O(1)
            continue  # O(1)
        yield _line("tests", when, run=run, repo_root=root, mode=_str(s.get("mode")), passed=_num(s.get("passed")), failed=_num(s.get("failed")),
                    skipped=_num(s.get("skipped")), seconds=_num(s.get("seconds")), task=_str(s.get("task")))  # O(1)


def rebuild(since, roots, home) -> list:  # every line of the ledgers from `since` on, sorted by t | O(R log R)
    floor = _stamp(datetime(since.year, since.month, since.day, tzinfo=timezone.utc))  # O(1)
    lines = list(_history(home)) + list(_feedback(home))  # O(R)
    for root in roots:  # O(roots)
        lines += list(_batches(root))  # O(R)
        runs = Path(root) / ".superlite" / "runs"  # O(1)
        try:  # O(1)
            dirs = sorted(p for p in runs.iterdir() if p.is_dir())  # O(A)
        except OSError:  # O(1)
            dirs = []  # O(1)
        for d in dirs:  # O(A)
            lines += list(_archive(d))  # O(F + R)
    lines = [x for x in lines if x["t"] >= floor]  # O(R)
    lines.sort(key=lambda x: x["t"])  # stable | O(R log R)
    return lines  # O(R)


def _default_root():  # the current git top level's main checkout, else the working folder | O(1) + one git process
    try:  # O(1)
        r = subprocess.run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], capture_output=True, text=True)  # O(1)
    except OSError:  # O(1)
        return Path.cwd()  # O(1)
    common = Path(r.stdout.strip()) if r.returncode == 0 and r.stdout.strip() else None  # O(1)
    return common.parent if common is not None and common.name == ".git" else Path.cwd()  # O(1)


def main(a) -> int:  # O(R log R)
    try:  # O(1)
        since = datetime.strptime(str(a.since), "%Y-%m-%d").date()  # O(1)
    except ValueError:  # O(1)
        print(f"telemetry export: bad date {a.since!r}, want YYYY-MM-DD", file=sys.stderr)  # O(1)
        return 2  # O(1)
    roots = [Path(r) for r in (a.root or [])] or [_default_root()]  # O(roots)
    lines = rebuild(since, roots, telemetry._home())  # O(R log R)
    text = "".join(json.dumps(x, ensure_ascii=False, separators=(",", ":")) + "\n" for x in lines)  # O(R)
    if a.out:  # O(1)
        Path(a.out).write_text(text, encoding="utf-8")  # replaces the file whole | O(size)
    else:  # O(1)
        sys.stdout.write(text)  # O(size)
    return 0  # O(1)


if __name__ == "__main__":  # O(1)
    ap = argparse.ArgumentParser(prog="telemetry_export")  # O(1)
    ap.add_argument("--since", required=True)  # O(1)
    ap.add_argument("--root", action="append", default=[])  # O(1)
    ap.add_argument("--out")  # O(1)
    sys.exit(main(ap.parse_args()))  # O(1)
