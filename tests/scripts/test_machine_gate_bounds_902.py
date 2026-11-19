"""#902: `--over-limit` takes bounds that still refuse at critical; a waiting review spawn goes before an implementer."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import machine_load as ml  # noqa: E402

G, M = 1 << 30, 1 << 20
MX = {"agents": 9, "each": 400 * M, "total": 64 * G, "free": 9 * G, "pressure": "warn", "swap_total": 2 * G,
      "swap_used": 3 * G // 2, "compressed": G, "other": ("bigd", 20 * G)}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.delenv("SUPERLITE_MACHINE_LIMIT", raising=False)
    monkeypatch.delenv("SUPERLITE_MACHINE_FLOOR", raising=False)


def _patch(monkeypatch, m):
    monkeypatch.setattr(ml, "measure", lambda *a, **k: dict(m))


def test_bounded_cause_examples():
    assert ml.bounded_cause({**MX, "pressure": "critical"}, {"max_workers": 6, "min_swap_free_mb": 1024}, 2) == "critical"
    assert ml.bounded_cause(MX, {"min_swap_free_mb": 1024}, None) == "swap"
    assert ml.bounded_cause({**MX, "swap_total": 0, "swap_used": 0}, {"min_swap_free_mb": 1024}, None) is None
    assert ml.bounded_cause(MX, {"max_workers": 6}, 6) == "workers"
    assert ml.bounded_cause(MX, {"max_workers": 6}, 5) is None
    assert ml.bounded_cause(MX, {"max_workers": None, "min_swap_free_mb": None}, 9) is None


def _waiter(pid, rank=0, what="fleet spawn (package-reviewer)", t=None):
    f = ml.home() / "machine-wait" / f"{pid}.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"pid": pid, "rank": rank, "what": what, "t": time.time() if t is None else t}))
    return f


@pytest.fixture
def live():
    p = subprocess.Popen(["sleep", "30"])
    yield p.pid
    p.kill()
    p.wait()


def test_review_waiting_examples(live):
    f = _waiter(live)
    assert ml.review_waiting() == "fleet spawn (package-reviewer)"
    assert ml.review_waiting(own_pid=live) is None
    _waiter(live, rank=1)
    assert ml.review_waiting() is None
    _waiter(live, t=time.time() - 4000)
    assert ml.review_waiting() is None
    f.unlink()
    d = subprocess.Popen(["sleep", "0"])
    d.wait()
    g = _waiter(d.pid)
    assert ml.review_waiting() is None and not g.exists()


def test_bounded_override_admits_past_floor(monkeypatch, capsys):
    _patch(monkeypatch, MX)
    assert ml.gate("w", 0, True, bounds={"min_swap_free_mb": 256}, run_workers=1) is None
    assert "machine limit overridden (--over-limit within --min-swap-free-mb 256): " in capsys.readouterr().err


def test_bounded_override_refuses_critical(monkeypatch):
    _patch(monkeypatch, {**MX, "pressure": "critical"})
    busy = ml.gate("w", 0, True, bounds={"min_swap_free_mb": 256}, run_workers=1)
    assert busy.startswith("machine busy after 0 s: memory pressure critical")
    assert "gave up after 1 check in 0 s: pressure critical" in busy


def test_bounded_override_refuses_low_swap(monkeypatch):
    _patch(monkeypatch, MX)
    busy = ml.gate("w", 0, True, bounds={"min_swap_free_mb": 1024}, run_workers=1)
    assert "; swap free under --min-swap-free-mb 1024" in busy and "swap free under 1024 MB" in busy


def test_bounded_override_refuses_worker_cap(monkeypatch):
    _patch(monkeypatch, MX)
    busy = ml.gate("w", 0, True, bounds={"max_workers": 6}, run_workers=6)
    assert "; 6 live workers in this run, --max-workers 6" in busy and "this run at --max-workers 6" in busy


def test_plain_over_limit_unbounded(monkeypatch):
    _patch(monkeypatch, {**MX, "pressure": "critical"})
    assert ml.gate("w", 0, True) is None


def test_implementer_yields_to_waiting_review(monkeypatch, live):
    _patch(monkeypatch, {**MX, "free": 32 * G})
    _waiter(live)
    busy = ml.gate("fleet spawn (implementer)", 0)
    assert "; a review spawn waits first: fleet spawn (package-reviewer)" in busy
    assert ml.gate("fleet spawn (package-reviewer)", 0, rank=0) is None


def test_review_waiter_registers_and_cleans(monkeypatch):
    it = iter([MX, {**MX, "free": 32 * G}])
    monkeypatch.setattr(ml, "measure", lambda *a, **k: dict(next(it)))
    f = ml.home() / "machine-wait" / f"{os.getpid()}.json"
    seen = []

    def sleep(_):
        d = json.loads(f.read_text())
        seen.append((d["pid"], d["rank"]))

    monkeypatch.setattr(ml.time, "sleep", sleep)
    assert ml.gate("fleet spawn (package-reviewer)", 30, rank=0, poll_s=0) is None
    assert seen == [(os.getpid(), 0)] and not f.exists()
