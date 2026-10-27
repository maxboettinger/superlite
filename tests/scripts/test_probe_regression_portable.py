"""Generated regression tests are self-contained: they import a local copy of the adapter."""
import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RUNNER = REPO / "skills" / "subagent-driven-development" / "probes" / "probe_run.py"

spec = importlib.util.spec_from_file_location("probe_run_mod", RUNNER)
pr = importlib.util.module_from_spec(spec)
sys.modules["probe_run_mod"] = pr
spec.loader.exec_module(pr)

ADAPTER = '''from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
EXPECTED_ERRORS = (ValueError,)


def call(x):
    if x == "boom":
        raise ValueError("expected")
    return x
'''


def write(tmp_path, adapter_text=ADAPTER):
    proj = tmp_path / "proj"
    (proj / ".superlite" / "probes").mkdir(parents=True)
    ad = proj / ".superlite" / "probes" / "adapter.py"
    ad.write_text(adapter_text)
    cfg = pr.Cfg(proj.resolve(), ad.resolve(), None, 10.0)
    group = {"category": "protocol", "kind": "k", "key": "kk", "probe": "p1", "size": 4}
    rep = {"status": "fail", "input": "'boom'",
           "probe_meta": {"entry": "call", "name": "n", "module": "/nonexistent.py"}}
    return proj, cfg, group, rep


def test_regression_imports_local_adapter_copy(tmp_path):
    proj, cfg, group, rep = write(tmp_path)
    rel = pr._write_regression(cfg, group, rep)
    reg = proj / "tests" / "regression"
    assert (reg / "_probe_adapter.py").exists()
    assert ".superlite" not in (proj / rel).read_text()


def test_copy_root_points_at_repo(tmp_path):
    proj, cfg, group, rep = write(tmp_path, "ROOT = 1\nX = 2\nROOT = 3\n")
    pr._write_regression(cfg, group, rep)
    lines = (proj / "tests/regression/_probe_adapter.py").read_text().splitlines()
    roots = [i for i, l in enumerate(lines) if l.startswith("ROOT = ")]
    assert lines[roots[0]] == "ROOT = Path(__file__).resolve().parents[2]"
    assert lines[roots[1]] == "ROOT = 3"
    assert "from pathlib import Path" in lines


def test_copy_refreshed_when_adapter_changes(tmp_path):
    proj, cfg, group, rep = write(tmp_path)
    pr._write_regression(cfg, group, rep)
    cfg.adapter.write_text(ADAPTER + "NEW = 1\n")
    pr._write_regression(cfg, group, rep)
    assert "NEW = 1" in (proj / "tests/regression/_probe_adapter.py").read_text()


def test_regression_runs_without_superlite_dir(tmp_path):
    proj, cfg, group, rep = write(tmp_path)
    rel = pr._write_regression(cfg, group, rep)
    shutil.rmtree(proj / ".superlite")
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", rel],
                       cwd=proj, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "1 passed" in r.stdout
