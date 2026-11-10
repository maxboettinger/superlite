"""`sl incident resolve --kind K --reason R` closes every open incident of one kind or tool in one call (#416)."""
import json
from pathlib import Path

from test_plan_tools import SCRIPTS, run

INCIDENT = SCRIPTS / "incident.py"
FINISH = SCRIPTS / "finish.py"


def add(log, file, line, kind="exception", context="boom", agent=None):
    args = ["add", "--file", file, "--line", line, "--kind", kind, "--context", context, "--log", log]
    if agent:
        args += ["--agent", agent]
    cp = run(INCIDENT, *args)
    assert cp.returncode == 0, cp.both


def entries(log):
    return [json.loads(x) for x in Path(log).read_text(encoding="utf-8").splitlines()]


def resolve(log, *args):
    return run(INCIDENT, "resolve", *args, "--log", log)


def open_count(tmp_path, log):
    cp = run(FINISH, "--ledger", tmp_path / "progress.md", "--log", log, cwd=tmp_path)
    assert cp.returncode == 0, cp.both
    return next(line for line in cp.out.splitlines() if line.startswith("open incidents: "))


def test_kind_closes_every_open_incident_of_that_kind(tmp_path):
    log = tmp_path / "i.jsonl"
    add(log, "src/a.py", 1, kind="unsure")
    add(log, "src/b.py", 2, kind="unsure")
    add(log, "src/c.py", 3, kind="exception")
    cp = resolve(log, "--kind", "unsure", "--reason", "tool artifact")
    assert cp.returncode == 0, cp.both
    assert cp.out.splitlines() == ["resolved src/a.py:1", "resolved src/b.py:2", "closed 2 of kind unsure (resolved)"]
    new = entries(log)[3:]
    assert [(e["file"], e["line"], e["kind"], e["resolution"], e["context"]) for e in new] == [
        ("src/a.py", 1, "unsure", "resolved", "resolved: tool artifact"),
        ("src/b.py", 2, "unsure", "resolved", "resolved: tool artifact")]
    assert open_count(tmp_path, log) == "open incidents: 1 (1 distinct)"


def test_probe_and_contract_name_the_tool_that_logged_them(tmp_path):
    log = tmp_path / "i.jsonl"
    add(log, "src/x.py", 5, kind="exception", agent="probe_run")
    add(log, "src/y.py", 6, kind="perf", agent="probe_run")
    add(log, "src/z.py", 7, kind="exception", agent="pt_review")
    add(log, "src/w.py", 8, kind="exception", agent="implementer")
    cp = resolve(log, "--kind", "probe", "--reason", "probe false positive")
    assert cp.returncode == 0, cp.both
    assert cp.out.splitlines() == ["resolved src/x.py:5", "resolved src/y.py:6", "closed 2 of kind probe (resolved)"]
    cp = resolve(log, "--kind", "contract", "--reason", "contract-check artifact", "--resolution", "wontfix")
    assert cp.returncode == 0, cp.both
    assert cp.out.splitlines() == ["wontfix src/z.py:7", "closed 1 of kind contract (wontfix)"]
    assert open_count(tmp_path, log) == "open incidents: 1 (1 distinct)"


def test_an_agent_name_works_as_the_kind(tmp_path):
    log = tmp_path / "i.jsonl"
    add(log, "src/x.py", 5, kind="exception", agent="probe_run")
    add(log, "src/w.py", 8, kind="exception", agent="implementer")
    cp = resolve(log, "--kind", "probe_run", "--ruling", "artifact")
    assert cp.returncode == 0, cp.both
    assert cp.out.splitlines() == ["resolved src/x.py:5", "closed 1 of kind probe_run (resolved)"]


def test_kind_unknown_closes_a_kindless_agentless_incident(tmp_path):
    log = tmp_path / "i.jsonl"
    log.write_text(json.dumps({"file": "src/k.py", "line": 4, "context": "no kind"}) + "\n", encoding="utf-8")
    cp = resolve(log, "--kind", "unknown", "--ruling", "artifact")
    assert cp.returncode == 0, cp.both
    assert cp.out.splitlines() == ["resolved src/k.py:4", "closed 1 of kind unknown (resolved)"]


def test_a_location_with_several_entries_is_closed_once(tmp_path):
    log = tmp_path / "i.jsonl"
    add(log, "src/a.py", 1, kind="unsure", context="first")
    add(log, "src/a.py", 1, kind="unsure", context="again")
    cp = resolve(log, "--kind", "unsure", "--reason", "r")
    assert cp.returncode == 0, cp.both
    assert cp.out.splitlines() == ["resolved src/a.py:1", "closed 1 of kind unsure (resolved)"]
    assert len(entries(log)) == 3


def test_a_resolved_location_is_not_closed_again(tmp_path):
    log = tmp_path / "i.jsonl"
    add(log, "src/a.py", 1, kind="unsure")
    assert resolve(log, "--file", "src/a.py", "--line", "1", "--ruling", "done").returncode == 0
    cp = resolve(log, "--kind", "unsure", "--reason", "r")
    assert cp.returncode == 2
    assert "no open incident of kind unsure; none is open" in cp.err
    assert len(entries(log)) == 2


def test_no_match_names_the_open_kinds_and_agents(tmp_path):
    log = tmp_path / "i.jsonl"
    add(log, "src/x.py", 5, kind="exception", agent="probe_run")
    add(log, "src/y.py", 6, kind="perf", agent="probe_run")
    add(log, "src/z.py", 7, kind="exception")
    cp = resolve(log, "--kind", "flaky", "--reason", "r")
    assert cp.returncode == 2
    assert "no open incident of kind flaky; open by kind: exception=2, perf=1; by agent: probe_run=2" in cp.err
    assert len(entries(log)) == 3


def test_kind_with_file_or_line_is_refused(tmp_path):
    log = tmp_path / "i.jsonl"
    add(log, "src/a.py", 1, kind="unsure")
    for extra in (["--file", "src/a.py"], ["--line", "1"], ["--file", "src/a.py", "--line", "1"]):
        cp = resolve(log, "--kind", "unsure", "--reason", "r", *extra)
        assert cp.returncode == 2 and "give --file F --line N, or --kind K, not both" in cp.err
    assert len(entries(log)) == 1


def test_neither_location_nor_kind_is_refused(tmp_path):
    log = tmp_path / "i.jsonl"
    add(log, "src/a.py", 1, kind="unsure")
    for extra in ([], ["--file", "src/a.py"], ["--line", "1"]):
        cp = resolve(log, "--reason", "r", *extra)
        assert cp.returncode == 2 and "give --file F --line N, or --kind K" in cp.err
    assert len(entries(log)) == 1


def test_a_ruling_is_required_and_reason_is_its_alias(tmp_path):
    log = tmp_path / "i.jsonl"
    add(log, "src/a.py", 1, kind="unsure")
    cp = resolve(log, "--file", "src/a.py", "--line", "1")
    assert cp.returncode == 2 and "give the ruling: --ruling TEXT (or --reason TEXT)" in cp.err
    cp = resolve(log, "--file", "src/a.py", "--line", "1", "--reason", "obsolete")
    assert cp.returncode == 0, cp.both
    assert cp.out.strip() == "resolved src/a.py:1"
    assert entries(log)[-1]["context"] == "resolved: obsolete"


def test_help_names_the_kind_form():
    cp = run(INCIDENT, "resolve", "--help")
    assert "--kind" in cp.out and "--reason" in cp.out and "probe" in cp.out and "contract" in cp.out
