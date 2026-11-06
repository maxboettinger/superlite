#!/usr/bin/env python3
"""Print the closing summary of a run.

    finish.py [--plan PLAN] [--ledger .superlite/progress.md] [--log .superlite/incidents.jsonl]

Collects, from the progress ledger, every `Ruling:` line (in order), the
commits and the last test counts, plus the open incidents from the log. Open means what the
review packet counts: a location whose newest entry is resolved, and a test-failure the newest
covering test summary shows green (a later full run covers every run_tests failure), are not open.
Ledger and log default to the run folder of `--plan` once it holds a run (else the session's run, #178). The
superlite-side stops of the run (guard blocks and rewrites, guard errors, test runs with no result, commit scope
blocks) print as one line, `superlite stops this run: N kind (tool), ...`, and each is also logged as an `auto`
feedback entry (`feedback.add_auto`; a failure to write feedback never fails finish, #140).
A task held by `sl hold` (and not committed) is listed with its reason.
Deterministic: the same files give the same text. Stdlib only.
"""
# Complexity notation:
#   R = lines in the progress ledger, I = lines in the incident log, C = commits and G = rulings found,
#   w = width of one line, F = failures listed in the newest test summary
import argparse  # O(1)
import json  # O(1)
from datetime import datetime, timedelta  # O(1)
import re  # O(1)
import sys  # O(1)
from pathlib import Path  # O(1)

DEFAULT_LEDGER = ".superlite/progress.md"  # O(1)
DEFAULT_LOG = ".superlite/incidents.jsonl"  # O(1)
DEFAULT_LINT_LOG = ".superlite/lint-log.jsonl"  # O(1)
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


def open_incidents(path, summary=None):  # O(I*w + I*F)
    """Open incidents as the review packet counts them: a location whose newest entry is resolved is not open,
    and (with a test summary) neither is a test-failure the newest run shows green."""
    pt = _pt_review()  # O(1)
    if pt is None:  # O(1)
        return _logged_open(path)  # O(I*w)
    entries = pt.read_incidents(Path(path))  # O(I) every parsed entry, resolved ones included
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
        file = str(e.get("file") or "")  # O(1)
        target = str(e.get("target") or ("" if file in ("", "-") else file))  # O(1)
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


def unblocked_report(ledger, lint_log):  # O(R*w + L*n)
    """One line: were all stable tasks dispatched before the next patch, and the largest stable-to-dispatch lag."""
    lp = Path(lint_log)  # O(1)
    if not lp.exists():  # O(1)
        return "unblocked: no lint log recorded"  # O(1)
    runs = []  # O(1)
    for ln in lp.read_text(encoding="utf-8", errors="replace").splitlines():  # O(L) iterations
        try:  # O(1)
            e = json.loads(ln)  # O(w)
            runs.append((datetime.fromisoformat(e["time"]), e))  # O(1)
        except (ValueError, KeyError, TypeError):  # O(1)
            continue  # O(1)
    if not runs:  # O(1)
        return "unblocked: no lint log recorded"  # O(1)
    sent = []  # (task, clock text) per `unblocked:` line | O(1)
    ledger_p = Path(ledger)  # O(1)
    for line in (ledger_p.read_text(encoding="utf-8", errors="replace").splitlines() if ledger_p.exists() else []):  # O(R)
        m = UNBLOCKED.match(line)  # O(w)
        if m:  # O(1)
            sent += [(t, m.group(2)) for t in m.group(1).split()]  # O(tasks)
    first_stable = {}  # task -> time it first became stable | O(1)
    for when, e in runs:  # O(L)
        for t in e.get("newly_stable") or []:  # O(n)
            first_stable.setdefault(t, when)  # O(1)
    sent_at = {}  # O(1)
    for t, clock in sent:  # O(tasks)
        if t in sent_at or t not in first_stable:  # O(1)
            continue  # O(1)
        base = first_stable[t]  # O(1)
        at = datetime.combine(base.date(), datetime.strptime(clock, "%H:%M:%S").time())  # O(1)
        sent_at[t] = at + timedelta(days=1) if at < base - timedelta(seconds=1) else at  # O(1)
    held = sorted({t for (_, a), (_, b) in zip(runs, runs[1:])  # stable at one lint, still pending at the next | O(L*n)
                   for t in set(a.get("pending") or []) & set(b.get("pending") or [])})
    lags = [(sent_at[t] - first_stable[t]).total_seconds() for t in sent_at]  # O(tasks)
    missing = sorted(t for t in first_stable if t not in sent_at and t in set(runs[-1][1].get("pending") or []))  # O(n)
    worst = f"max lag {max(0, max(lags)):.0f}s" if lags else "max lag n/a (no `unblocked:` lines)"  # O(1)
    if held:  # O(1)
        return f"unblocked: NO - {' '.join(held)} still waiting at the next lint; {worst}"  # O(1)
    if missing:  # O(1)
        return f"unblocked: NO - never dispatched: {' '.join(missing)}; {worst}"  # O(1)
    return f"unblocked: yes - every stable task was dispatched before the next patch; {worst}"  # O(1)


def history_section(plan, sl_dir):  # O(M + B + n*(n + e))
    """Append the run's rows to history (global and project), refresh stats, and report predicted against actual."""
    sl = Path(sl_dir)  # O(1)
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
            "to commit: `sl autocommit apply` (one commit per task, same titles, no trailer) or `git add -A && git commit`",
            "to discard the checkpoints: `sl autocommit clean`"]


def summary(ledger, log, lint_log=DEFAULT_LINT_LOG, plan=None, sl_dir=None):  # O(R*w + I*w + C + G)
    rulings, commits, tests = read_ledger(ledger)  # O(R*w)
    incidents = open_incidents(log, load_run_summaries(sl_dir or Path(ledger).parent))  # O(I*w + I*S*F)
    out = ["# superlite run summary", ""]  # O(1)
    cp = checkpoint_note(ledger)  # checkpoint mode: nothing was committed | O(1) + git spawns
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
    if tests:  # O(1)
        mode, p, f, s, sec, rec = tests  # O(1)
        mode = f"{mode}, recorded" if rec else mode  # O(1)
        out.append(f"tests ({mode}): {p} passed, {f} failed, {s} skipped in {sec}s")  # O(1)
    else:  # O(1)
        out.append("tests: none recorded")  # O(1)
    out.append("")  # O(1)
    out.append(unblocked_report(ledger, lint_log))  # see unblocked_report
    out.append("")  # O(1)
    sys.path.insert(0, str(Path(__file__).resolve().parent))  # O(1)
    import orchestrator  # O(1)
    out.append(orchestrator.summary_line(Path(ledger).resolve().parent))  # mode, and the approval time in human mode | O(file)
    out.append("after finishing: `sl orchestrator end` archives the run markers (the coordinator guard stops)")  # O(1)
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
        out.append(history_section(plan or None, sl_dir or str(Path(ledger).parent)))  # see history_section
        out.append("")  # O(1)
    out.append(f"open incidents: {len(incidents)} ({len(ranked_incidents(incidents))} distinct)")  # O(I + G log G)
    out += group_incidents(incidents)  # O(I + G log G)
    if incidents:  # the close form for one an obsolete or fixed one (#116) | O(1)
        out.append("- close one: sl incident resolve --file F --line N --ruling \"TEXT\" (file and line as listed)")  # O(1)
    return "\n".join(out) + "\n"  # O(R + C + G + I) join


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
    sys.stdout.write(summary(ledger, log, a.lint_log or str(Path(ledger).with_name("lint-log.jsonl")), a.plan))  # O(output)
    log_auto(read_stops(log), str(Path(log).resolve()))  # after the summary: a feedback failure never costs the closing text (#140) | O(I*w)
    return 0  # O(1)


if __name__ == "__main__":  # O(1)
    sys.exit(main())  # O(1)
