#!/usr/bin/env bash
set -euo pipefail
mkdir -p src/calc tests
cat > pyproject.toml <<'TOML'
[project]
name = "calc"
version = "0.1.0"

[tool.pytest.ini_options]
pythonpath = ["src"]
TOML
touch src/calc/__init__.py
cat > src/calc/core.py <<'PY'
def days_in_feb(year):
    return 28
PY
cat > tests/test_core.py <<'PY'
from calc.core import days_in_feb


def test_leap_year():
    assert days_in_feb(2024) == 29
PY
