#!/usr/bin/env bash
set -euo pipefail
mkdir -p src/app tests
cat > pyproject.toml <<'TOML'
[project]
name = "app"
version = "0.1.0"
requires-python = ">=3.10"

[tool.pytest.ini_options]
pythonpath = ["src"]
TOML
echo '"""app."""' > src/app/__init__.py
cat > tests/test_app.py <<'PY'
import app


def test_import():
    assert app is not None
PY
