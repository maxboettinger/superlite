"""probe_run --dismiss stores a ruling and later runs keep the group out of failures (#417)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SDD = ROOT / "skills" / "subagent-driven-development"
PROBE_RUN = SDD / "probes" / "probe_run.py"
PT_REVIEW = SDD / "scripts" / "pt_review.py"

SOURCE = '''
class BadInput(Exception):
    pass


def parse(text):
    if text.isdigit():
        return int(text)
    if KEY:
        return {}["missing"]
    raise BadInput(text[:20])
'''


def project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    (root / "src").mkdir(parents=True)
    (root / "src" / "a.py").write_text("KEY = False\n" + SOURCE, encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
    (root / "plan.md").write_text("# p\n\n**Probe entry:** call=a.parse\n", encoding="utf-8")
    p = subprocess.run([sys.executable, str(PT_REVIEW), "adapter", "--plan", str(root / "plan.md"),
                        "--root", str(root)], capture_output=True, text=True)
    assert p.returncode == 0, p.stdout + p.stderr
    return root


def probe_run(root: Path, *args) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(PROBE_RUN), "--plan", str(root / "plan.md"), *map(str, args)],
                          capture_output=True, text=True, timeout=300, cwd=root)


def results(root: Path) -> dict:
    return json.loads((root / ".superlite" / "probes" / "probe-results.json").read_text(encoding="utf-8"))


def incidents(root: Path) -> list[dict]:
    p = root / ".superlite" / "incidents.jsonl"
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


def dismissed_project(tmp_path: Path) -> Path:
    root = project(tmp_path)
    assert probe_run(root, "--categories", "deep").returncode == 1
    p = probe_run(root, "--dismiss", "test_probe_deep_1", "--reason", "domain error")
    assert p.returncode == 0, p.stdout + p.stderr
    return root


def test_dismiss_cli_stores_and_removes(tmp_path):
    root = project(tmp_path)
    p = probe_run(root, "--categories", "deep")
    assert p.returncode == 1
    reg = root / "tests" / "regression"
    assert (reg / "test_probe_deep_1.py").is_file()
    p = probe_run(root, "--dismiss", "test_probe_deep_1", "--reason", "domain error")
    assert p.returncode == 0, p.stdout + p.stderr
    assert p.stdout.startswith("dismissed test_probe_deep_1: deep crash|BadInput|"), p.stdout
    assert not (reg / "test_probe_deep_1.py").exists() and not (reg / "_probe_adapter.py").exists()
    store = json.loads((root / ".superlite" / "probes" / "dismissed.json").read_text(encoding="utf-8"))
    assert len(store["dismissed"]) == 1
    assert incidents(root)[-1]["resolution"] == "wontfix"


def test_dismiss_unknown_exit_2(tmp_path):
    root = tmp_path / "proj"
    (root / ".superlite").mkdir(parents=True)
    (root / "plan.md").write_text("# p\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
    p = probe_run(root, "--dismiss", "g7")
    assert p.returncode == 2 and "g7" in p.stderr


def test_dismissed_group_not_regenerated(tmp_path):
    root = dismissed_project(tmp_path)
    before = len(incidents(root))
    p = probe_run(root, "--categories", "deep")
    assert p.returncode == 0, p.stdout + p.stderr
    assert not list((root / "tests" / "regression").glob("test_probe_*.py"))
    res = results(root)
    assert res["failures"] == [] and res["dismissed"]
    assert all(g["dismissed"] == "test_probe_deep_1" for g in res["dismissed"])
    assert " dismissed" in p.stdout
    assert not [e for e in incidents(root)[before:] if e.get("resolution") == "open"]


def test_other_exception_still_fails(tmp_path):
    root = dismissed_project(tmp_path)
    src = root / "src" / "a.py"
    src.write_text(src.read_text(encoding="utf-8").replace("KEY = False", "KEY = True"), encoding="utf-8")
    p = probe_run(root, "--categories", "deep")
    assert p.returncode == 1, p.stdout + p.stderr
    res = results(root)
    assert [g["exc"] for g in res["failures"]] == ["KeyError"]
    assert (root / res["failures"][0]["regression_test"]).is_file()


def test_dismissed_error_group_exit_0(tmp_path, monkeypatch):
    root = project(tmp_path)
    probe_run(root, "--categories", "deep")
    pid = results(root)["probes"][0]["id"]
    store = root / ".superlite" / "probes" / "dismissed.json"
    store.write_text(json.dumps({"dismissed": [{"id": pid, "category": pid.split("/")[0], "kind": None, "sig": None,
                                                "probes": [pid], "test": None, "incident": None}]}), encoding="utf-8")
    sys.path.insert(0, str(PROBE_RUN.parent))
    import probe_run as pr
    real = pr.run_probe

    def fake(pool, cfg, meta):
        r = real(pool, cfg, meta)
        return {**r, "status": "error", "detail": "make failed: boom"} if r["id"] == pid else {**r, "status": "pass"}
    monkeypatch.setattr(pr, "run_probe", fake)
    monkeypatch.chdir(root)
    rc = pr.main(["--plan", str(root / "plan.md"), "--categories", "deep"])
    assert [g["dismissed"] for g in results(root)["dismissed"]] == [pid]
    assert rc == 0
