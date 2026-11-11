"""pool.sync fills a Herdr agent's missing baseline_k from fleet_io (#455)."""
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import assign  # noqa: E402
import fleet_io  # noqa: E402
import pool  # noqa: E402


def test_sync_fills_missing_baseline_for_herdr_agents(tmp_path, monkeypatch):
    (tmp_path / "fleet.json").write_text("{}")
    monkeypatch.setattr(fleet_io, "baseline_k", lambda sd, wid: {"W1": 14.4, "W2": 1.0, "a3": 2.0}[wid])
    data = {"agents": [{"id": "W1", "backend": "herdr"}, {"id": "W2", "backend": "herdr", "baseline_k": 9.5}, {"id": "a3"}]}
    pool.sync(data, tmp_path, 0)
    w1, w2, a3 = data["agents"]
    assert w1["baseline_k"] == 14.4
    assert w2["baseline_k"] == 9.5
    assert "baseline_k" not in a3


def test_sync_without_fleet_json_never_calls_baseline(tmp_path, monkeypatch):
    def boom(sd, wid):
        raise AssertionError("baseline_k called")
    monkeypatch.setattr(fleet_io, "baseline_k", boom)
    data = {"agents": [{"id": "W1", "backend": "herdr"}]}
    pool.sync(data, tmp_path, 0)
    assert "baseline_k" not in data["agents"][0]


def test_sync_baseline_none_or_error_leaves_key_absent(tmp_path, monkeypatch):
    (tmp_path / "fleet.json").write_text("{}")

    def fake(sd, wid):
        if wid == "W2":
            raise OSError("x")
        return None
    monkeypatch.setattr(fleet_io, "baseline_k", fake)
    data = {"agents": [{"id": "W1", "backend": "herdr"}, {"id": "W2", "backend": "herdr"}]}
    pool.sync(data, tmp_path, 0)
    assert all("baseline_k" not in a for a in data["agents"])


def test_eligibility_counts_from_filled_baseline(tmp_path, monkeypatch):
    (tmp_path / "fleet.json").write_text("{}")
    monkeypatch.setattr(fleet_io, "baseline_k", lambda sd, wid: 40.0)
    w1 = {"id": "W1", "backend": "herdr", "context_k": 70}
    assert assign.eligibility(w1, 20.0, None, 2.0) == "context over 80k"
    pool.sync({"agents": [w1]}, tmp_path, 0)
    assert assign.eligibility(w1, 20.0, None, 2.0) is None
