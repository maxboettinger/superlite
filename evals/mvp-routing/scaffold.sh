#!/usr/bin/env bash
set -euo pipefail
mkdir -p tests
cat > pyproject.toml <<'TOML'
[project]
name = "readinglist"
version = "0.1.0"

[tool.pytest.ini_options]
pythonpath = ["src"]
TOML
