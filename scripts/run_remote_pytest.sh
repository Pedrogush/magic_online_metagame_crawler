#!/usr/bin/env bash
set -euo pipefail

HOST="${1:?Host (user@host) is required as the first argument}"
REPO_PATH="${2:-/home/pedro/Documents/Projects/Codex/magic_online_metagame_crawler}"
BRANCH="${3:-refactor-deck-selector-architecture-011CV2pbBY7A3j4q2Mfx55c4}"
REMOTE_PYTEST_ARGS="${4:-}"

: "${SSH_CLIENT:=}"  # avoid unused check

echo "Connecting to ${HOST}..."
ssh "${HOST}" bash <<EOF
set -euo pipefail
cd "${REPO_PATH}"
git fetch origin
git checkout "${BRANCH}"
git pull origin "${BRANCH}"
echo "Running pytest on ${HOST}:${REPO_PATH} (${BRANCH})..."
pytest ${REMOTE_PYTEST_ARGS}
EOF
