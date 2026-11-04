"""`sl incident resolve` closes an open incident with a ruling (#116), `--kind` lists its choices, and the
package-reviewer brief names the accepted kinds and the resolve form (#85)."""
import json
import sys
from pathlib import Path

from test_plan_tools import SCRIPTS, run

sys.path.insert(0, str(SCRIPTS))
import incident  # noqa: E402

INCIDENT = SCRIPTS / "incident.py"
FINISH = SCRIPTS / "finish.py"
BRIEF = SCRIPTS.parents[2] / "agents" / "package-reviewer.md"


def add(log, file, line, kind="unsure", context="seam guess", **extra):
    args = ["add", "--file", file, "--line", line, "--kind", kind, "--context", context, "--log", log]
    for k, v in extra.items():
        args += [f"--{k}", v]
    return run(INCIDENT, *args)


def entries(log):
    return [json.loads(x) for x in Path(log).read_text(encoding="utf-8").splitlines()]


def open_lines(tmp_path, log):
    cp = run(FINISH, "--ledger", tmp_path / "progress.md", "--log", log, cwd=tmp_path)
    assert cp.returncode == 0, cp.both
    return cp.out


def test_an_unknown_kind_is_refused_and_help_lists_the_kinds(tmp_path):
    cp = add(tmp_path / "i.jsonl", "a.py", 1, kind="bug")
    assert cp.returncode == 2 and "verified" in cp.err and "workaround" in cp.err
    shown = run(INCIDENT, "add", "--help")
    assert all(k in shown.out for k in incident.KINDS), shown.out


def test_resolve_closes_the_open_incident_with_the_ruling(tmp_path):
    log = tmp_path / "i.jsonl"
    assert add(log, "src/model.swift", 42, kind="spec-ambiguity", context="Produces type unclear").returncode == 0
    assert "src/model.swift:42" in open_lines(tmp_path, log)
    cp = run(INCIDENT, "resolve", "--file", "src/model.swift", "--line", "42", "--ruling", "type renamed by review ruling",
             "--log", log)
    assert cp.returncode == 0, cp.both
    last = entries(log)[-1]
    assert (last["file"], last["line"], last["kind"], last["resolution"]) == ("src/model.swift", 42, "spec-ambiguity", "resolved")
    assert "type renamed by review ruling" in last["context"]
    assert "src/model.swift:42" not in open_lines(tmp_path, log)


def test_resolve_takes_a_windows_path_and_keeps_the_logged_spelling(tmp_path):
    log = tmp_path / "i.jsonl"
    add(log, "src/a.py", 3)
    cp = run(INCIDENT, "resolve", "--file", "src\\a.py", "--line", "3", "--ruling", "obsolete", "--resolution", "wontfix",
             "--log", log)
    assert cp.returncode == 0, cp.both
    assert (entries(log)[-1]["file"], entries(log)[-1]["resolution"]) == ("src/a.py", "wontfix")


def test_resolve_without_an_incident_there_names_the_open_ones(tmp_path):
    log = tmp_path / "i.jsonl"
    add(log, "src/a.py", 3)
    cp = run(INCIDENT, "resolve", "--file", "src/a.py", "--line", "4", "--ruling", "x", "--log", log)
    assert cp.returncode == 2 and "src/a.py:4" in cp.err and "src/a.py:3" in cp.err, cp.err
    assert len(entries(log)) == 1


def test_the_open_list_uses_the_newest_entry_per_location(tmp_path):
    """Final review: open means the location's newest non-verified entry is not resolved, as the packet and finish count."""
    log = tmp_path / "i.jsonl"
    add(log, "src/a.py", 3, resolution="open")
    add(log, "src/a.py", 3, resolution="fixed")  # closed later: not open
    add(log, "src/b.py", 7, resolution="partial")  # not a resolved value: open
    cp = run(INCIDENT, "resolve", "--file", "src/c.py", "--line", "1", "--ruling", "x", "--log", log)
    assert cp.returncode == 2 and "src/b.py:7" in cp.err and "src/a.py:3" not in cp.err, cp.err


def test_a_location_with_only_verified_entries_is_not_resolved(tmp_path):
    """Final review: a `verified` entry is no incident, so resolve exits 2 and the log stays as it was."""
    log = tmp_path / "i.jsonl"
    add(log, "src/a.py", 3, kind="verified", context="checked")
    cp = run(INCIDENT, "resolve", "--file", "src/a.py", "--line", "3", "--ruling", "x", "--log", log)
    assert cp.returncode == 2, cp.both
    assert len(entries(log)) == 1


def test_finish_says_how_to_close_an_open_incident(tmp_path):
    log = tmp_path / "i.jsonl"
    add(log, "src/a.py", 3)
    assert "incident resolve --file F --line N --ruling" in open_lines(tmp_path, log)


def test_the_package_reviewer_brief_names_the_kinds_and_resolve():
    text = BRIEF.read_text(encoding="utf-8")
    missing = [k for k in incident.KINDS if f"`{k}`" not in text and f"--kind {k}`" not in text]
    assert not missing, missing
    assert "incident resolve" in text
