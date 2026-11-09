"""#333: `sl task Tn` names a one-word section by its capitalised word."""
import sys

import pytest

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import task  # noqa: E402
import plan_tools as pt  # noqa: E402

SEC = "## Design\nbody"


def mk(sections: str, body: str = "", extra: str = "", tid: str = "T2") -> pt.Plan:
    return pt.Plan(
        f"# Plan\n\n{sections}\n\n## Package\n\n### T1 First\n**Owns:** a.py\n**Produces:** a.f() -> int\n\n"
        f"### {tid} Second\n**Owns:** b.py\n{extra}\n{body}\n"
    )


def secs(plan, tid="T2"):
    return task.referenced_sections(plan, plan.by_id[tid])


def test_issue_333_per_design():
    p = mk(SEC, "**Notes:** implement per Design.\n**Steps:** 1 test, 2 implement per Design")
    assert secs(p) == [SEC]
    assert "## Plan sections this task names\n\n## Design\nbody" in task.render(p, "T2")


@pytest.mark.parametrize("body", ["**Covers:** Design 1", "sections 1 to 6 under Design.", "see Design 2)",
                                  "the Design's rule", "both Designs", "(Design)"])
def test_capitalised_mentions(body):
    assert secs(mk(SEC, body)) == [SEC]


@pytest.mark.parametrize("body", ["**Kind:** design", "design the parser", "a redesign", "the Designer",
                                  "Design-time check", "call `Design.render()` here", "```\nper Design\n```"])
def test_not_a_mention(body):
    assert secs(mk(SEC, body)) == []
    assert secs(mk(SEC, "", extra=body)) == []


def test_field_label_not_a_mention():
    assert secs(mk("## Notes\nshared notes", "**Notes:** do x")) == []
    assert secs(mk("## Notes\nshared notes", "**Notes:** see Notes above")) == ["## Notes\nshared notes"]


def test_lowercase_heading_explicit_only():
    assert secs(mk("## design\nbody", "per Design")) == []
    assert secs(mk("## design\nbody", "per design")) == []
    assert secs(mk("## design\nbody", "design section")) == ["## design\nbody"]


@pytest.mark.parametrize("body", ["design sections 1 to 7", "sections design"])
def test_explicit_plural_sections(body):
    assert secs(mk("## design\nbody", body)) == ["## design\nbody"]


def test_acronym_heading():
    api = "## API\nGET /x"
    assert secs(mk(api, "call the API")) == [api]
    assert secs(mk(api, "call the api")) == []
    assert secs(mk(api, "the APIs")) == [api]


def test_skeleton_and_constraints_never():
    assert secs(mk("## Coverage\ncov\n\n## Self-review\nsr", "per Coverage and Self-review")) == []


def test_multiword_unchanged():
    assert secs(mk("## Shared helper\nx", "Use the shared helper.")) == ["## Shared helper\nx"]
    assert secs(mk("## Shared helper\nx", "Shared")) == []


def test_heading_phrase_lower_keyword():
    assert pt.heading_phrase("2. The `Design`:", lower=False) == "The Design"
    assert pt.heading_phrase("2. The `Design`:") == "the design"
    assert pt.heading_phrase("**Design**") == "design"
    assert pt.heading_phrase("1.2 Wire  Format", lower=False) == "Wire Format"
