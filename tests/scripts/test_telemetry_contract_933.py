"""Every telemetry kind has a test that asserts a line of it (#933): `test_kind_<kind>_<case>`."""
import re
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import telemetry  # noqa: E402

HERE = Path(__file__).resolve().parent


def _kind_tests() -> set[str]:
    names = set()
    for path in HERE.glob("test_telemetry*.py"):
        if path.name != Path(__file__).name:
            names |= set(re.findall(r"^\s*def (test_kind_\w+)\(", path.read_text(encoding="utf-8"), re.M))
    return names


def test_every_kind_has_a_test():
    names = _kind_tests()
    missing = [k for k in telemetry.KINDS if not any(n.startswith(f"test_kind_{k}_") for n in names)]
    assert missing == [], f"kinds without a test_kind_<kind>_<case> test: {missing}"


def test_kind_names_are_known():
    names = _kind_tests()
    unknown = [n for n in names if not any(n.startswith(f"test_kind_{k}_") for k in telemetry.KINDS)]
    assert unknown == [], f"test_kind_ tests for no known kind: {unknown}"
