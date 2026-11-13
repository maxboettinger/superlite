"""Stats gate baseline (#681): a cheap tier is gated against the default tier's measured rate."""
from __future__ import annotations

import sys

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import routing  # noqa: E402

GATE = {"min_n": 8, "baseline": "default_tier", "min_first_time_pass": 0.8}
FT = {"task": "T1", "band": "b1", "mechanical": True, "critical_path": False}


def cfg():
    return {"default_tier": "sonnet", "tiers": {"haiku": {}, "sonnet": {}},
            "rules": [{"tier": "haiku", "when": {"mechanical": True, "critical_path": False}}, {"tier": "sonnet", "when": {}}],
            "stats_gate": GATE}


def stats(h, s):
    return {"bands_by_tier": {"haiku|b1": h, "sonnet|b1": s}}


def test_gate_bar_examples():
    st = {"bands_by_tier": {"sonnet|b1": {"n": 20, "ftp_rate": 0.74}}}
    assert routing.gate_bar(st, GATE, "sonnet", "b1") == 0.74
    st3 = {"bands_by_tier": {"sonnet|b1": {"n": 3, "ftp_rate": 0.5}}}
    assert routing.gate_bar(st3, GATE, "sonnet", "b1") == 0.8
    assert routing.gate_bar(st, {"min_n": 8, "min_first_time_pass": 0.8}, "sonnet", "b1") == 0.8


def test_gate_bar_null_rate_falls_back():
    st = {"bands_by_tier": {"sonnet|b1": {"n": 20, "ftp_rate": None}}}
    assert routing.gate_bar(st, GATE, "sonnet", "b1") == 0.8


def test_cheap_tier_at_baseline_keeps_haiku():
    st = stats({"n": 10, "ftp_rate": 0.75}, {"n": 20, "ftp_rate": 0.74})
    assert routing.pick_tier(FT, cfg(), st) == "haiku"


def test_cheap_tier_below_baseline_gated():
    st = stats({"n": 10, "ftp_rate": 0.70}, {"n": 20, "ftp_rate": 0.74})
    gated = []
    assert routing.pick_tier(FT, cfg(), st, gated) == "sonnet"
    assert gated == ["T1"]


def test_thin_baseline_uses_fixed_bar():
    st = stats({"n": 10, "ftp_rate": 0.78}, {"n": 3, "ftp_rate": 0.9})
    assert routing.pick_tier(FT, cfg(), st) == "sonnet"


def test_shipped_gate_has_baseline():
    assert routing.load_cfg()["stats_gate"] == GATE
