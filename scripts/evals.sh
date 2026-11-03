#!/usr/bin/env bash
# evals.sh - run the eval suite against the plugin in this repo.
# Usage: scripts/evals.sh [claude plugin eval args, e.g. --case brainstorm-first --runs 1]
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p evals/results
exec claude plugin eval . --trust-plugin --no-publish --scaffold --judge-model haiku --max-cost-usd 5 \
  --allow-tools "Bash(pytest:*)" "Bash(python3:*)" Edit Write --json evals/results/last.json "$@"
