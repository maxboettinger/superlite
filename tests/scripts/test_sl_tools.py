import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SL = ROOT / "skills" / "subagent-driven-development" / "scripts" / "sl"
_GIT_BASH = r"C:\Program Files\Git\bin\bash.exe"
BASH = _GIT_BASH if os.name == "nt" and os.path.exists(_GIT_BASH) else shutil.which("bash")


def _sl(tmp_path, *args):
    env = {k: v for k, v in os.environ.items() if k not in ("SUPERLITE_SL", "SUPERLITE_PYTHON")}
    env["SUPERLITE_CACHE_DIR"] = str(tmp_path / "cache")
    return subprocess.run([BASH, str(SL), *args], capture_output=True, text=True, env=env, encoding="utf-8")


def test_bare_sl_lists_tools(tmp_path):
    r = _sl(tmp_path)
    assert r.returncode == 2
    assert "usage: sl" in r.stderr
    for name in ("orchestrator", "metrics", "dispatch", "probe_run"):
        assert name in r.stderr.split()
    assert "_pyrun" not in r.stderr


def test_typo_suggests_nearest(tmp_path):
    r = _sl(tmp_path, "metrcs")
    assert r.returncode == 2
    assert "did you mean 'metrics'?" in r.stderr
    assert "sl: unknown tool 'metrcs'" in r.stderr


def test_unknown_without_match(tmp_path):
    r = _sl(tmp_path, "zzzz")
    assert r.returncode == 2
    assert "did you mean" not in r.stderr
    assert "metrics" in r.stderr.split()


def test_status_hint(tmp_path):
    r = _sl(tmp_path, "status")
    assert r.returncode == 2
    assert "try: sl orchestrator status; sl metrics" in r.stderr
