#!/usr/bin/env python3
"""Print the closing summary of a run.

    finish.py [--plan PLAN] [--ledger .superlite/progress.md] [--log .superlite/incidents.jsonl]

Collects, from the progress ledger, every `Ruling:` line (in order), the
commits and the run's test result (the last `tests full` line that is not a recorded one, else the newest line; a newer run, a recorded one too, prints beside it with the commits made after the full run, #498, #593), plus the open incidents from the log. Open means what the
review packet counts: an incident on a file no longer on disk (inside a git checkout) or at a location a ledger `Ruling:` names, a location whose newest entry is resolved, and a test-failure the newest
covering test summary shows green (a later full run covers every run_tests failure), are not open.
Ledger and log default to the run folder of `--plan` once it holds a run (else the session's run, #178). The
superlite-side stops of the run (guard blocks and rewrites, guard errors, test runs with no result, commit scope
blocks) print as one line, `superlite stops this run: N kind (tool), ...`, and each is also logged as an `auto`
feedback entry (`feedback.add_auto`; a failure to write feedback never fails finish, #140).
A task held by `sl hold` (and not committed) is listed with its reason.
The output ends with the takeover hint (only when another live session owns the run) and then the last line,
`next: sl orchestrator end [--plan PLAN]` (#497): the guard blocks every edit until it runs, a merge-conflict fix too.
Before the takeover hint, `moved_lines` adds one `WARNING:` line per ref of the default branch (local, then `origin/`) that changed files this run owns since the branch left it (#493; warn only, never fails finish).
Idle test trees of the run and orphaned DerivedData are dropped afterwards (#614).
Deterministic: the same files give the same text. Stdlib only.
"""
# Complexity notation:
#   R = lines in the progress ledger, I = lines in the incident log, C = commits and G = rulings found,
#   w = width of one line, F = failures listed in the newest test summary
import argparse  # O(1)
import json  # O(1)
from datetime import datetime, timedelta  # O(1)
import re  # O(1)
import subprocess  # O(1)
import sys  # O(1)
import time  # O(1)
from collections import Counter  # O(1)
from pathlib import Path  # O(1)

DEFAULT_LEDGER = ".superlite/progress.md"  # O(1)
DEFAULT_LOG = ".superlite/incidents.jsonl"  # O(1)
DEFAULT_LINT_LOG = ".superlite/lint-log.jsonl"  # O(1)
END_TAIL = " (archives the run markers; the coordinator guard blocks every edit, a merge-conflict fix too, until it runs)"  # O(1)
UNBLOCKED = re.compile(r"^\s*[-*+]?\s*unblocked:\s*dispatched\s+((?:[A-Z]{1,3}\d+[A-Za-z]?\s*)+?)\s*at\s+(\d\d:\d\d:\d\d)")  # O(1)

RULING = re.compile(r"^\s*(?:[-*+]\s+)?(?:\*\*)?Ruling:(?:\*\*)?\s*(.*?)\s*$")  # O(1)
COMMIT = re.compile(r"^\s*[-*+]?\s*commit\s+([A-Z]{1,3}\d+[A-Za-z]?)\s+([0-9a-f]{7,40})\s*(.*?)\s*$")  # O(1)
TESTS = re.compile(r"^\s*[-*+]?\s*tests\s+(\w+)\s+passed=(\d+)\s+failed=(\d+)"  # O(1)
                   r"\s+skipped=(\d+)\s+seconds=([\d.]+)(\s+recorded)?")  # O(1)


def read_ledger(path):  # O(R*w)
    p = Path(path)  # O(1)
    if not p.exists():  # O(1) stat
        return [], [], None  # O(1)
    rulings, commits, tests = [], [], None  # O(1)
    for line in p.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n").split("\n"):  # O(R) iterations; read + split O(ledger bytes)
        m = RULING.match(line)  # O(w) regex
        if m:  # O(1)
            rulings.append(m.group(1))  # O(1)
            continue  # O(1)
        m = COMMIT.match(line)  # O(w) regex
        if m:  # O(1)
            commits.append(m.groups())  # O(1)
            continue  # O(1)
        m = TESTS.match(line)  # O(w) regex
        if m:  # O(1)
            tests = m.groups()  # O(1)
    return rulings, commits, tests  # O(1)


def test_result(ledger):  # O(R*w) (result, newer run, count of runs after the result); (None, None, 0) when no tests line
    p = Path(ledger)  # O(1)
    try:  # O(1)
        text = p.read_text(encoding="utf-8", errors="replace")  # O(ledger bytes)
    except OSError:  # O(1)
        return None, None, 0  # O(1)
    runs = []  # O(1)
    for line in text.replace("\r\n", "\n").split("\n"):  # O(R)
        m = TESTS.match(line)  # O(w) regex
        if m:  # O(1)
            mode, pa, fa, sk, sec, rec = m.groups()  # O(1)
            runs.append({"mode": mode, "passed": int(pa), "failed": int(fa), "skipped": int(sk), "seconds": float(sec), "recorded": bool(rec)})  # O(1)
    if not runs:  # O(1)
        return None, None, 0  # O(1)
    i = max((k for k, r in enumerate(runs) if r["mode"] == "full" and not r["recorded"]), default=len(runs) - 1)  # a recorded run never counts as the full run (#593) | O(R)
    after = runs[i + 1:]  # O(R)
    return runs[i], (after[-1] if after else None), len(after)  # O(1)


def commits_after_full(ledger):  # O(R*w) task ids committed after the last full (non-recorded) tests line, first-seen order; [] when none
    try:  # O(1)
        text = Path(ledger).read_text(encoding="utf-8", errors="replace")  # O(ledger bytes)
    except OSError:  # O(1)
        return []  # O(1)
    out, seen_full = [], False  # O(1)
    for line in text.replace("\r\n", "\n").split("\n"):  # O(R)
        m = TESTS.match(line)  # O(w) regex
        if m:  # O(1)
            if m.group(1) == "full" and not m.group(6):  # O(1)
                out, seen_full = [], True  # O(1)
            continue  # O(1)
        m = COMMIT.match(line)  # O(w) regex
        if m and seen_full and m.group(1) not in out:  # O(C)
            out.append(m.group(1))  # O(1)
    return out  # O(1)


def _pt_review():  # O(1) after the first import; None when pt_review cannot be imported
    """pt_review (it pulls in plan_tools and more), or None: the closing summary must not die over its filter."""
    here = str(Path(__file__).resolve().parent)  # O(1)
    if here not in sys.path:  # O(path entries)
        sys.path.insert(0, here)  # O(1)
    try:  # O(1)
        import pt_review  # lazy | O(1)
    except Exception:  # noqa: BLE001 (ImportError, or any error raised while it loads) | O(1)
        return None  # O(1)
    return pt_review  # O(1)


def load_test_summary(sl_dir):  # O(file) the newest test summary, as the review packet reads it; None when absent or unreadable
    pt = _pt_review()  # O(1)
    if pt is None:  # O(1)
        return None  # O(1)
    return pt.load_summary(pt.newest_summary_path(Path(sl_dir) / "test-summary.json"))  # O(file)


def load_run_summaries(sl_dir):  # O(S*file) every test summary of the run, newest first; [] when none
    pt = _pt_review()  # O(1)
    if pt is None:  # O(1)
        return []  # O(1)
    return pt.run_summaries(Path(sl_dir) / "test-summary.json")  # O(S*file)


def _stale(pt, entry, summary):  # O(S*F) summary: one summary dict, or a newest-first list of them
    try:  # O(1)
        runs = summary if isinstance(summary, list) else [summary]  # O(1)
        return pt.stale_in_run(entry, [r for r in runs if r])  # O(S*F)
    except (TypeError, ValueError, AttributeError):  # a structurally malformed summary keeps the incident open | O(1)
        return False  # O(1)


def _logged_open(path):  # O(I*w) the plain filter, used when pt_review cannot be imported
    p = Path(path)  # O(1)
    out = []  # O(1)
    if not p.exists():  # O(1) stat
        return out  # O(1)
    for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():  # O(I) iterations; read O(log bytes)
        try:  # O(1)
            e = json.loads(ln)  # O(w)
        except json.JSONDecodeError:  # O(1)
            continue  # O(1)
        if (isinstance(e, dict) and "file" in e and e.get("kind") != "verified"  # O(1)
                and e.get("resolution") in (None, "open", "unresolved")):  # O(1)
            out.append(e)  # O(1)
    return out  # O(1)


def _git_top(path):  # O(1) + spawn; the git toplevel of the log's folder, None outside git or on any error
    try:  # O(1)
        import worktree  # O(1)
        rc, top, _ = worktree.git(path.resolve().parent, "rev-parse", "--show-toplevel")  # O(1) + spawn
        return Path(top.strip()) if not rc and top.strip() else None  # O(1)
    except Exception:  # noqa: BLE001 | O(1)
        return None  # O(1)


def _drop_gone_and_ruled(pt, path, entries, top, ledger=None):  # O(I*R*m + I) outside git (top None) the gone-file filter is skipped
    try:  # O(1)
        if top is not None:  # O(1)
            entries = pt.split_gone(top, entries, None)[0]  # O(I)
        rulings = pt.ledger_rulings(Path(ledger) if ledger else path.with_name("progress.md"))  # O(ledger bytes)
        return [e for e in entries if not pt.ruled(e, rulings)]  # O(I*R*m)
    except Exception:  # noqa: BLE001 | O(1)
        return entries  # O(1)


def open_incidents(path, summary=None, ledger=None):  # O(I*w + I*F)
    """Open incidents as the review packet counts them: a location whose newest entry is resolved is not open,
    and (with a test summary) neither is a test-failure the newest run shows green."""
    pt = _pt_review()  # O(1)
    if pt is None:  # O(1)
        return _logged_open(path)  # O(I*w)
    top = _git_top(Path(path))  # O(1) + spawn
    entries = pt.read_incidents(Path(path), top)  # O(I) every parsed entry, resolved ones included; paths as the packet normalizes them
    entries = _drop_gone_and_ruled(pt, Path(path), entries, top, ledger)  # O(I*R*m + I) as the packet leaves them out (B127)
    entries = [e for e in entries if not _stale(pt, e, summary)]  # the packet drops stale test failures before it looks for superseded locations | O(I*F)
    gone = pt.superseded(entries)  # O(I) before the open filter
    return [e for e in entries  # O(I) iterations
            if e.get("kind") != "verified" and e.get("resolution") in (None, "open", "unresolved")  # O(1)
            and (e["file"], e["line"]) not in gone]  # O(1)


def ranked_incidents(incidents):  # O(I) hashing + O(G log G) sort
    """Distinct (file, line, kind, context) groups with their counts, most frequent first, ties in log order."""
    counts = {}  # group -> count, insertion order is log order | O(1)
    for e in incidents:  # O(I) iterations
        key = (e["file"], e["line"], e.get("kind") or "unknown", e.get("context", ""))  # O(w) hash
        counts[key] = counts.get(key, 0) + 1  # O(1)
    return sorted(counts.items(), key=lambda kv: -kv[1])  # O(G log G); stable sort keeps log order on ties


def group_incidents(incidents, limit=15):  # O(I + G log G + limit*w)
    """Summary lines for the open incidents: identical ones collapse to `Nx`, at most `limit` lines then a more line."""
    ranked = ranked_incidents(incidents)  # O(I + G log G)
    lines = []  # O(1)
    for (file, line, kind, context), n in ranked[:limit]:  # O(limit) iterations
        prefix = f"{n}x " if n > 1 else ""  # O(1)
        lines.append(f"- {prefix}{file}:{line} [{kind}] {context}")  # O(w)
    if len(ranked) > limit:  # O(1)
        lines.append(f"- (+{len(ranked) - limit} more)")  # O(1)
    return lines  # O(1)


STOP_KINDS = ("rule-block", "rule-rewrite", "guard-error", "no-result")  # incident kinds the hooks, lint and run_tests log for a stop | O(1)
UNRESOLVED = ("", "none", "open", "unresolved")  # as commit_task reads a block's state | O(1)


def _error_target(file, line, context):  # O(w) a commit_task block's target: file[:line] plus the error, cut at 150 chars
    reason = re.sub(r"^[A-Z]{1,3}\d+[A-Za-z]?:\s*", "", " ".join(str(context or "").split()))  # drop the task prefix | O(w)
    reason = reason.removesuffix("; nothing committed").strip()  # O(w)
    if reason.startswith("change outside Owns") or "blocked by commit_task" in reason:  # a scope block names no error | O(1)
        reason = ""  # O(1)
    try:  # O(1)
        n = int(line or 0)  # O(1)
    except (TypeError, ValueError):  # O(1)
        n = 0  # O(1)
    head = f"{file}:{n}" if n > 0 else file  # O(1)
    return f"{head} {reason[:150]}" if reason else head  # O(1)


def read_stops(path):  # O(I*w) the stops of a run: (kind, tool, target) per incident, in log order
    """Superlite-side stops from the incident log: the kinds in STOP_KINDS, and an open `exception` of commit_task (a
    commit scope block or a refused commit). `tool` is the entry's `tool` (the hook or command that stopped), else its
    `agent`; hook entries carry no file, so `target` is the entry's `target`, else its file.
    A rule-block row's `rule` and `cwd` follow the target as ` (rule R, cwd C)`, ` (rule R)` or ` (cwd C)` (#233)."""
    p = Path(path)  # O(1)
    out = []  # O(1)
    if not p.is_file():  # O(1)
        return out  # O(1)
    for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():  # O(I) iterations
        try:  # O(1)
            e = json.loads(ln)  # O(w)
        except ValueError:  # O(1)
            continue  # O(1)
        if not isinstance(e, dict):  # O(1)
            continue  # O(1)
        kind = e.get("kind")  # O(1)
        if kind == "exception" and e.get("agent") == "commit_task":  # O(1)
            if str(e.get("resolution") or "").lower() not in UNRESOLVED:  # a block a later commit resolved is not a stop | O(1)
                continue  # O(1)
        elif kind not in STOP_KINDS:  # O(1)
            continue  # O(1)
        if kind == "no-result" and e.get("signal"):  # a signal-killed run is no bug (#548) | O(1)
            continue  # O(1)
        file = str(e.get("file") or "")  # O(1)
        target = str(e.get("target") or ("" if file in ("", "-") else file))  # O(1)
        if kind == "exception" and e.get("agent") == "commit_task" and file not in ("", "-") and not e.get("target"):  # O(1)
            target = _error_target(file, e.get("line"), e.get("context"))  # O(w)
        extra = [f"{k} {' '.join(str(e[k]).split())}" for k in ("rule", "cwd") if e.get(k)]  # O(w)
        if extra:  # O(1)
            target += " (" + ", ".join(extra) + ")"  # O(w)
        out.append((kind, str(e.get("tool") or e.get("agent") or "unknown"), target))  # O(1)
    return out  # O(1)


def stops_line(stops):  # O(I + G log G) None when the run had no stops
    """`superlite stops this run: 2 rule-block (block-coordinator-edits), 1 no-result (run_tests)`: most frequent first."""
    counts = {}  # (kind, tool) -> count, insertion order is log order | O(1)
    for kind, tool, _target in stops:  # O(I) iterations
        counts[(kind, tool)] = counts.get((kind, tool), 0) + 1  # O(1)
    if not counts:  # O(1)
        return None  # O(1)
    ranked = sorted(counts.items(), key=lambda kv: -kv[1])  # O(G log G); stable: ties keep log order
    return "superlite stops this run: " + ", ".join(f"{n} {kind} ({tool})" for (kind, tool), n in ranked)  # O(G)


def log_auto(stops, run=""):  # O(I*w) one `feedback.add_auto` per stop; the number written; never raises
    """Each stop becomes one `auto` feedback entry (tool, kind as the reason, target); triage groups the repeats.
    The target already carries a rule-block's ` (rule R, cwd C)` suffix from `read_stops` (#233)."""
    try:  # feedback is optional here: finish must not die over it | O(1)
        sys.path.insert(0, str(Path(__file__).resolve().parent))  # O(1)
        import feedback  # lazy | O(1)
        version = feedback.version()  # O(size of package.json)
    except Exception:  # noqa: BLE001 | O(1)
        return 0  # O(1)
    marker = Path(run).with_name("finish-auto.json") if run else None  # per run folder: stops already fed to feedback | O(1)
    have = {}  # "tool|kind|target" -> how many a finish of this run already logged: a repeat adds only the new ones | O(1)
    try:  # O(1)
        have = json.loads(marker.read_text(encoding="utf-8")) if marker and marker.is_file() else {}  # O(size)
        have = have if isinstance(have, dict) else {}  # O(1)
    except (OSError, ValueError):  # O(1)
        have = {}  # O(1)
    seen = {}  # stops of this call per key | O(1)
    written = 0  # O(1)
    for kind, tool, target in stops:  # O(I) iterations
        try:  # O(1)
            k = "|".join((tool, kind, target))  # O(w)
            seen[k] = seen.get(k, 0) + 1  # O(1)
            if seen[k] <= int(have.get(k, 0)):  # an earlier finish of this run logged it | O(1)
                continue  # O(1)
            if feedback.add_auto(tool, kind, target, version):  # O(w) + locked append
                written += 1  # O(1)
            else:  # not written: a later finish tries again | O(1)
                seen[k] -= 1  # O(1)
        except Exception:  # noqa: BLE001 | O(1)
            seen[k] = seen.get(k, 1) - 1  # O(1)
    if marker:  # O(1)
        try:  # O(1)
            marker.write_text(json.dumps({k: max(n, int(have.get(k, 0))) for k, n in seen.items()}), encoding="utf-8")  # O(k)
        except OSError:  # O(1)
            pass  # O(1)
    return written  # O(1)


def _clock(t):  # O(1) HH:MM:SS
    return t.strftime("%H:%M:%S")  # O(1)


def unblocked_report(ledger, lint_log):  # O(R*w + L*n)
    """One line: were all stable tasks dispatched before the next patch, with the lint and ledger times behind a NO."""
    lp = Path(lint_log)  # O(1)
    if not lp.exists():  # O(1)
        return "unblocked: no lint log recorded"  # O(1)
    lints = []  # (time, pending) per lint, in file order | O(1)
    for ln in lp.read_text(encoding="utf-8", errors="replace").splitlines():  # O(L) iterations
        try:  # O(1)
            e = json.loads(ln)  # O(w)
            lints.append((datetime.fromisoformat(e["time"]), list(e.get("pending") or [])))  # O(n)
        except (ValueError, KeyError, TypeError):  # O(1)
            continue  # O(1)
    if not lints:  # O(1)
        return "unblocked: no lint log recorded"  # O(1)
    ledger_p = Path(ledger)  # O(1)
    sent_at, committed, any_sent = {}, set(), False  # O(1)
    prev = lints[0][0]  # the ledger clock is read forward from the first lint | O(1)
    for line in (ledger_p.read_text(encoding="utf-8", errors="replace").splitlines() if ledger_p.exists() else []):  # O(R)
        m = UNBLOCKED.match(line)  # O(w)
        if m:  # O(1)
            any_sent = True  # O(1)
            at = datetime.combine(prev.date(), datetime.strptime(m.group(2), "%H:%M:%S").time())  # O(1)
            at = at + timedelta(days=1) if at < prev - timedelta(hours=12) else at  # O(1)
            prev = max(prev, at)  # O(1)
            for t in m.group(1).split():  # O(tasks)
                sent_at.setdefault(t, at)  # first time naming t | O(1)
            continue  # O(1)
        m = COMMIT.match(line)  # O(w)
        if m:  # O(1)
            committed.add(m.group(1))  # O(1)
    offered = {}  # task -> time of the first lint whose pending holds it | O(1)
    for when, pending in lints:  # O(L)
        for t in pending:  # O(n)
            offered.setdefault(t, when)  # O(1)
    held = {}  # task -> (offered, next lint, sent) at its first pair still unsent | O(1)
    for (_, a), (bt, b) in zip(lints, lints[1:]):  # O(L)
        for t in a:  # O(n)
            if t in b and t not in held and not (t in sent_at and sent_at[t] <= bt + timedelta(seconds=1)):  # O(1)
                held[t] = (offered[t], bt, sent_at.get(t))  # O(1)
    lags = [max(0, (sent_at[t] - offered[t]).total_seconds()) for t in sent_at if t in offered]  # O(tasks)
    if lags:  # O(1)
        worst = f"max lag {max(lags):.0f}s"  # O(1)
    else:  # O(1)
        worst = "max lag n/a (no `unblocked:` lines)" if not any_sent else "max lag n/a (no logged task was offered by a lint)"  # O(1)
    missing = [t for t in lints[-1][1] if t not in sent_at and t not in committed]  # O(n)
    if held:  # O(1)
        groups = {}  # (offered, next, sent) -> ids, first-seen order | O(1)
        for t, key in held.items():  # O(h)
            groups.setdefault(key, []).append(t)  # O(1)
        parts = []  # O(1)
        for i, ((o, nx, s), ids) in enumerate(list(groups.items())[:3]):  # O(1) at most 3 groups
            why = f"sent {_clock(s)}" if s else "no unblocked: line names it"  # O(1)
            parts.append(f"{' '.join(ids)}{' still waiting at the next lint' if i == 0 else ''} (offered {_clock(o)}, next lint {_clock(nx)}, {why})")  # O(n)
        more = f", +{len(groups) - 3} more" if len(groups) > 3 else ""  # O(1)
        return f"unblocked: NO - {', '.join(parts)}{more}; {worst}"  # O(1)
    if missing:  # O(1)
        return (f"unblocked: NO - never dispatched: {' '.join(missing)} (pending at the last lint {_clock(lints[-1][0])}; "  # O(1)
                f"no unblocked: line or commit names them); {worst}")
    return f"unblocked: yes - every stable task was dispatched before the next patch; {worst}"  # O(1)


def _default_ref(g, top):  # O(1) + spawns: the default branch ref a run branched from, None when none exists
    rc, out, _ = g(top, "symbolic-ref", "-q", "--short", "refs/remotes/origin/HEAD")  # O(1) + spawn
    names = ([out] if not rc and out else []) + ["origin/main", "main", "master"]  # O(1)
    for n in names:  # O(1) iterations
        if g(top, "rev-parse", "--verify", "-q", f"{n}^{{commit}}")[0] == 0:  # O(1) + spawn
            return n  # O(1)
    return None  # O(1)


def inline_commits(sd):  # O(C) + git spawns
    """-> (base, [(sha, subject), ...]) the branch commits since the run's base, oldest first (an inline run has no commit lines, #668);
    base = checkpoints.json `base`, else the merge-base of HEAD with the default branch. None when there is no base, no commit or any error."""
    try:  # O(1)
        sys.path.insert(0, str(Path(__file__).resolve().parent))  # O(1)
        import worktree  # O(1)
        g = worktree.git  # O(1)
        top = _git_top(Path(sd) / "x")  # O(1) + spawn
        if top is None:  # O(1)
            return None  # O(1)
        base = None  # O(1)
        try:  # O(1)
            b = json.loads((Path(sd) / "checkpoints.json").read_text(encoding="utf-8")).get("base")  # O(size)
            if isinstance(b, str) and b and g(top, "rev-parse", "--verify", "-q", f"{b}^{{commit}}")[0] == 0:  # O(1) + spawn
                base = g(top, "rev-parse", f"{b}^{{commit}}")[1]  # O(1) + spawn
        except (OSError, ValueError, AttributeError):  # O(1)
            base = None  # O(1)
        if base is None:  # O(1)
            ref = _default_ref(g, top)  # O(1) + spawns
            rc, mb, _ = g(top, "merge-base", "HEAD", ref) if ref else (1, "", "")  # O(1) + spawn
            if rc or not mb:  # O(1)
                return None  # O(1)
            base = mb  # O(1)
        rc, out, _ = g(top, "log", "--reverse", "--format=%H%x00%s", f"{base}..HEAD")  # O(C) + spawn
        rows = [tuple(ln.split("\0", 1)) for ln in out.split("\n") if "\0" in ln] if not rc else []  # O(C)
        return (base, rows) if rows else None  # O(1)
    except Exception:  # noqa: BLE001 | O(1)
        return None  # O(1)


def spec_rulings(sd):  # O(spec bytes) the `Ruling:` lines of <run folder>/spec.md, in order; [] when none or unreadable
    try:  # O(1)
        text = (Path(sd) / "spec.md").read_text(encoding="utf-8", errors="replace")  # O(size)
    except OSError:  # O(1)
        return []  # O(1)
    return [m.group(1) for m in (RULING.match(ln) for ln in text.replace("\r\n", "\n").split("\n")) if m]  # O(lines)


OK_CONCLUSIONS = ("success", "skipped", "neutral")  # O(1)


def ci_full_run(top, sha):  # O(runs) + spawn (timeout 15 s)
    """-> {"name", "id", "url", "more"} when `gh run list --commit SHA` shows every run completed with success, skipped or neutral
    and one success; None on any error, timeout or other result. Never raises."""
    try:  # O(1)
        cp = subprocess.run(["gh", "run", "list", "--commit", sha, "--json", "databaseId,workflowName,name,status,conclusion,url", "--limit", "20"],  # O(1) + spawn
                            cwd=str(top), capture_output=True, text=True, timeout=15)
        if cp.returncode:  # O(1)
            return None  # O(1)
        runs = json.loads(cp.stdout)  # O(size)
        if not isinstance(runs, list) or not runs or not all(isinstance(r, dict) for r in runs):  # O(runs)
            return None  # O(1)
        if any(r.get("status") != "completed" or r.get("conclusion") not in OK_CONCLUSIONS for r in runs):  # O(runs)
            return None  # O(1)
        first = next((r for r in runs if r.get("conclusion") == "success"), None)  # O(runs)
        if first is None:  # O(1)
            return None  # O(1)
        return {"name": first.get("workflowName") or first.get("name") or "ci", "id": first.get("databaseId"),  # O(1)
                "url": first.get("url") or "", "more": len(runs) - 1}
    except Exception:  # noqa: BLE001 (OSError, timeout, bad JSON) | O(1)
        return None  # O(1)


def ci_line(sd):  # O(runs) + git spawns; the `tests (full, CI)` line when HEAD is clean, pushed and its CI runs are green, else None
    try:  # O(1)
        sys.path.insert(0, str(Path(__file__).resolve().parent))  # O(1)
        import worktree  # O(1)
        top = _git_top(Path(sd) / "x")  # O(1) + spawn
        if top is None:  # O(1)
            return None  # O(1)
        g = worktree.git  # O(1)
        rc, st, _ = g(top, "status", "--porcelain", "--untracked-files=no")  # O(files) + spawn
        if rc or st:  # O(1)
            return None  # O(1)
        rc, sha, _ = g(top, "rev-parse", "HEAD")  # O(1) + spawn
        if rc or not sha:  # O(1)
            return None  # O(1)
        rc, rem, _ = g(top, "branch", "-r", "--contains", sha)  # O(refs) + spawn
        if rc or not rem:  # O(1)
            return None  # O(1)
        r = ci_full_run(top, sha)  # O(runs) + spawn
        if r is None:  # O(1)
            return None  # O(1)
        more = f" and {r['more']} more" if r["more"] else ""  # O(1)
        return f"tests (full, CI): {r['name']} run {r['id']}{more} green on HEAD {sha[:10]} ({r['url']})"  # O(1)
    except Exception:  # noqa: BLE001 | O(1)
        return None  # O(1)


def history_section(plan, sl_dir):  # O(M + B + n*(n + e))
    """Append the run's rows to history (global and project), refresh stats, and report predicted against actual."""
    sl = Path(sl_dir)  # O(1)
    if plan == "":  # a run without a plan document (#668) | O(1)
        return "history: no plan document (inline run); nothing recorded"  # O(1)
    if not plan or not (sl / "metrics.jsonl").is_file():  # O(1)
        return "history: no metrics.jsonl or plan, nothing recorded"  # O(1)
    sys.path.insert(0, str(Path(__file__).resolve().parent))  # O(1)
    try:  # O(1)
        import history  # O(1)
        rows = history.record_run(plan, sl_dir)  # O(M + B)
    except Exception as e:  # noqa: BLE001 | O(1)
        return f"history: not recorded ({e})"  # O(1)
    out = [f"history: {len(rows)} rows appended"]  # predicted vs actual is the build report's job | O(1)
    try:  # O(1)
        import report  # O(1)
        out += ["", report.report_text(plan, sl_dir).rstrip("\n")]  # O(M + B + n*(n + e))
    except Exception as e:  # noqa: BLE001 | O(1)
        out.append(f"report: not produced ({e})")  # O(1)
    return chr(10).join(out)  # O(n)


def checkpoint_note(ledger):  # O(files) + git spawns; [] unless this run took hidden checkpoints
    """Lines saying nothing was committed and how to commit, when state is in checkpoint mode."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))  # O(1)
    import autocommit  # O(1)
    sl = Path(ledger).resolve().parent  # O(1)
    try:  # O(1)
        st = json.loads((sl / "checkpoints.json").read_text(encoding="utf-8", errors="replace"))  # O(size)
    except (OSError, ValueError):  # O(1)
        return []  # O(1)
    if autocommit.is_on() or not st.get("entries"):  # O(1)
        return []  # O(1)
    files = sorted({f for e in st["entries"] for f in e["files"]})  # O(files)
    return ["", "NOTHING WAS COMMITTED: your branch is untouched and the work is uncommitted in the tree.",  # O(1)
            f"changed files: {len(files)}; hidden checkpoint refs: refs/superlite/{st['run']}/* ({len(st['entries'])})",
            "to commit: `sl autocommit apply` (one commit per task, same titles; add `--trailer \"Key: value\"`, repeatable, for each attribution line your harness requires) or `git add -A && git commit`",
            "to discard the checkpoints: `sl autocommit clean`"]


def _ended(d):  # O(1) a summary's end time (started + seconds); None when it has none
    st, sec = d.get("started"), d.get("seconds")  # O(1)
    if any(isinstance(x, bool) or not isinstance(x, (int, float)) for x in (st, sec)):  # O(1)
        return None  # O(1)
    return st + sec  # O(1)


def _fail_ids(d):  # O(F)
    return {str(x).split(": ", 1)[0] for x in d.get("failures") or []}  # O(F)


def packet_lines(sl_dir):  # O(S*F + F log F)
    """Say so when the review packet predates a full run that changed the test results (#416); [] otherwise."""
    try:  # O(1)
        mtime = (Path(sl_dir) / "review-packet.md").stat().st_mtime  # O(1)
        runs = [(e, d) for d in load_run_summaries(sl_dir) if isinstance(d, dict) and (e := _ended(d)) is not None]  # O(S)
        full = [(e, d) for e, d in runs if d.get("mode") == "full" and not d.get("recorded") and e > mtime]  # O(S)
        if not full:  # O(1)
            return []  # O(1)
        end, last = max(full, key=lambda x: x[0])  # O(S)
        before = [(e, d) for e, d in runs if e <= mtime]  # O(S)
        old = _fail_ids(max(before, key=lambda x: x[0])[1]) if before else set()  # O(S + F)
        new = _fail_ids(last)  # O(F)
        green, red = sorted(old - new), sorted(new - old)  # O(F log F)
        if not green and not red:  # O(1)
            return []  # O(1)
        clock = lambda t: time.strftime("%H:%M:%S", time.localtime(t))  # O(1)
        changes = [f"- green since the packet: {i}" for i in green] + [f"- red since the packet: {i}" for i in red]  # O(F)
        out = [f"review packet: older than the last full run (packet {clock(mtime)}, full run done {clock(end)}: "  # O(1)
               f"{last.get('passed')} passed, {last.get('failed')} failed); rebuild it with `sl plan_tools packet` before trusting its test findings"]
        out += changes[:5]  # O(1)
        if len(changes) > 5:  # O(1)
            out.append(f"- (+{len(changes) - 5} more)")  # O(1)
        return out  # O(1)
    except (OSError, TypeError, ValueError, AttributeError):  # O(1)
        return []  # O(1)


def bulk_close_line(incidents):  # O(I)
    """The `sl incident resolve --kind K` offer with the open kinds and agents, one per (file, line); None for none."""
    last = {(e["file"], e["line"]): e for e in incidents}  # O(I)
    if not last:  # O(1)
        return None  # O(1)
    kinds = Counter(e.get("kind") or "unknown" for e in last.values())  # O(I)
    tools = Counter(t for e in last.values() if (t := e.get("agent") or e.get("tool")))  # O(I)
    parts = ["open by kind: " + ", ".join(f"{k}={n}" for k, n in sorted(kinds.items()))]  # O(k log k)
    if tools:  # O(1)
        parts.append("by agent: " + ", ".join(f"{k}={n}" for k, n in sorted(tools.items())))  # O(t log t)
    return ("- close all of one kind or tool: sl incident resolve --kind K --reason \"TEXT\" "  # O(1)
            f"({'; '.join(parts)})")


def _git_files(top, *args):  # O(files) + spawn: NUL-separated names of a git command, [] on failure
    import worktree  # O(1)
    rc, out, _ = worktree.git(top, *args)  # O(files) + spawn
    return [f for f in out.split("\0") if f] if not rc else []  # O(files)


def moved_lines(sd, plan=None):  # O(files) + git spawns
    """-> WARNING lines for the default branch moving in files the run owns (local ref, then origin/<name>); [] on any failure."""
    try:  # O(1)
        sys.path.insert(0, str(Path(__file__).resolve().parent))  # O(1)
        import worktree  # O(1)
        g = worktree.git  # O(1)
        rc, top, _ = g(Path(sd).resolve().parent, "rev-parse", "--show-toplevel")  # O(1) + spawn
        if rc or not top:  # O(1)
            return []  # O(1)
        head = g(top, "symbolic-ref", "-q", "refs/remotes/origin/HEAD")[1].rsplit("/", 1)[-1]  # O(1) + spawn
        names = [head] if head else []  # O(1)
        names += [n for n in ("main", "master") if n not in names and g(top, "show-ref", "--verify", "-q", f"refs/heads/{n}")[0] == 0 and not head]  # O(1) + spawns
        if not names:  # O(1)
            return []  # O(1)
        name = names[0]  # O(1)
        owned = None  # computed once, only when a ref moved | O(1)
        seen = set()  # O(1)
        out = []  # O(1)
        for label, ref in ((name, f"refs/heads/{name}"), (f"origin/{name}", f"refs/remotes/origin/{name}")):  # O(1)
            rc, sha, _ = g(top, "rev-parse", "--verify", "-q", ref)  # O(1) + spawn
            if rc or not sha or sha in seen:  # O(1)
                continue  # O(1)
            seen.add(sha)  # O(1)
            rc, base, _ = g(top, "merge-base", "HEAD", ref)  # O(1) + spawn
            if rc or not base or base == sha:  # O(1) unrelated, or already merged (the ref is the merge-base)
                continue  # O(1)
            moved = _git_files(top, "diff", "--name-only", "-z", base, ref)  # O(files) + spawn
            if owned is None:  # O(1)
                owned = (worktree._plan_owns(plan) if plan else []) + _git_files(top, "diff", "--name-only", "-z", base, "HEAD") + _git_files(top, "diff", "--name-only", "-z", "HEAD")  # O(files) + spawns
            hits = worktree.overlaps(moved, owned)  # O(files^2)
            if not hits:  # O(1)
                continue  # O(1)
            k = g(top, "rev-list", "--count", f"{base}..{ref}")[1]  # O(1) + spawn
            n, c = len(hits), int(k or 0)  # O(1)
            out.append(f"WARNING: {label} moved in {n} file{'s' if n != 1 else ''} this run owns ({c} commit{'s' if c != 1 else ''} "  # O(1)
                       f"since this branch left it at {base[:10]}): {worktree.shown_list(hits)}; merge {label} into this branch before shipping (finishing skill: conflict step)")
        return out  # O(1)
    except Exception:  # O(1) warn only
        return []  # O(1)


def summary(ledger, log, lint_log=DEFAULT_LINT_LOG, plan=None, sl_dir=None, end_plan=None):  # O(R*w + I*w + C + G)
    rulings, commits, _ = read_ledger(ledger)  # O(R*w)
    incidents = open_incidents(log, load_run_summaries(sl_dir or Path(ledger).parent), ledger)  # O(I*w + I*S*F)
    out = ["# superlite run summary", ""]  # O(1)
    run_sd = Path(ledger).resolve().parent  # O(d)
    inline = None  # (base, commits) of a run with no plan document and no commit line (#668) | O(1)
    if not commits and not plan:  # O(1)
        sys.path.insert(0, str(Path(__file__).resolve().parent))  # O(1)
        import orchestrator  # O(1)
        if plan == "" or orchestrator.plan_file(run_sd) is None:  # O(1)
            inline = inline_commits(run_sd)  # O(C) + spawns
            have = set(rulings)  # O(R)
            rulings = rulings + [r for r in spec_rulings(run_sd) if r not in have]  # O(R)
    cp = checkpoint_note(ledger)  # checkpoint mode: nothing was committed | O(1) + git spawns
    if inline:  # O(1)
        out.append(f"commits: {len(inline[1])} (branch commits since {inline[0][:10]}, inline run)")  # O(1)
        out += [f"- {sha[:10]} {subject}".rstrip() for sha, subject in inline[1]]  # O(C)
    else:  # O(1)
        out.append(f"{'checkpoints' if cp else 'commits'}: {len(commits)}")  # O(1)
        out += [f"- {t} {sha[:10]} {title}".rstrip() for t, sha, title in commits]  # O(C)
    out += cp  # O(1)
    out.append("")  # O(1)
    out.append(f"rulings: {len(rulings)}")  # O(1)
    out += [f"- {r}" for r in rulings]  # O(G)
    out.append("")  # O(1)
    import next_tasks  # lazy | O(1)
    held = {t: r for t, r in next_tasks.held_tasks(ledger).items() if t not in {c[0] for c in commits}}  # O(R + C)
    if held:  # O(1)
        out.append(f"held: {len(held)} (still waiting for a human step)")  # O(1)
        out += [f"- {t}: {r}" for t, r in held.items()]  # O(h)
        out.append("- release one: sl hold --release Tn")  # O(1)
        out.append("")  # O(1)
    res, newer, n_newer = test_result(ledger)  # O(R*w)
    nm = lambda r: f"recorded {r['mode']}" if r["recorded"] else r["mode"]  # O(1)
    fmt = lambda r: f"{r['passed']} passed, {r['failed']} failed, {r['skipped']} skipped in {r['seconds']:.1f}s"  # O(1)
    after = commits_after_full(ledger) if res and res["mode"] == "full" and not res["recorded"] else []  # O(R*w)
    ci = None if res and res["mode"] == "full" and not res["recorded"] and not after else ci_line(run_sd)  # a green CI run of HEAD is the full run (#668) | O(runs) + spawns
    if ci:  # O(1)
        out.append(ci)  # O(1)
        if res:  # O(1)
            out.append(f"- local {nm(res)} run (not the run's result): {fmt(res)}")  # O(1)
    elif res:  # O(1)
        out.append(f"tests ({res['mode']}{', recorded' if res['recorded'] else ''}): {fmt(res)}")  # O(1)
        if newer:  # O(1)
            out.append(f"- newer {nm(newer)} run (not the run's result): {fmt(newer)}" if n_newer == 1
                       else f"- {n_newer} newer {nm(newer)} runs (not the run's result), newest: {fmt(newer)}")  # O(1)
        if after:  # O(1)
            out.append(f"- committed after this full run: {', '.join(after)} (it does not cover them; rerun sl run_tests --full)")  # O(C)
    else:  # O(1)
        out.append("tests: none recorded")  # O(1)
    out += packet_lines(sl_dir or Path(ledger).parent)  # O(S*F)
    out.append("")  # O(1)
    out.append(unblocked_report(ledger, lint_log))  # see unblocked_report
    out.append("")  # O(1)
    sys.path.insert(0, str(Path(__file__).resolve().parent))  # O(1)
    import orchestrator  # O(1)
    out.append(orchestrator.summary_line(Path(ledger).resolve().parent))  # mode, and the approval time in human mode | O(file)
    stops = stops_line(read_stops(log))  # O(I*w)
    if stops:  # O(1)
        out.append(stops)  # O(1)
    out.append("superlite friction this run (broken, slow, unclear, repeated work)? "  # O(1)
               "`sl feedback add \"<what, where, expected>\"` once per finding")
    out.append("")  # O(1)
    cr = Path(ledger).with_name("chain-rulings.json")  # sequential rulings lint accepted, with the minutes they cost | O(1)
    try:  # O(1)
        accepted = json.loads(cr.read_text(encoding="utf-8", errors="replace")) if cr.is_file() else []  # O(size)
    except ValueError:  # O(1)
        accepted = []  # O(1)
    out.append(f"sequential rulings accepted: {len(accepted)}")  # O(1)
    out += [f"- {a}" for a in accepted]  # O(accepted)
    out.append("")  # O(1)
    if plan is not None:  # O(1)
        out.append(history_section(plan, sl_dir or str(Path(ledger).parent)))  # see history_section
        out.append("")  # O(1)
    out.append(f"open incidents: {len(incidents)} ({len(ranked_incidents(incidents))} distinct)")  # O(I + G log G)
    out += group_incidents(incidents)  # O(I + G log G)
    if incidents:  # the close form for one an obsolete or fixed one (#116) | O(1)
        out.append("- close one: sl incident resolve --file F --line N --ruling \"TEXT\" (file and line as listed)")  # O(1)
        out.append(bulk_close_line(incidents))  # O(I)
    try:  # warn only (#493) | O(files) + spawns
        out += moved_lines(Path(ledger).resolve().parent, plan or None)  # O(files) + spawns
    except Exception:  # O(1)
        pass  # O(1)
    try:  # a hint only: finish never fails over it | O(d)
        import state  # O(1)
        sd = Path(ledger).resolve().parent  # O(d)
        other = state.live_owner(sd)  # O(d)
        if other:  # O(1)
            out.append(f"this run belongs to session {other}: run `sl orchestrator takeover --plan {sd}` before `sl orchestrator end`")  # O(1)
    except Exception:  # O(1)
        pass  # O(1)
    end_plan = plan if end_plan is None else end_plan  # O(1)
    out.append(f"next: sl orchestrator end{' --plan ' + end_plan if end_plan else ''}" + END_TAIL)  # the last line (#497) | O(1)
    return "\n".join(out) + "\n"  # O(R + C + G + I) join


def drop_trees(sd):  # best effort: drop the run's idle test trees and orphaned DerivedData, one stderr line (#614) | O(T + folders)
    try:  # O(1)
        if Path(sd).name != ".superlite":  # O(1)
            return  # O(1)
        import trees  # O(1)
        dropped = trees.clean_idle(Path(sd).parent)  # O(T)
        n, freed = trees.sweep_derived_data()  # O(folders + files)
        if dropped or n:  # O(1)
            print(f"finish: removed {len(dropped)} test tree(s) and {n} orphaned DerivedData folder(s), {freed / 1024 ** 3:.1f} GB", file=sys.stderr)  # O(1)
    except Exception:  # cleanup never changes the exit code or stdout | O(1)
        pass  # O(1)


def open_render_edits(sd):  # O(a) the root-relative files of `.superlite/render-edits.json` still applied (#547); [] when none or unreadable
    try:  # O(1)
        files = json.loads((Path(sd) / "render-edits.json").read_text(encoding="utf-8")).get("files")  # O(file)
    except (OSError, ValueError, AttributeError):  # O(1)
        return []  # O(1)
    return sorted(files) if isinstance(files, dict) else []  # O(a log a)


def main(argv=None):  # O(R*w + I*w)
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])  # O(1)
    sys.path.insert(0, str(Path(__file__).resolve().parent))  # O(1)
    import state  # O(1)
    ap.add_argument("--ledger", help="default: progress.md in the run folder (--plan's own, else the session's run)")  # O(1)
    ap.add_argument("--log", help="default: incidents.jsonl in the run folder")  # O(1)
    ap.add_argument("--plan", help="record this run into history (needs .superlite/metrics.jsonl); its run folder is the default")  # O(1)
    ap.add_argument("--lint-log", help="default: lint-log.jsonl next to the ledger")  # O(1)
    a = ap.parse_args(argv)  # O(1)
    sd = state.for_plan(a.plan) if a.plan else state.resolve()  # the defaults follow --plan once its run started (#178) | O(d)
    ledger, log = a.ledger or str(sd / "progress.md"), a.log or str(sd / "incidents.jsonl")  # O(1)
    sys.stdout.reconfigure(encoding="utf-8")  # O(1)
    open_edits = open_render_edits(Path(ledger).parent)  # the ledger sits in the run folder (#547) | O(a log a)
    if open_edits:  # O(1)
        print(f"BLOCKED: render edits still applied: {', '.join(open_edits)}; run sl render_edit restore first")  # O(a)
        return 2  # O(1)
    plan = a.plan  # O(1)
    import orchestrator  # O(1)
    if plan and Path(plan).is_dir():  # a run folder: its plan file, "" when it has none (an inline run, #668) | O(d)
        found = orchestrator.plan_file(state.plan_dir(plan))  # O(d + file)
        plan = str(found) if found else ""  # O(1)
    elif not plan and orchestrator.plan_file(sd) is None:  # O(d)
        plan = ""  # O(1)
    sys.stdout.write(summary(ledger, log, a.lint_log or str(Path(ledger).with_name("lint-log.jsonl")), plan, end_plan=a.plan or ""))  # O(output)
    log_auto(read_stops(log), str(Path(log).resolve()))  # after the summary: a feedback failure never costs the closing text (#140) | O(I*w)
    drop_trees(sd)  # the run's trees are not needed after the summary (#614) | O(T + folders)
    return 0  # O(1)


if __name__ == "__main__":  # O(1)
    sys.exit(main())  # O(1)
