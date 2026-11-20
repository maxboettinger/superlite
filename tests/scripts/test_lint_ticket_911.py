"""#911: lint warns on mixed per-task tracker keys and on commit template fields a task leaves unset."""
import json
import os
import subprocess
import sys

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import plan_tools as ptm  # noqa: E402

PLAN_TOOLS = SCRIPTS / "plan_tools.py"
TAIL = " have no **Ticket:** while T1, T3 have one and the plan header has none; give each task its key, or put one **Ticket:** in the plan header"


def make(base, header="", tasks=None, name="plan.md"):
    """tasks: list of (id, extra field lines, status)."""
    text = f"# Plan\n**Goal:** x.\n{header}\n"
    for i, (tid, extra, status) in enumerate(tasks):
        text += f"\n### {tid} thing{i} · Complexity 2 · Est. context 30k\n**Owns:** src/{tid.lower()}.py\n"
        if status:
            text += f"**Status:** {status}\n"
        for line in extra:
            text += line + "\n"
    p = base / name
    p.write_text(text, encoding="utf-8")
    return p


def warns(base, header, tasks, root=None):
    p = make(base, header, tasks)
    return ptm.subject_warnings(ptm.Plan.load(str(p)), root)


def mixed():
    return [("T1", ["**Ticket:** A-1"], None), ("T2", [], None), ("T3", ["**Ticket:** A-3"], None), ("T4", [], None)]


def test_mixed_keys_warn(tmp_path):
    assert warns(tmp_path, "", mixed()) == ["WARNING: TICKET: T2, T4" + TAIL]


def test_one_id_singular(tmp_path):
    out = warns(tmp_path, "", [("T1", ["**Ticket:** A-1"], None), ("T2", [], None)])
    assert out == ["WARNING: TICKET: T2 has no **Ticket:** while T1 has one and the plan header has none; "
                   "give each task its key, or put one **Ticket:** in the plan header"]


def test_header_key_quiet(tmp_path):
    assert warns(tmp_path, "**Ticket:** A-0", mixed()) == []


def test_all_or_none_quiet(tmp_path):
    keyed = [(f"T{i}", [f"**Ticket:** A-{i}"], None) for i in (1, 2, 3)]
    bare = [(f"T{i}", [], None) for i in (1, 2, 3)]
    assert warns(tmp_path, "", keyed) == []
    assert warns(tmp_path, "", bare) == []


def test_draft_ignored(tmp_path):
    tasks = [("T1", ["**Ticket:** A-1"], None), ("T2", ["**Ticket:** A-2"], None), ("T3", [], "draft")]
    assert warns(tmp_path, "", tasks) == []


def test_list_cut_at_five(tmp_path):
    tasks = [("T1", ["**Ticket:** A-1"], None)] + [(f"T{i}", [], None) for i in range(2, 9)]
    out = warns(tmp_path, "", tasks)
    assert len(out) == 1
    assert out[0].startswith("WARNING: TICKET: T2, T3, T4, T5, T6 +2 more have no **Ticket:**")


COMMIT = "**Ticket:** A-0\n**Commit:** `{type}({scope}): {ticket} {title}`"


def scoped(*missing):
    tasks = [("T1", ["**Type:** feat", "**Scope:** a"], None)]
    for tid in missing:
        tasks.append((tid, ["**Type:** fix"], None))
    return tasks


def test_commit_field_missing_warns(tmp_path):
    assert warns(tmp_path, COMMIT, scoped("T2")) == [
        "WARNING: COMMIT: T2 has no **Scope:** for {scope} in the commit subject template; "
        "its subject leaves it out (set it on the task or in the plan header)"]
    assert warns(tmp_path, COMMIT, scoped("T2", "T3")) == [
        "WARNING: COMMIT: T2, T3 have no **Scope:** for {scope} in the commit subject template; "
        "their subjects leave it out (set it on the task or in the plan header)"]


def test_header_field_quiet(tmp_path):
    assert warns(tmp_path, COMMIT + "\n**Scope:** core", scoped("T2")) == []


def test_default_template_quiet(tmp_path):
    tasks = [(f"T{i}", [f"**Ticket:** A-{i}"], None) for i in (1, 2)]
    assert warns(tmp_path, "", tasks) == []


def test_testcmd_template_read(tmp_path):
    (tmp_path / ".superlite").mkdir()
    (tmp_path / ".superlite" / "test-cmd.json").write_text(
        json.dumps({"test": "pytest", "commit_subject": "{type}: {title}"}), encoding="utf-8")
    out = warns(tmp_path, "", [("T1", [], None)], root=tmp_path)
    assert len(out) == 1
    assert out[0].startswith("WARNING: COMMIT: T1 has no **Type:** for {type}")


def test_lint_prints_both(tmp_path):
    tasks = [("T1", ["**Ticket:** A-1", "**Type:** feat", "**Scope:** a"], None), ("T2", ["**Type:** fix"], None)]
    p = make(tmp_path, "**Commit:** `{type}({scope}): {ticket} {title}`", tasks)
    env = dict(os.environ, PYTHONIOENCODING="utf-8", SUPERLITE_HOME=str(tmp_path / "home"))
    out = subprocess.run([sys.executable, str(PLAN_TOOLS), "lint", "--plan", str(p)], capture_output=True, text=True,
                         cwd=tmp_path, env=env, timeout=120).stdout
    assert "WARNING: TICKET: T2 has no **Ticket:** while T1 has one" in out
    assert "WARNING: COMMIT: T2 has no **Scope:** for {scope}" in out
