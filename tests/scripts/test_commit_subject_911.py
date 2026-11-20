"""Commit subjects: per-task tickets, subject templates, apply rebuilding subjects (#911)."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from test_commit_also import OFF, commit  # noqa: E402
from test_run_scripts import ENV, SCRIPTS, git, make_repo, run, write  # noqa: E402

sys.path.insert(0, str(SCRIPTS))
import autocommit  # noqa: E402


def plan(tmp_path, head, *blocks):
    p = tmp_path / "plan.md"
    p.write_text(f"# P\n\n{head}\n\n## Tasks\n\n" + "\n".join(blocks), encoding="utf-8")
    return str(p)


def test_default_subject_unchanged(tmp_path):
    p = plan(tmp_path, "**Ticket:** PIX-9", "### T2 tag counts\n**Owns:** `a`\n")
    assert autocommit.subject("T2", "tag counts", p) == "PIX-9 T2: tag counts"
    assert autocommit.message("T2", "tag counts", p) == "PIX-9 T2: tag counts"
    q = plan(tmp_path, "", "### T2 tag counts\n**Owns:** `a`\n")
    assert autocommit.subject("T2", "tag counts", q) == "T2: tag counts"
    assert autocommit.message("T2", "tag counts", q) == "T2: tag counts"
    assert autocommit.subject("T2", "tag counts", None) == "T2: tag counts"
    assert autocommit.message("T2", "tag counts", None) == "T2: tag counts"


def test_missing_plan_default(tmp_path, capsys):
    assert autocommit.subject("T2", "tag counts", str(tmp_path / "none.md")) == "T2: tag counts"
    assert capsys.readouterr().err == ""


def test_task_ticket_wins(tmp_path):
    p = plan(tmp_path, "**Ticket:** PIX-9", "### T1 parser\n**Ticket:** PIX-11\n**Owns:** `a`\n",
             "### T2 cli\n**Owns:** `b`\n")
    assert autocommit.subject("T1", "parser", p) == "PIX-11 T1: parser"
    assert autocommit.subject("T2", "cli", p) == "PIX-9 T2: cli"
    assert autocommit.ticket(p) == "PIX-9"


def test_fenced_ticket_ignored(tmp_path):
    p = plan(tmp_path, "", "### T1 parser\n**Owns:** `a`\n```\n**Ticket:** FENCE-1\n```\n")
    assert autocommit.subject("T1", "parser", p) == "T1: parser"


HEAD_TPL = "**Commit:** `{type}({scope}): {ticket} {title}`"


def test_header_template(tmp_path):
    p = plan(tmp_path, HEAD_TPL, "### T1 parser\n**Type:** feat\n**Scope:** parser\n**Ticket:** PIX-11\n**Owns:** `a`\n")
    assert autocommit.subject("T1", "parser", p) == "feat(parser): PIX-11 parser"


def test_template_missing_scope_drops_parens(tmp_path):
    p = plan(tmp_path, HEAD_TPL, "### T1 parser\n**Type:** fix\n**Ticket:** PIX-12\n**Owns:** `a`\n")
    assert autocommit.subject("T1", "parser", p) == "fix: PIX-12 parser"
    q = plan(tmp_path, HEAD_TPL, "### T1 parser\n**Type:** feat\n**Scope:** a\n**Owns:** `a`\n")
    assert autocommit.subject("T1", "parser", q) == "feat(a): parser"


def test_header_field_fallback(tmp_path):
    head = HEAD_TPL + "\n**Type:** feat\n**Scope:** core"
    p = plan(tmp_path, head, "### T1 parser\n**Ticket:** PIX-1\n**Owns:** `a`\n")
    assert autocommit.subject("T1", "parser", p) == "feat(core): PIX-1 parser"
    q = plan(tmp_path, head, "### T1 parser\n**Type:** fix\n**Ticket:** PIX-1\n**Owns:** `a`\n")
    assert autocommit.subject("T1", "parser", q) == "fix(core): PIX-1 parser"


def test_names_case_insensitive(tmp_path):
    p = plan(tmp_path, "**Commit:** `{Type}: {TITLE}`", "### T1 parser\n**type:** docs\n**Owns:** `a`\n")
    assert autocommit.subject("T1", "parser", p) == "docs: parser"


def test_empty_render_falls_back(tmp_path):
    p = plan(tmp_path, "**Commit:** `{type}`", "### T1 parser\n**Owns:** `a`\n")
    assert autocommit.subject("T1", "parser", p) == "T1: parser"


def test_testcmd_template(tmp_path, capsys):
    cfg = tmp_path / ".superlite"
    cfg.mkdir()
    (cfg / "test-cmd.json").write_text(json.dumps({"test": "pytest", "commit_subject": "{ticket}: {title}"}))
    p = plan(tmp_path, "**Ticket:** PIX-9", "### T1 parser\n**Owns:** `a`\n")
    assert autocommit.subject("T1", "parser", p, root=str(tmp_path)) == "PIX-9: parser"
    p2 = tmp_path / "plan2.md"
    p2.write_text("# P\n\n**Ticket:** PIX-9\n**Commit:** {tid} {title}\n\n## Tasks\n\n### T1 parser\n**Owns:** `a`\n", encoding="utf-8")
    assert autocommit.subject("T1", "parser", str(p2), root=str(tmp_path)) == "T1 parser"
    (cfg / "test-cmd.json").write_text(json.dumps({"test": "pytest", "commit_subject": 5}))
    assert autocommit.subject("T1", "parser", p, root=str(tmp_path)) == "PIX-9 T1: parser"
    (cfg / "test-cmd.json").write_text("{not json")
    assert autocommit.subject("T1", "parser", p, root=str(tmp_path)) == "PIX-9 T1: parser"
    assert capsys.readouterr().err == ""


def test_template_fields():
    assert autocommit.template_fields("{type}({scope}): {ticket} {title} {Type}") == ["type", "scope", "ticket", "title"]


def test_field_values(tmp_path):
    p = plan(tmp_path, "**Ticket:** PIX-9", "### T1 parser\n**Scope:** core\n**Owns:** `a`\n",
             "### T2 cli\n**Owns:** `b`\n")
    assert autocommit.field_values(p, ["ticket", "scope"]) == (
        {"ticket": "PIX-9"}, {"T1": {"title": "parser", "scope": "core"}, "T2": {"title": "cli"}})
    assert autocommit.field_values(None, ["ticket"]) == ({}, {})


def test_entry_subjects_keeps_unknown(tmp_path):
    p = plan(tmp_path, "**Ticket:** PIX-9", "### T1 parser\n**Owns:** `a`\n")
    entries = [{"task": "T1", "title": "T1: old", "files": []}, {"task": "T0", "title": "T0: skeleton", "files": []}]
    assert autocommit.entry_subjects(entries, p) == ["PIX-9 T1: parser", "T0: skeleton"]
    entries.append({"title": "x", "files": []})
    assert autocommit.entry_subjects(entries, p) == ["PIX-9 T1: parser", "T0: skeleton", "x"]
    assert autocommit.entry_subjects(entries, None) == ["T1: old", "T0: skeleton", "x"]


def add_ticket(repo, key):
    p = repo / "plan.md"
    p.write_text(p.read_text(encoding="utf-8").replace("### T1 · parser · Complexity 3 · Est. context 20k · Est. time 1 min\n",
                                                        f"### T1 · parser · Complexity 3 · Est. context 20k · Est. time 1 min\n**Ticket:** {key}\n", 1),
                 encoding="utf-8")


def test_commit_task_uses_task_ticket(tmp_path):
    repo = make_repo(tmp_path)
    add_ticket(repo, "PIX-5")
    write(repo, "src/a.py", "A = 1\n")
    r = commit(repo, "T1", env=OFF)
    assert r.returncode == 0, r.stdout + r.stderr
    sha = r.stdout.strip()
    assert git(repo, "log", "-1", "--format=%s", sha) == "PIX-5 T1: parser"
    st = json.loads((repo / ".superlite" / "checkpoints.json").read_text(encoding="utf-8"))
    assert st["entries"][0]["title"] == "PIX-5 T1: parser"


def test_commit_task_autocommit_uses_task_ticket(tmp_path):
    repo = make_repo(tmp_path)
    add_ticket(repo, "PIX-5")
    write(repo, "src/a.py", "A = 1\n")
    r = commit(repo, "T1", env=ENV)
    assert r.returncode == 0, r.stdout + r.stderr
    assert git(repo, "log", "-1", "--format=%s") == "PIX-5 T1: parser"


def test_apply_rebuilds_subjects(tmp_path):
    repo = make_repo(tmp_path)
    write(repo, "src/a.py", "A = 1\n")
    r = commit(repo, "T1", env=OFF)
    assert r.returncode == 0, r.stdout + r.stderr
    add_ticket(repo, "PIX-7")
    r = run("autocommit", "apply", "--plan", "plan.md", cwd=repo, env=OFF)
    assert r.returncode == 0, r.stdout + r.stderr
    assert git(repo, "log", "-1", "--format=%s") == "PIX-7 T1: parser"
    assert "- PIX-7 T1: parser" in r.stdout


def test_empty_header_key_does_not_shadow_later(tmp_path):
    p = plan(tmp_path, "**Ticket:**\n**Ticket:** PIX-3", "### T1 parser\n**Owns:** `a`\n")
    assert autocommit.ticket(p) == "PIX-3"
    assert autocommit.subject("T1", "parser", p) == "PIX-3 T1: parser"


def test_apply_skipped_line_uses_rebuilt_subject(tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    monkeypatch.chdir(repo)
    write(repo, "README.md", "v1\n")
    autocommit.checkpoint("T1", "parser", ["README.md"], "plan.md")
    write(repo, "README.md", "base\n")
    autocommit.checkpoint("T1", "parser", ["README.md"], "plan.md")
    add_ticket(repo, "PIX-8")
    r = run("autocommit", "apply", cwd=repo, env=OFF)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "apply: skipped PIX-8 T1: parser (no change left)" in r.stdout


def test_title_text_kept_verbatim(tmp_path):
    q = plan(tmp_path, "", "### T1 Add `parse()` helper\n**Owns:** `a`\n")
    assert autocommit.subject("T1", "Add `parse()` helper", q) == "T1: Add `parse()` helper"
    p = plan(tmp_path, "**Ticket:** PIX-9", "### T1 Add `parse()` helper\n**Owns:** `a`\n")
    assert autocommit.subject("T1", "Add `parse()` helper", p) == "PIX-9 T1: Add `parse()` helper"
    assert autocommit.subject("T1", "Add  two  spaces", p) == "PIX-9 T1: Add  two  spaces"
    r = plan(tmp_path, HEAD_TPL, "### T1 parser\n**Type:** fix\n**Ticket:** PIX-12\n**Owns:** `a`\n")
    assert autocommit.subject("T1", "parser", r) == "fix: PIX-12 parser"
