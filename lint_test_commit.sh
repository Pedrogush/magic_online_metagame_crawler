#!/bin/bash

# Lint, Test, and Commit workflow
# This script runs linting, tests, and handles commits with automatic test fixes

set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

echo "================================================"
echo "Step 1: Running linters (Black + Ruff)"
echo "================================================"

# Run black
echo "Running Black..."
if ! python3 -m black --check .; then
    echo "Black formatting issues found. Applying fixes..."
    python3 -m black .
    echo "Black formatting applied."
fi

# Run ruff
echo "Running Ruff..."
if ! python3 -m ruff check .; then
    echo "Ruff found issues. Attempting auto-fix..."
    python3 -m ruff check --fix .
    echo "Ruff fixes applied."
fi

echo ""
echo "================================================"
echo "Step 2: Running pytest on host machine"
echo "================================================"

# Capture pytest output to both display and file
PYTEST_OUTPUT_FILE="/tmp/pytest_output_$$.txt"
if ./run_pytest_on_host.sh -v 2>&1 | tee "$PYTEST_OUTPUT_FILE"; then
    PYTEST_PASSED=true
    PYTEST_EXIT_CODE=0
else
    PYTEST_PASSED=false
    PYTEST_EXIT_CODE=$?
fi

echo ""
echo "================================================"
echo "Step 3: Handling results"
echo "================================================"

if [ "$PYTEST_PASSED" = false ]; then
    echo "❌ Tests failed (exit code: $PYTEST_EXIT_CODE)"
    echo ""
    echo "Spawning Claude session to fix test failures..."
    echo ""

    # Create a temporary file with instructions for Claude
    CLAUDE_PROMPT_FILE="/tmp/claude_pytest_fix_$$.txt"
    cat > "$CLAUDE_PROMPT_FILE" <<EOF
The pytest suite has failing tests. Please analyze the test output below, fix all failing tests, and commit the fixes.

PYTEST OUTPUT:
================================================================================
$(cat "$PYTEST_OUTPUT_FILE")
================================================================================

Instructions:
1. Analyze the test failures above
2. Fix the code to make all tests pass
3. Run the tests again to verify the fixes work
4. Once all tests pass, create a commit with a descriptive message about the fixes
5. Push the changes to remote

Focus on fixing the actual issues in the code, not just making the tests pass superficially.
EOF

    # Spawn Claude with the prompt
    claude-code --dangerously-skip-permissions --prompt "$(cat "$CLAUDE_PROMPT_FILE")"

    # Cleanup
    rm -f "$CLAUDE_PROMPT_FILE"
    rm -f "$PYTEST_OUTPUT_FILE"

else
    echo "✅ All tests passed!"
    echo ""

    # Check if there are any changes to commit
    if git diff --quiet && git diff --cached --quiet; then
        echo "No changes to commit."
    else
        echo "Creating commit with linting changes..."

        # Stage all changes
        git add -A

        # Get list of changed files for commit message
        CHANGED_FILES=$(git diff --cached --name-only | wc -l)

        # Create commit
        git commit -m "Apply linting fixes from Black and Ruff

- Formatted with Black
- Fixed linting issues with Ruff
- All tests passing ($CHANGED_FILES files changed)"

        echo ""
        echo "Pushing to remote..."
        git push

        echo ""
        echo "✅ Changes committed and pushed successfully!"
    fi

    rm -f "$PYTEST_OUTPUT_FILE"
fi

echo ""
echo "================================================"
echo "Workflow complete"
echo "================================================"
