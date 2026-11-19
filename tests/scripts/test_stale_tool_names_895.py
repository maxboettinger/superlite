from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SDD = "skills/subagent-driven-development"


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def test_no_sl_lint_stable():
    for rel in (f"{SDD}/scripts/next_tasks.py", f"{SDD}/SKILL.md", "docs/tools.md"):
        assert "sl lint --stable" not in read(rel), rel
    assert "rerun sl plan_tools lint --stable" in read(f"{SDD}/scripts/next_tasks.py")


def test_no_sl_setup():
    for rel in (f"{SDD}/scripts/compact_due.py", "hooks/compact-nudge", "docs/config.md", "docs/hooks.md"):
        text = read(rel)
        assert "sl setup" not in text, rel
        assert "/superlite:setup" in text, rel


def test_allowlist_has_no_setup_or_lint_lines():
    text = read("tests/scripts/doc_contract_allowlist.txt")
    assert "| lint --stable |" not in text
    assert "| setup |" not in text


def test_config_names_remote_write_grant():
    text = read("docs/config.md")
    section = text.split("## Permissions (Claude Code)")[1].split("\n## ")[0]
    assert "ssh <host> bash -s < script" in section


def test_skill_size():
    assert len(read(f"{SDD}/SKILL.md")) <= 13300
