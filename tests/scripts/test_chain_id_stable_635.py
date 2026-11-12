import hashlib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"))

import shape  # noqa: E402
from test_0_3_1_scripts import _chain_id, _chain_plan, run  # noqa: E402,F401


def test_chain_id_ignores_minutes():
    assert shape.chain_id(["T1", "T2", "T3"], [1.0, 2.0, 3.0]) == shape.chain_id(["T1", "T2", "T3"], [4.0, 5.5, 9.0])


def test_chain_id_ignores_order():
    assert shape.chain_id(["T3", "T1", "T2"]) == shape.chain_id(["T1", "T2", "T3"])


def test_chain_id_value():
    assert shape.chain_id(["T2", "T1", "T3"]) == "chain-" + hashlib.sha1(b"T1|T2|T3").hexdigest()[:4]


def test_chain_id_differs_for_other_members():
    assert shape.chain_id(["T1", "T2", "T4"]) != shape.chain_id(["T1", "T2", "T3"])


def test_lint_chain_id_survives_a_minutes_edit(tmp_path):
    plan = _chain_plan(tmp_path)
    args = ("plan_tools", "lint", "--plan", plan, "--stated", "--max-task-min", "10")
    cid = _chain_id(run(*args).stdout)
    text = plan.read_text(encoding="utf-8")
    plan.write_text(text + f"\nRuling: sequential [{cid}] - one shared parser\n", encoding="utf-8")
    edited = re.sub(r"(### T2 .*?\*\*Est\. time:\*\* )5 min", r"\g<1>8 min", plan.read_text(encoding="utf-8"), count=1, flags=re.S)
    assert edited != plan.read_text(encoding="utf-8")
    plan.write_text(edited, encoding="utf-8")
    out = run(*args).stdout
    assert "CHAIN [" not in out
    assert f"NOTE: accepted Ruling: sequential [{cid}]" in out
