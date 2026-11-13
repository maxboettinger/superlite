"""#693 T4: the guard judges a script file this session wrote when a shell, source or a path runs it."""
import json
import os
import subprocess
import sys
import time

import pytest

from test_block_coordinator_edits import ROOT, bash, proj, run  # noqa: F401

sys.path.insert(0, str(ROOT / "skills" / "subagent-driven-development" / "scripts"))
import guard_judge as gj  # noqa: E402


@pytest.fixture
def out(tmp_path_factory):
    return tmp_path_factory.mktemp("out")


def put(path, text, mode=0o644, when=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(text, bytes):
        path.write_bytes(text)
    else:
        path.write_text(text)
    path.chmod(mode)
    if when is not None:
        os.utime(path, (when, when))
    return path


@pytest.mark.parametrize("form", ["sh {o}/w.sh", "bash {o}/w.sh", "zsh {o}/w.sh", "{o}/w.sh", "source {o}/w.sh",
                                  ". {o}/w.sh", "bash < {o}/w.sh", "bash scripts/w.sh"])
def test_session_shell_script_writer_blocked(proj, out, form):  # noqa: F811
    put(out / "w.sh", "echo y > src/a.py\n", 0o755)
    put(proj / "scripts" / "w.sh", "echo y > src/a.py\n")
    r = bash(proj, form.format(o=out))
    assert r.returncode == 2, r.stderr
    assert r.stderr.splitlines()[-1] == "Blocked target: src/a.py"


@pytest.mark.parametrize("form", ["sh {o}/r.sh", "{o}/r.sh"])
def test_session_shell_script_reader_passes(proj, out, form):  # noqa: F811
    put(out / "r.sh", "wc -l src/a.py\n", 0o755)
    assert bash(proj, form.format(o=out)).returncode == 0


def test_session_script_eval_inside(proj, out):  # noqa: F811
    put(out / "e.sh", 'eval "$(echo rm -rf src)"\n')
    assert bash(proj, f"sh {out}/e.sh").returncode == 2


@pytest.mark.parametrize("kind", ["big", "latin", "mode0", "swift"])
def test_session_script_unreadable_refused(proj, out, kind):  # noqa: F811
    cmd, want = f"sh {out}/s", ""
    if kind == "big":
        put(out / "s", "# c\n" * 17500 + "ls\n")
        want = "over 65536 characters"
    elif kind == "latin":
        put(out / "s", b"\xff\xfe ls")
        want = "not UTF-8 text"
    elif kind == "mode0":
        if os.geteuid() == 0:
            pytest.skip("root reads mode 000")
        put(out / "s", "ls\n", 0)
        want = "unreadable"
    else:
        put(out / "s", "#!/usr/bin/env swift\nprint(1)\n", 0o755)
        cmd, want = f"{out}/s", "swift"
    r = bash(proj, cmd)
    assert r.returncode == 2, r.stderr
    assert want in r.stderr


def test_binary_and_missing_run(proj, out):  # noqa: F811
    put(out / "app", b"\x7fELF" + b"\0" * 64, 0o755)
    assert bash(proj, f"{out}/app --version").returncode == 0
    assert bash(proj, "bash nothere.sh").returncode == 0
    assert bash(proj, f"{out}/none.sh").returncode == 0
    assert bash(proj, 'bash "$SL" x').returncode == 0


def test_old_and_tracked_scripts_pass(proj, out):  # noqa: F811
    t = out / "t.jsonl"
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 3600))
    t.write_text(json.dumps({"type": "user", "timestamp": stamp}) + "\n")
    w = put(out / "w.sh", "echo y > src/a.py\n", when=time.time() - 7200)
    r = run(proj, "Bash", {"command": f"sh {w}"}, transcript_path=str(t))
    assert r.returncode == 0, r.stderr
    os.utime(w, None)
    r = run(proj, "Bash", {"command": f"sh {w}"}, transcript_path=str(t))
    assert r.returncode == 2, r.stderr
    subprocess.run(["git", "init", "-q"], cwd=proj, check=True)
    put(proj / "tools" / "w.sh", "echo y > src/a.py\n")
    subprocess.run(["git", "add", "tools/w.sh"], cwd=proj, check=True)
    r = run(proj, "Bash", {"command": "bash tools/w.sh"}, transcript_path=str(t))
    assert r.returncode == 0, r.stderr


def test_plugin_tree_exempt(tmp_path, monkeypatch):
    plugin = tmp_path / "plugin"
    monkeypatch.setattr(gj, "PLUGIN_ROOT", os.path.realpath(plugin))
    sd = tmp_path / "sd"
    sd.mkdir()
    outside = tmp_path / "proj"
    (outside / ".superlite").mkdir(parents=True)
    s = put(plugin / "tools" / "s.sh", "ls\n")
    ctx = gj._Ctx("", str(outside), "active", (str(sd),))
    assert gj._session_written(os.path.realpath(s), ctx) is False
    inner = plugin / "proj"
    (inner / ".superlite").mkdir(parents=True)
    s2 = put(inner / "s.sh", "ls\n")
    ctx2 = gj._Ctx("", str(inner), "active", (str(sd),))
    assert gj._session_written(os.path.realpath(s2), ctx2) is True


def test_activate_still_passes(proj):  # noqa: F811
    put(proj / ".venv" / "bin" / "activate", "rm -rf src\n")
    assert bash(proj, "source .venv/bin/activate").returncode == 0
