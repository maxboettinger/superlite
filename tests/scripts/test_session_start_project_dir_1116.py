# tests/scripts/test_session_start_project_dir_1116.py: session-start exports the launch folder as SUPERLITE_PROJECT_DIR (#1116)
import json, os, subprocess
from test_session_state import BASH, ROOT


def run_hook(tmp_path, extra_input=None, project_dir=None):
    env_file = tmp_path / "env.sh"
    env = dict(os.environ, CLAUDE_ENV_FILE=str(env_file), CLAUDE_PLUGIN_ROOT=str(ROOT))
    env.pop("CLAUDE_PROJECT_DIR", None)
    env.pop("SUPERLITE_PROJECT_DIR", None)
    if project_dir:
        env["CLAUDE_PROJECT_DIR"] = project_dir
    data = {"session_id": "a1", "source": "clear", **(extra_input or {})}
    r = subprocess.run([BASH, str(ROOT / "hooks" / "session-start")], input=json.dumps(data), capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    got = subprocess.run([BASH, "-c", '. "$1"; printf %s "${SUPERLITE_PROJECT_DIR-unset}"', "x", str(env_file)],
                         capture_output=True, text=True, env={k: v for k, v in os.environ.items() if k != "SUPERLITE_PROJECT_DIR"})
    return got.stdout, env_file.read_text()


def test_exports_claude_project_dir_with_a_space(tmp_path):
    assert run_hook(tmp_path, project_dir="/tmp/my proj")[0] == "/tmp/my proj"


def test_falls_back_to_the_input_cwd(tmp_path):
    assert run_hook(tmp_path, {"cwd": "/w/proj"})[0] == "/w/proj"


def test_no_launch_folder_no_export(tmp_path):
    value, text = run_hook(tmp_path)
    assert value == "unset"
    assert "export SUPERLITE_SESSION_ID=a1" in text
