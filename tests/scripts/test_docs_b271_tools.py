"""B271 (#1008): docs/tools.md names #998's --plan anchoring and lint --stable's missing-plan refusal in the plan_tools row, and #999's remote base rerun with test-summary-base.json host and command in the --base-skips paragraph; each quoted text is checked against the script printing it."""
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
LINES = (ROOT / "docs" / "tools.md").read_text(encoding="utf-8").splitlines()
SCRIPTS = ROOT / "skills" / "subagent-driven-development" / "scripts"
START = {"plan_tools": "| `plan_tools` |", "base-skips": "`sl run_tests --base-skips [--plan DIR]`"}

NAMED = [  # (place, text it holds exactly once)
    ("plan_tools", "`anchor_plan`"),
    ("plan_tools", "resolves at the enclosing checkout's top (`state.git_root`: a linked worktree's own top)"),
    ("plan_tools", "a bare `.superlite` at the nearest run up to that top"),
    ("plan_tools", "`--spec` and `prune`'s `--dir` keep cwd semantics"),
    ("plan_tools", "`error: plan not found: <path>` (exit 2) before it binds the run (`state.bind`) (#998)"),
    ("base-skips", "A full run through `maxapp remote` reruns the base through that same remote command"),
    ("base-skips", "`run_tests: --base-skips runs on the full run's host: <command>`"),
    ("base-skips", "`run_tests: --base-skips: the remote test command cannot be narrowed to the skipped tests' files; it runs whole at the base: <command>`"),
    ("base-skips", "`host` (`remote`, `local`, or empty when nothing ran)"),
    ("base-skips", "`command` (its first 200 characters) (#999)"),
]
CODE = [  # (script, literal its source holds)
    ("plan_tools.py", "def anchor_plan(value: str, cwd: str | None = None) -> str:"),
    ("plan_tools.py", 'raise PlanError(f"plan not found: {path}")'),
    ("run_tests.py", "run_tests: --base-skips runs on the full run's host: {narrowed}"),
    ("run_tests.py", "run_tests: --base-skips: the remote test command cannot be narrowed to the skipped tests' files; it runs whole at the base: {full['command']}"),
    ("run_tests.py", '"host": host, "command": ran[:200]'),
]


def place(name):
    found = [x for x in LINES if x.startswith(START[name])]
    assert len(found) == 1, name
    return found[0]


@pytest.mark.parametrize("name,text", NAMED)
def test_place_names_it_once(name, text):
    assert place(name).count(text) == 1


@pytest.mark.parametrize("script,literal", CODE)
def test_quoted_texts_match_the_code(script, literal):
    assert literal in (SCRIPTS / script).read_text(encoding="utf-8")
