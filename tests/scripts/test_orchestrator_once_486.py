"""#486, #502: start states the orchestrator step once; later texts read it; --branch and --dir are named."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def test_start_states_it_once_and_where_it_lives():
    text = read("commands/start.md")
    assert 1 <= text.count("sl orchestrator set") <= 2
    for need in (".superlite/orchestrator.json", "lint --stable", "--branch", "--dir"):
        assert need in text, need


def test_feature_and_mvp_only_read_it():
    for rel in ("commands/feature.md", "commands/mvp.md"):
        text = read(rel)
        assert "sl orchestrator set" not in text, rel
        assert "unless the user already said" not in text, rel
        assert "sl orchestrator status" in text, rel


def test_brainstorming_reads_status_first():
    text = read("skills/brainstorming/SKILL.md")
    assert "sl orchestrator status" in text
    assert text.count("sl orchestrator set") <= 1
    assert "--branch" in text
