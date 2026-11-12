"""#594/B145: plain-edge seams, probe parameter types, forecast inputs note."""
from __future__ import annotations

import json
import os
import subprocess
import sys

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import fleet_io as io  # noqa: E402
import next_tasks as nt  # noqa: E402
import plan_tools as ptm  # noqa: E402

PLAN_TOOLS = SCRIPTS / "plan_tools.py"

READING = """# Plan
**Goal:** x.

```mermaid
%% taskgraph
flowchart LR
  T1 --> T2
```

### T1 read the spec · Complexity 3 · Est. context 30k
**Owns:** none

### T2 build · Complexity 3 · Est. context 30k
**Owns:** src/app/b.py
"""

PROBE = """# Plan
**Goal:** x.

```mermaid
%% taskgraph
flowchart LR
  T1 --> T2
```

### T1 metrics · Complexity 3 · Est. context 30k
**Owns:** src/m.py
**Produces:** m.measurement_counts(counts: dict[str, int]) -> int

### T2 check · Complexity 3 · Est. context 30k
**Owns:** src/c.py
**Probe entry:** call=m.measurement_counts
"""

PROSE = {"time_factor": 2.0}


def env(tmp_path, **extra):
    e = dict(os.environ, PYTHONIOENCODING="utf-8", SUPERLITE_HOME=str(tmp_path / "home"), **extra)
    return e


def write(tmp_path, text):
    proj = tmp_path / "proj"
    (proj / ".superlite").mkdir(parents=True)
    (proj / ".git").mkdir()
    p = proj / "plan.md"
    p.write_text(text, encoding="utf-8")
    return proj, p


def run(tmp_path, proj, *args, **extra):
    return subprocess.run([sys.executable, str(PLAN_TOOLS), *args], capture_output=True, text=True, cwd=proj,
                          env=env(tmp_path, **extra), timeout=120)


def test_reading_task_edge_is_no_seam(tmp_path):
    proj, p = write(tmp_path, READING)
    r = run(tmp_path, proj, "taskgraph", "--plan", str(p), "--format", "full")
    assert json.loads(r.stdout)["seams"] == []
    assert not any(x.startswith("seam") for x in io.review_reasons(str(p), "T2"))


def test_seams_of_values():
    graph = {"T1": [], "T2": ["T1"]}
    plan = ptm.Plan.load  # noqa: F841
    assert ptm.seams_of(graph) == ["T1↔T2"]


def test_plain_edge_dropped_with_plan(tmp_path):
    _, p = write(tmp_path, READING)
    plan = ptm.Plan.load(str(p))
    assert ptm.seams_of({"T1": [], "T2": ["T1"]}, plan) == []
    assert ptm.seams_of({"T8": [], "T9": ["T8"]}, plan) == ["T8↔T9"]


def test_file_owning_edge_stays_seam(tmp_path):
    _, p = write(tmp_path, READING.replace("**Owns:** none", "**Owns:** src/a.py"))
    assert ptm.seams_of({"T1": [], "T2": ["T1"]}, ptm.Plan.load(str(p))) == ["T1↔T2"]


def test_next_tasks_full_drops_plain_edge(tmp_path):
    _, p = write(tmp_path, READING)
    nt._GRAPHS.clear()
    assert nt.taskgraph_full(str(p))["seams"] == []


def test_dict_param_call_rejected(tmp_path):
    proj, p = write(tmp_path, PROBE)
    out = run(tmp_path, proj, "lint", "--plan", str(p)).stdout
    assert ("PROBE: call=m.measurement_counts takes counts: dict[str, int]; probes pass one text argument (str)") in out


def test_text_param_issue_values():
    f = ptm.text_param_issue
    assert f("counts: dict[str, int]") == "counts: dict[str, int]"
    assert f("text: str") is None
    assert f("raw") is None
    assert f("s: Optional[str], n: int = 3") is None
    assert f("self, ref: 'str | None'", method=True) is None
    assert f("x: Any") is None
    assert f("x: Union[str, None]") is None
    assert f("x: typing.Optional[str]") is None
    assert f("x: None | str") is None


def test_str_param_call_passes(tmp_path):
    proj, p = write(tmp_path, PROBE.replace("dict[str, int]", "str"))
    assert "PROBE:" not in run(tmp_path, proj, "lint", "--plan", str(p)).stdout


def test_forecast_inputs_note_values():
    f = ptm.forecast_inputs_note
    assert f({"time": {}}) == "inputs: live inputs off (test minutes and contention not read)"
    live = {"tests": {"fast_min": None, "full_min": 4, "full_source": "test-cmd.json", "slots": 3},
            "contention": {"factor": 1.0, "slots": 3}}
    assert f({"prose": PROSE, "live": live}) == "inputs: fast test minutes missing (no test-cmd.json run_min, under 3 ledger runs)"
    live2 = {"tests": {"fast_min": 1, "full_min": 4, "full_source": "test-cmd.json", "slots": None},
             "contention": {"factor": 1.5, "slots": 2}}
    assert f({"live": live2}) == "inputs: contention x1.5 (default 2 build slots); prose x2.0 time, x3.0 calls (built-in default)"
    assert f({"prose": PROSE, "live": live2 | {"tests": dict(live2["tests"], slots=2)}}) == ""


def test_lint_line_names_inputs(tmp_path):
    feat = "\n**Components:** 1\n**LOC owned:** 50\n**Tests:** fast"
    proj, p = write(tmp_path, READING.replace("**Owns:** none", "**Owns:** src/a.py" + feat).replace("**Owns:** src/app/b.py", "**Owns:** src/app/b.py" + feat))
    out = run(tmp_path, proj, "lint", "--stable", "--plan", str(p), SUPERLITE_FORECAST_LIVE="0").stdout
    assert "· inputs: live inputs off" in out
