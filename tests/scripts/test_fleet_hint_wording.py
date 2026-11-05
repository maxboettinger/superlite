from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEXT = (ROOT / "skills" / "using-superlite" / "SKILL.md").read_text(encoding="utf-8")

# every rule, command and skill name of the text before the fleet sentence was added (wording trimmed to fit the cap)
OLD_RULES = [
    "/superlite:start", "A new app is never trivial", "human mode: after an approved review plan",
    "chat design, build", "one AskUserQuestion (≤4), one design+plan",
    "human (approves plan first) or AI", '"decide yourself", away, headless, no AskUserQuestion: AI (a Ruling)',
    "`brainstorming`, no menu", "sl orchestrator set human|ai", "AI asks only major/uncertain questions",
    "halts only on destructive/outward/security steps",
    "build `brainstorming`", "plan `writing-plans`", "run `subagent-driven-development`", "bug `systematic-debugging`",
    "TDD `test-driven-development`", "done `verification-before-completion`", "finish `finishing-a-development-branch`",
    "**2+ tasks: `subagent-driven-development`,** loaded before the plan", "no `general-purpose` agents",
    "inline only if small (few files, one chain; say so)", "Bounded (existing flow)", "fresh `superlite:final-reviewer`",
    "<skill-dir>/../subagent-driven-development/scripts/sl <tool>", "never `python`", "`sl graphify_gate`",
    "sl feedback add --kind bug|slow|unclear|repeat|idea", "don't fix mid-task",
    "**Superlite broke/unclear?**", '"<what, where, expected>"',
    "references/<harness>-tools.md", "agents/*.md",
]


def test_root_skill_names_fleet_on():
    assert "`sl fleet on` before the first dispatch" in TEXT
    assert "taskgraph implementers only" in TEXT and "inline starts no worker" in TEXT


def test_root_skill_under_cap():
    assert len(TEXT) < 1500
    missing = [r for r in OLD_RULES if r not in TEXT]
    assert not missing, missing


def test_fleet_worker_env_stays_out_of_unit_tests(monkeypatch):
    import os
    import subprocess
    import sys
    assert "SUPERLITE_FLEET_WORKER" not in os.environ and "SUPERLITE_FLEET_AGENT" not in os.environ
    env = dict(os.environ, SUPERLITE_FLEET_WORKER="W1", SUPERLITE_FLEET_AGENT="claude")
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider",
                        str(ROOT / "tests" / "scripts" / "test_session_start.py")],
                       env=env, cwd=ROOT, capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stdout[-1500:]
