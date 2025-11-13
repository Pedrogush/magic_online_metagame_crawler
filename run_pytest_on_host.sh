#!/bin/bash

# Configuration file location
CONFIG_FILE="${HOME}/.ssh/pytest_host.conf"

# Load configuration
if [ -f "$CONFIG_FILE" ]; then
    source "$CONFIG_FILE"
else
    echo "Error: Configuration file not found at $CONFIG_FILE"
    echo "Please create it with: HOST_USER, HOST_IP, PYTEST_PATH, PROJECT_PATH"
    exit 1
fi

# Validate required variables
if [ -z "$HOST_USER" ] || [ -z "$HOST_IP" ] || [ -z "$PYTEST_PATH" ] || [ -z "$PROJECT_PATH" ]; then
    echo "Error: Missing required configuration variables"
    exit 1
fi

# Auto-detect Windows host IP from VM/WSL gateway
# NOTE: VM/WSL assigns a new IP to the Windows host on each reboot
# Try to detect from eth0 first (common in WSL), then fall back to default gateway
DETECTED_IP=""

# Check for eth0 gateway (WSL/VM common interface)
if ip route show dev eth0 &>/dev/null; then
    DETECTED_IP=$(ip route show dev eth0 | grep default | awk '{print $3}')
fi

# Fall back to default gateway if eth0 not found
if [ -z "$DETECTED_IP" ]; then
    DETECTED_IP=$(ip route show | grep default | head -1 | awk '{print $3}')
fi

if [ -n "$DETECTED_IP" ]; then
    # Test if detected IP is actually reachable on port 22
    if timeout 2 bash -c "echo >/dev/tcp/$DETECTED_IP/22" 2>/dev/null; then
        echo "Auto-detected Windows host IP: $DETECTED_IP (verified reachable)"
        if [ "$DETECTED_IP" != "$HOST_IP" ]; then
            echo "Note: Configured IP ($HOST_IP) differs from detected IP"
            echo "Using auto-detected IP: $DETECTED_IP"
        fi
        HOST_IP="$DETECTED_IP"
    else
        echo "Auto-detected IP $DETECTED_IP is not reachable on port 22"
        echo "Using configured IP: $HOST_IP"
    fi
else
    echo "Could not auto-detect host IP, using configured IP: $HOST_IP"
fi

# SSH key path (default to id_ed25519, can be overridden in config)
SSH_KEY="${SSH_KEY:-${HOME}/.ssh/id_ed25519}"

# Ensure we're inside a git repository so we can detect the current branch
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "Error: This script must be run from within the git repository."
    exit 1
fi

# Detect the current branch we are working on
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$CURRENT_BRANCH" = "HEAD" ]; then
    echo "Error: Detached HEAD detected. Please checkout a branch before running remote pytest."
    exit 1
fi

REMOTE_URL=$(git config --get remote.origin.url)
if [ -z "$REMOTE_URL" ]; then
    echo "Error: Unable to determine remote.origin.url for this repository."
    exit 1
fi

CURRENT_COMMIT=$(git rev-parse --short HEAD)

# Additional pytest arguments passed to this script (escaped for remote execution)
PYTEST_ARGS_ESCAPED=""
if [ "$#" -gt 0 ]; then
    PYTEST_ARGS_ESCAPED=$(printf ' %q' "$@")
fi

echo "Connecting to $HOST_USER@$HOST_IP..."
echo "Running pytest for branch: $CURRENT_BRANCH ($CURRENT_COMMIT)"
echo "Remote origin: $REMOTE_URL"
echo "Configured project path on host: $PROJECT_PATH"
echo ""

# Optional: export KEEP_REMOTE_TEMP_DIR=1 before running to inspect the remote workspace afterwards
KEEP_FLAG="${KEEP_REMOTE_TEMP_DIR:-}"

# SSH into Windows host, create a temporary clean workspace, sync to the current branch, and run pytest
ssh -i "$SSH_KEY" \
    -o StrictHostKeyChecking=ask \
    -o PasswordAuthentication=no \
    "$HOST_USER@$HOST_IP" \
    bash -s -- \
    "$CURRENT_BRANCH" \
    "$REMOTE_URL" \
    "$PROJECT_PATH" \
    "$PYTEST_PATH" \
    "$PYTEST_ARGS_ESCAPED" \
    "$KEEP_FLAG" <<'REMOTE_PYTEST_SCRIPT'
set -euo pipefail

BRANCH="$1"
REMOTE_URL="$2"
PROJECT_PATH="$3"
PYTEST_PATH="$4"
PYTEST_ARGS_ESCAPED="$5"
KEEP_REMOTE_TEMP_DIR="${6:-}"

cleanup() {
    TARGET_DIR="${TEMP_ROOT:-${TEMP_DIR:-}}"
    if [ -n "$TARGET_DIR" ] && [ -d "$TARGET_DIR" ]; then
        if [ -n "${KEEP_REMOTE_TEMP_DIR:-}" ]; then
            echo "KEEP_REMOTE_TEMP_DIR set; leaving remote workspace at: ${TEMP_DIR:-$TARGET_DIR}"
            return
        fi
        rm -rf "$TARGET_DIR"
    fi
}
trap cleanup EXIT

if [ -z "${PROJECT_PATH:-}" ]; then
    echo "Error: PROJECT_PATH not provided in remote environment."
    exit 1
fi

WORKSPACE_PARENT=$(dirname "$PROJECT_PATH")
RUNS_DIR="$WORKSPACE_PARENT/.codex_pytest_runs"
mkdir -p "$RUNS_DIR"

if command -v mktemp >/dev/null 2>&1; then
    if ! TEMP_ROOT=$(mktemp -d "$RUNS_DIR/run_XXXXXX" 2>/dev/null); then
        TEMP_ROOT=$(mktemp -d)
    fi
else
    TEMP_ROOT="$RUNS_DIR/run_$(date +%s)_$$"
    mkdir -p "$TEMP_ROOT"
fi

TEMP_DIR="$TEMP_ROOT/workspace"

echo "Created remote temp workspace: $TEMP_DIR"
echo "Cloning repository: $REMOTE_URL"
git clone "$REMOTE_URL" "$TEMP_DIR"
cd "$TEMP_DIR"

echo "Checking out branch '$BRANCH'..."
if git fetch origin "$BRANCH"; then
    git checkout -B "$BRANCH" "origin/$BRANCH"
    git reset --hard "origin/$BRANCH"
else
    echo "Error: Branch '$BRANCH' not found on origin '$REMOTE_URL'."
    echo "Please push the branch before running remote pytest."
    exit 1
fi

echo "Running pytest via: $PYTEST_PATH$PYTEST_ARGS_ESCAPED"
if [ -n "$PYTEST_ARGS_ESCAPED" ]; then
    eval "set -- $PYTEST_ARGS_ESCAPED"
    PYTEST_ARGS_ACTUAL=("$@")
    "$PYTEST_PATH" "${PYTEST_ARGS_ACTUAL[@]}"
else
    "$PYTEST_PATH"
fi
REMOTE_PYTEST_SCRIPT

# Capture exit code from pytest
EXIT_CODE=$?

echo ""
echo "Pytest finished with exit code: $EXIT_CODE"
exit $EXIT_CODE
