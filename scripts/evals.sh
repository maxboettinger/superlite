#!/usr/bin/env bash
# evals.sh - run the eval suite against the plugin in this repo.
# Usage: scripts/evals.sh [claude plugin eval args, e.g. --case brainstorm-first --runs 1]
# A red run reruns, once, each failing case whose with-plugin runs disagreed.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p evals/results
run() {
  claude plugin eval . --trust-plugin --no-publish --scaffold --judge-model haiku --max-cost-usd 5 \
    --allow-tools "Bash(pytest:*)" "Bash(python3:*)" Edit Write "$@"
}
rm -f evals/results/last.json
rc=0
run --json evals/results/last.json "$@" || rc=$?
[ "$rc" -eq 1 ] || exit "$rc"
cases=$(python3 scripts/evals_retry.py evals/results/last.json) || exit 1
for c in $cases; do
  echo "evals: retry once: $c (its runs disagreed)" >&2
  run "$@" --case "$c" --json "evals/results/retry-$c.json" || exit 1
done
echo "evals: green after one retry of: $(echo $cases)" >&2
