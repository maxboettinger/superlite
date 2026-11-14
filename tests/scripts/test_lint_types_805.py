"""#805: lint rejects a type a Produces signature names that a task the producer does not depend on declares."""
from __future__ import annotations

from test_plan_tools import make_plan

import plan_tools

OFF = "**Wave0:** none"
ENUM = "state.MergeState(Enum)"
RUN = "merge.run(x: int) -> MergeState"


def types_lines(tmp_path, tasks, edges=(), header=OFF):
    p = make_plan(tmp_path, tasks, edges, header=header)
    plan = plan_tools.Plan.load(str(p))
    issues, _ = plan_tools.lint_plan(plan, plan_tools.build_parser().parse_args(["lint", "--plan", str(p)]))
    return [str(i) for i in issues if str(i).startswith("TYPES:")]


def test_consumer_declares_type(tmp_path):
    got = types_lines(tmp_path, [{"id": "T3", "produces": ENUM}, {"id": "T4", "produces": RUN}], [("T4", "T3")])
    assert got == ["TYPES: T4 Produces names MergeState, which T3 declares, and T3 depends on T4: "
                   "declare MergeState in T4 or in a task both depend on"]


def test_by_name_consume_declares(tmp_path):
    got = types_lines(tmp_path, [{"id": "T3"}, {"id": "T4", "consumes": "MergeState (T3, by name)", "produces": RUN}],
                      [("T4", "T3")])
    assert got == ["TYPES: T4 Produces names MergeState, which T3 declares, and T3 depends on T4: "
                   "declare MergeState in T4 or in a task both depend on"]


def test_parallel_unstubbed(tmp_path):
    got = types_lines(tmp_path, [{"id": "T3", "produces": ENUM}, {"id": "T4", "produces": RUN}])
    assert got == ["TYPES: T4 Produces names MergeState, which T3 declares; T4 does not depend on T3 and no Wave 0 stub "
                   "of T3 provides it: declare MergeState in T4, or add T3 --> T4"]


def test_parallel_stubbed_ok(tmp_path):
    tasks = [{"id": "T3", "owns": "src/pkg/state.py, tests/test_state.py", "produces": ENUM},
             {"id": "T4", "consumes": f"{ENUM} (T3)", "produces": RUN}]
    assert types_lines(tmp_path, tasks, header="") == []


def test_ancestor_or_self_ok(tmp_path):
    tasks = [{"id": "T3", "produces": ENUM}, {"id": "T4", "produces": RUN}]
    assert types_lines(tmp_path, tasks, [("T3", "T4")]) == []
    assert types_lines(tmp_path, [{"id": "T4", "produces": f"{ENUM} · {RUN}"}]) == []
