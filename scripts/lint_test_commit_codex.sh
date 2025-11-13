#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

echo "================================================"
echo "Codex: Step 1 - Running linters"
echo "================================================"

echo "Running Black..."
if ! python3 -m black --check .; then
    echo "Black formatting issues detected; applying fixes..."
    python3 -m black .
    echo "Black formatting applied."
fi

echo ""
echo "Running Ruff..."
if ! python3 -m ruff check .; then
    echo "Ruff detected issues; attempting auto-fix..."
    python3 -m ruff check --fix .
    echo "Ruff fixes applied."
fi

echo ""
echo "================================================"
echo "Codex: Step 2 - Running pytest on host"
echo "================================================"

PYTEST_OUTPUT_FILE="/tmp/pytest_codex_$$.txt"
PYTEST_EXIT_CODE=0

if ./run_pytest_on_host.sh -v 2>&1 | tee "$PYTEST_OUTPUT_FILE"; then
    echo "✅ pytest succeeded"
else
    PYTEST_EXIT_CODE=$?
    echo ""
    echo "================================================"
    echo "Codex: Tests failed"
    echo "================================================"
    cat "$PYTEST_OUTPUT_FILE"
    echo ""
    echo "Fix these errors in tests, then push and commit to remote."
    rm -f "$PYTEST_OUTPUT_FILE"
    exit "$PYTEST_EXIT_CODE"
fi

echo ""
echo "================================================"
echo "Codex: Step 3 - Commit + push"
echo "================================================"

if git diff --quiet && git diff --cached --quiet; then
    echo "No changes to commit."
else
    git add -A
    git commit -m "Codex: run lint/test workflow"
    git push
    echo ""
    echo "✅ Codex lint/test workflow committed and pushed."
fi

rm -f "$PYTEST_OUTPUT_FILE"

echo ""
echo "================================================"
echo "Codex workflow complete"
echo "================================================"
