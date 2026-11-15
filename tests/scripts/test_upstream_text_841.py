"""#841: the prime names the sl tool forms; the `model` rule is stated once, for superlite agents."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skills" / "subagent-driven-development" / "scripts"))
import build_prime  # noqa: E402


def test_prime_preambles_name_the_sl_forms_841():
    for text in (build_prime.PREAMBLE, build_prime.PREAMBLE_SLIM):
        assert "- Log every unexpected failure, workaround or guess with `sl incident add`.\n" in text
        assert "- Do not commit. The coordinator records a checkpoint with `sl commit_task`.\n" in text
    for text in (build_prime.PREAMBLE, build_prime.PREAMBLE_SLIM, build_prime.PREAMBLE_MINI):
        assert "incident.py" not in text and "commit_task.py" not in text


def test_model_rule_stated_once_for_superlite_agents_841():
    hits = [(p.relative_to(ROOT).as_posix(), line) for p in sorted((ROOT / "skills").rglob("*.md"))
            for line in p.read_text(encoding="utf-8").splitlines() if "pass `model`" in line]
    assert [h[0] for h in hits] == ["skills/subagent-driven-development/SKILL.md"], hits
    assert "Never pass `model` to a superlite agent." in hits[0][1]


def test_no_skill_sets_a_model_on_explore_841():
    brain = (ROOT / "skills" / "brainstorming" / "SKILL.md").read_text(encoding="utf-8")
    assert "(broad sweeps: an Explore agent, effort low)" in brain
    for p in sorted((ROOT / "skills").rglob("*.md")):
        assert "model haiku" not in p.read_text(encoding="utf-8"), p
