"""#1097: package-reviewer.md runs mutation checks in a throwaway worktree under .superlite/, never in the shared tree."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MUTATION = "- Mutation checks: never break, revert or take out code in the shared tree to watch a test fail (a red-run proof, a fix's test run against the code before the fix): other tasks' `commit_task` calls and the coordinator's full run read those files while you work, and `commit_task` holds every changed file of your `Files in scope:` line until you report. Make a throwaway worktree of the reviewed checkpoint under `.superlite/` (never staged, never in `git status`): `git worktree add --detach .superlite/mutate/NAME <sha>` (NAME as for `--worker`; `<sha>` the newest one under your brief's `Commits:`, or its `Reviewed version:`), copy in the test files it lacks, break the code there, `cd` into it and run `<abs sl> run_tests --fast PATHS --worker NAME` to see the failure, then `cd` back to `Root:` and `git worktree remove --force .superlite/mutate/NAME`. The shared tree only ever holds your fix and its test."
RED = "- A `Red runs (task reports):` section in your brief names tasks whose report shows no red run. Prove each new test of those tasks can fail before you accept it: break the code it tests in a mutation worktree (the `Mutation checks:` rule), see the test fail there for the right reason, and see it pass in the shared tree, where that code stays untouched. List each such test under tests added with that red run's summary line. A test that stays green is a finding: make it fail on the defect it guards, with its own red run."


def lines():
    return (ROOT / "agents/package-reviewer.md").read_text(encoding="utf-8").splitlines()


def test_mutation_rule_once_after_experiments():
    ls = lines()
    assert ls.count(MUTATION) == 1
    i = next(n for n, line in enumerate(ls) if line.startswith("- Experiments:"))
    assert ls[i + 1] == MUTATION


def test_red_run_proof_points_to_the_mutation_rule():
    ls = lines()
    assert ls.count(RED) == 1
    assert ls.index(RED) == ls.index(MUTATION) + 1
    assert not any("put the code back" in line for line in ls)
