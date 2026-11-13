from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(p):
    return (ROOT / p).read_text()


def test_config_names_cap_keys():
    t = read("docs/config.md")
    assert "\n## Lead cap\n" in t
    sec = t.split("\n## Lead cap\n")[1].split("\n## ")[0]
    for w in ("room", "lead_units", "leads_per_repo", "leads_per_machine", "lead_weekly_max", "fixed cap 2", "cap:"):
        assert w in sec, w


def test_backlog_command_no_fixed_cap():
    t = read("commands/backlog.md")
    assert "capped at 2" not in t and "cap:" in t and "--cap N" in t


def test_fleet_points_to_config():
    line = next(l for l in read("docs/fleet.md").splitlines() if l.startswith("- Machine gate"))
    assert "docs/config.md" in line and "room" in line
