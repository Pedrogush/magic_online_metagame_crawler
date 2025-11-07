#!/bin/bash
set -euo pipefail

# Only run this hook in remote/web environments
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

echo "Installing Python dependencies..."

# Install core dependencies that work on Linux
# Skip GUI dependencies (pyautogui, pynput) that are Windows/Mac-specific
# and pythonnet which requires .NET runtime
pip install --quiet \
  loguru \
  pillow \
  pytesseract \
  curl_cffi \
  beautifulsoup4 \
  pymongo \
  pytest 2>&1 | grep -v "WARNING:" || true

# Set PYTHONPATH to include the project root and package directories
echo 'export PYTHONPATH="$CLAUDE_PROJECT_DIR:$CLAUDE_PROJECT_DIR/widgets:$CLAUDE_PROJECT_DIR/navigators:$CLAUDE_PROJECT_DIR/utils"' >> "$CLAUDE_ENV_FILE"

echo "✓ Dependencies installed successfully!"
echo "Note: GUI dependencies (pyautogui, pynput) and pythonnet skipped on Linux"
