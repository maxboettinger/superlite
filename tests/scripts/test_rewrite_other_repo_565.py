"""#565: a test run outside the plan root is left as written; a redirect target is no test path."""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOOK = ROOT / "hooks" / "rewrite-test-runs"
BASH = shutil.which("bash")
SL = (ROOT / "skills" / "subagent-driven-development" / "scripts" / "sl").as_posix()
SLFULL = f'bash "{SL}" run_tests --full'
SLFAST = f'bash "{SL}" run_tests --fast'

pytestmark = pytest.mark.skipif(os.name == "nt", reason="POSIX paths")


@pytest.fixture
def tree(tmp_path):
    main = tmp_path / "main"
    proj = main / ".claude" / "worktrees" / "wt"
    (proj / ".superlite").mkdir(parents=True)
    (proj / ".superlite" / "pool.json").write_text("{}")
    (proj / "tests").mkdir()
    other = tmp_path / "other"
    (other / "tests").mkdir(parents=True)
    return {"main": main, "proj": proj, "other": other, "tmp": tmp_path}


def run(proj, command, env_extra=None, **extra):
    raw = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}, **extra})
    env = {k: v for k, v in os.environ.items() if not k.startswith("SUPERLITE_")}
    env.pop("CLAUDE_PLUGIN_ROOT", None)
    env["CLAUDE_PROJECT_DIR"] = str(proj)
    env.update(env_extra or {})
    return subprocess.run([BASH, str(HOOK)], input=raw, capture_output=True, text=True, env=env)


def unchanged(r):
    assert (r.returncode, r.stdout, r.stderr) == (0, "", "")
    return True


def rewritten(r):
    assert r.returncode == 0 and r.stderr == "", r.stderr
    return json.loads(r.stdout)["hookSpecificOutput"]["updatedInput"]["command"]


def test_issue_565_cross_repo_check_left_as_written(tree):
    cmd = f"cd {tree['other']} && npm install && npm run build && npm test > /tmp/x-565.log 2>&1"
    assert unchanged(run(tree["proj"], cmd, cwd=str(tree["proj"])))


@pytest.mark.parametrize("form", [
    "cd {o} && npm test",
    "cd {o}; npm test",
    "pushd {o} && npm test",
    "(cd {o} && npm test -- --ci)",
    "cd {o} && pytest -x",
    "cd {o} && pytest tests/test_a.py",
    "cd {o} && go test ./...",
    "cd '{o}' && npm test",
    'cd "{o}" && npm test',
    "cd -P {o} && npm test",
    "cd {o}/tests && cd .. && npm test",
    "cd {main} && pytest",
])
def test_cd_into_another_repo_left_as_written(tree, form):
    assert unchanged(run(tree["proj"], form.format(o=tree["other"], main=tree["main"])))


def test_cwd_in_another_repo_left_as_written(tree):
    assert unchanged(run(tree["proj"], "npm test", cwd=str(tree["other"])))
    assert unchanged(run(tree["proj"], "pytest tests/test_a.py", cwd=str(tree["other"])))


def test_runs_in_the_plan_root_still_rewritten(tree):
    p = tree["proj"]
    assert rewritten(run(p, "pytest", cwd=str(p))).strip() == SLFULL
    assert rewritten(run(p, "pytest tests/test_a.py", cwd=str(p / "tests"))).strip() == f"{SLFAST} tests/test_a.py"
    assert rewritten(run(p, f"pytest {p}/tests/test_a.py")).strip() == f"{SLFAST} {p}/tests/test_a.py"
    assert rewritten(run(p, f"cd {p} && pytest -x")) == f"cd {p} && {SLFULL} "
    assert rewritten(run(p, f"cd {p}/tests && pytest")) == f"cd {p}/tests && {SLFULL} "
    assert rewritten(run(p, "cd tests && pytest", cwd=str(p))) == f"cd tests && {SLFULL} "


def test_cwd_above_the_plan_root_still_rewritten(tree):
    p = tree["proj"]
    assert rewritten(run(p, "pytest tests/test_a.py", cwd=str(tree["main"]))).strip() == f"{SLFAST} tests/test_a.py"
    assert rewritten(run(p, "npm test", cwd=str(tree["main"]))).strip() == SLFULL


def test_back_into_the_plan_root_rewrites_only_that_run(tree):
    o, p = tree["other"], tree["proj"]
    cmd = f"cd {o} && npm run build && npm test; cd {p} && pytest"
    assert rewritten(run(p, cmd)) == f"cd {o} && npm run build && npm test; cd {p} && {SLFULL} "


@pytest.mark.parametrize("cmd", [
    "cd $REPO && npm test",
    'cd "$REPO" && pytest',
    "cd $(git rev-parse --show-toplevel) && pytest",
    "cd - && pytest",
    "popd && pytest",
    "cd ~other && npm test",
    "cd *x && npm test",
])
def test_unreadable_directory_left_as_written(tree, cmd):
    assert unchanged(run(tree["proj"], cmd))


def test_tilde_is_home(tree):
    p = tree["proj"]
    assert rewritten(run(p, "cd ~/tests && pytest", env_extra={"HOME": str(p)})) == f"cd ~/tests && {SLFULL} "
    assert unchanged(run(p, "cd ~ && pytest", env_extra={"HOME": str(tree["other"])}))
    assert unchanged(run(p, "cd && pytest", env_extra={"HOME": str(tree["other"])}))


def test_symlinked_spelling_of_the_plan_root_still_rewritten(tree):
    link = tree["tmp"] / "alias"
    link.symlink_to(tree["proj"], target_is_directory=True)
    assert rewritten(run(tree["proj"], f"cd {link} && pytest")) == f"cd {link} && {SLFULL} "
    assert rewritten(run(tree["proj"], f"cd {link}/tests && pytest")) == f"cd {link}/tests && {SLFULL} "
    out = tree["tmp"] / "out-link"
    out.symlink_to(tree["other"], target_is_directory=True)
    assert unchanged(run(tree["proj"], f"cd {out} && pytest"))


@pytest.mark.parametrize("cmd", [
    "pytest {o}/tests/test_a.py",
    "pytest ../../../../other/tests/test_a.py",
    "cargo test --manifest-path {o}/Cargo.toml",
])
def test_named_path_outside_the_plan_root_left_as_written(tree, cmd):
    assert unchanged(run(tree["proj"], cmd.format(o=tree["other"]), cwd=str(tree["proj"])))


@pytest.mark.parametrize("cmd,want", [
    ("pytest tests/test_a.py > out/log.txt", " tests/test_a.py"),
    ("pytest tests/test_a.py >/tmp/x-565.log 2>&1", " tests/test_a.py"),
    ("pytest tests/test_a.py 2> err/x.log", " tests/test_a.py"),
    ("pytest tests/test_a.py >> logs/x.log", " tests/test_a.py"),
    ("pytest tests/test_a.py &> logs/x.log", " tests/test_a.py"),
    ("pytest tests/test_a.py < in/x.txt", " tests/test_a.py"),
    ("npm test > /tmp/x-565.log 2>&1", None),
    ("npm test 2>logs/err.txt", None),
])
def test_redirect_target_is_no_test_path(tree, cmd, want):
    got = rewritten(run(tree["proj"], cmd)).strip()
    assert got == (f"{SLFAST}{want}" if want else SLFULL)


def test_outside_runs_are_never_denied(tree):
    o, p = tree["other"], tree["proj"]
    assert unchanged(run(p, f"cd {o} && until npm test; do sleep 1; done"))
    assert unchanged(run(p, f"cd {o} && npm test > /dev/null"))
    assert unchanged(run(p, f"cd {o} && npm test", agent_id="a1"))
    assert unchanged(run(p, f"cd {o} && pytest", env_extra={"SUPERLITE_FLEET_WORKER": "W3"}))


def test_inside_runs_still_denied(tree):
    p = tree["proj"]
    assert run(p, "until npm test; do sleep 1; done").returncode == 2
    assert run(p, f"cd {p} && npm test > /dev/null").returncode == 2
    assert run(p, "npm test", agent_id="a1").returncode == 2
    assert run(p, "pytest", env_extra={"SUPERLITE_FLEET_WORKER": "W3"}).returncode == 2


def test_isolate_stack_runner_in_another_repo_not_denied(tree):
    p, o = tree["proj"], tree["other"]
    (p / ".superlite" / "test-cmd.json").write_text(json.dumps({"language": "swift", "test": "xcodebuild test -scheme App"}))
    assert run(p, "xcodebuild test -scheme App", agent_id="a1").returncode == 2
    assert unchanged(run(p, f"cd {o} && xcodebuild test -scheme App", agent_id="a1"))


def test_builtins_only(tree):
    o, p = tree["other"], tree["proj"]
    assert unchanged(run(p, f"cd {o} && npm test", env_extra={"PATH": ""}))
    link = tree["tmp"] / "alias2"
    link.symlink_to(p, target_is_directory=True)
    assert rewritten(run(p, f"cd {link} && pytest", env_extra={"PATH": ""})) == f"cd {link} && {SLFULL} "


def test_null_runner_with_spanning_quote_still_denied(tree):
    p = tree["proj"]
    assert run(p, "npm test > /dev/null \"a; b\"").returncode == 2


def test_cwd_above_root_through_a_symlink_still_rewritten(tree):
    link = tree["tmp"] / "main-link"
    link.symlink_to(tree["main"], target_is_directory=True)
    assert rewritten(run(tree["proj"], "npm test", cwd=str(link))).strip() == SLFULL
