"""Docs contract: absolute sl path, prime file pointer, new flags."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))
SKILL = (ROOT / "skills" / "subagent-driven-development" / "SKILL.md").read_text(encoding="utf-8")


def test_no_shell_variable_in_agent_commands():
    for f in (ROOT / "agents").glob("*.md"):
        t = f.read_text(encoding="utf-8")
        assert "$SUPERLITE" not in t and "$SL" not in t, f.name
        if f.name != "final-reviewer.md":
            assert "absolute" in t and "sl" in t, f.name


def test_skill_prime_is_file_pointer():
    assert "Read <abs>/.superlite/prime.md" in SKILL and "reply READY" in SKILL
    assert "never paste" in SKILL.lower() or "Never paste" in SKILL
    assert "prime verbatim" not in SKILL and "pasted verbatim" not in SKILL


def test_implementer_reads_prime_file():
    for n in ("implementer.md", "implementer-haiku.md"):
        t = (ROOT / "agents" / n).read_text(encoding="utf-8")
        assert "prime.md" in t, n


def test_skill_verify_command_has_task():
    assert "run_tests --fast PATHS --task Tn --background" in SKILL


def test_skill_names_new_flags():
    assert '--also F --ruling "..."' in SKILL
    assert "trees clean" in SKILL
    assert "zsh" in SKILL


def test_writing_plans_headers():
    t = (ROOT / "skills" / "writing-plans" / "SKILL.md").read_text(encoding="utf-8")
    assert "**Ticket:**" in t and "**Wave0:** none" in t
    assert "test-cmd.json" in t and "{only_testing}" in t


def test_docs_mention_new_surface():
    lang = (ROOT / "docs" / "language.md").read_text(encoding="utf-8")
    assert "Xcode" in lang and "isolated" in lang
    tools = (ROOT / "docs" / "tools.md").read_text(encoding="utf-8")
    assert "trees" in tools and "--task" in tools and "--also" in tools


def test_wave0_agent_line_absolute():
    import wave0
    line = wave0.agent_line(Path("/r/.superlite/briefs/wave0.md"), "T0")
    assert "bash " in line and "/scripts/sl" in line
    assert "$SUPERLITE" not in line and "SUPERLITE=" not in line
    assert str(SCRIPTS / "sl") in line.replace("\\\\", "/")


def test_using_superlite_cap():
    assert len((ROOT / "skills" / "using-superlite" / "SKILL.md").read_text(encoding="utf-8")) <= 1500 + 3000
