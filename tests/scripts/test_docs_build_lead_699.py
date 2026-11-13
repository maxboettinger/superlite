# tests/scripts/test_docs_build_lead_699.py
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def holds(rel, *needles):
    t = (ROOT / rel).read_text()
    for n in needles:
        assert n in t, (rel, n)


def test_tools_md():
    holds("docs/tools.md", "lead.build_model", "DONE planned:", "building lead=", "Other shipped summaries")


def test_config_md():
    holds("docs/config.md", "lead.build_model", "lead.build_effort")


def test_backlog_md():
    holds("skills/subagent-driven-development/backlog.md", "lead.build_model", "Status: DONE planned: <plan>")


def test_experiments_md():
    holds("docs/experiments.md", "lead.build_model", "leads")
