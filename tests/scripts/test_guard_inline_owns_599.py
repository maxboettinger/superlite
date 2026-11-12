"""#599: a coordinator that builds a one-task plan inline may write that task's Owns."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import guard_judge as gj  # noqa: E402

INLINE = "- An inline build (the run's plan holds exactly one task): you may write that task's Owns yourself."
ONE = "# Plan\n\n### T1 a\n**Owns:** src/app.py, tests/test_app.py\n"
TWO = ONE + "\n### T2 b\n**Owns:** src/other.py\n"


def make(tmp_path, plan_text=ONE, stable=True):
    p = tmp_path / "proj"
    (p / "src").mkdir(parents=True)
    (p / "lib").mkdir()
    (p / "docs" / "plans").mkdir(parents=True)
    (p / ".superlite").mkdir()
    (p / "src" / "app.py").write_text("x = 1\n")
    (p / "src" / "other.py").write_text("x = 1\n")
    plan = p / "docs" / "plans" / "plan.md"
    plan.write_text(plan_text)
    subprocess.run(["git", "init", "-q", str(p)], check=True)
    if stable:
        (p / ".superlite" / "stable.json").write_text(json.dumps({"plan": str(plan)}))
    return p


def j(p, cmd, mode="active"):
    return gj.judge(cmd, str(p), str(p), mode, (str(p / ".superlite"),))


def cli(p, *extra, mode="active", nonce="N"):
    env = {k: v for k, v in os.environ.items() if not k.startswith("SUPERLITE_")}
    env["SUPERLITE_GUARD_NONCE"] = nonce
    return subprocess.run([sys.executable, "-I", str(SCRIPTS / "guard_judge.py"), "--mode", mode, "--project", str(p),
                           "--sd", str(p / ".superlite"), *extra], input="{}", capture_output=True, text=True, env=env, cwd=str(p))


def test_inline_owns_one_task(tmp_path):
    p = make(tmp_path)
    assert gj.inline_owns(str(p / ".superlite")) == (os.path.realpath(p), ["src/app.py", "tests/test_app.py"])


def test_inline_owns_none_cases(tmp_path):
    p = make(tmp_path, TWO)
    assert gj.inline_owns(str(p / ".superlite")) is None
    q = make(tmp_path / "b", stable=False)
    assert gj.inline_owns(str(q / ".superlite")) is None
    r = make(tmp_path / "c", ONE + "**Repo:** ../x\n")
    assert gj.inline_owns(str(r / ".superlite")) is None


def test_bash_write_to_owned_file_passes(tmp_path):
    p = make(tmp_path)
    assert j(p, "sed -i '' s/a/b/ src/app.py") is None
    assert j(p, "echo x > src/other.py").kind == "code"


def test_owned_glob(tmp_path):
    p = make(tmp_path, "# Plan\n\n### T1 a\n**Owns:** src/\n")
    assert j(p, "echo x > src/new.py") is None
    assert j(p, "echo x > lib/a.py").kind == "code"


def test_two_task_plan_blocks_bash(tmp_path):
    p = make(tmp_path, TWO)
    assert j(p, "echo x > src/app.py").kind == "code"


def test_owns_cli(tmp_path):
    p = make(tmp_path)
    for target in ("src/app.py", str(p / "src" / "app.py")):
        r = cli(p, "--owns", target)
        assert (r.returncode, r.stdout.strip()) == (0, "guard: ok N")
    r = cli(p, "--owns", "src/other.py")
    assert (r.returncode, r.stdout) == (1, "")
    r = cli(p, "--owns", "src/app.py", mode="human")
    assert (r.returncode, r.stdout) == (1, "")


def test_owns_cli_refuses_protected_and_hardlink(tmp_path):
    p = make(tmp_path, "# Plan\n\n### T1 a\n**Owns:** .superlite/\n")
    assert cli(p, "--owns", ".superlite/orchestrator.json").returncode == 1
    q = make(tmp_path / "b")
    try:
        os.link(q / "src" / "app.py", q / "lib" / "x.py")
    except OSError:
        pytest.skip("no hard links")
    assert cli(q, "--owns", "src/app.py").returncode == 1
    assert j(q, "echo x > src/app.py").kind == "code"


def test_code_message_has_inline_line():
    lines = gj.MESSAGES["code"]
    i = lines.index(INLINE)
    assert lines[i + 1].startswith("- A throwaway edit to check a render")
