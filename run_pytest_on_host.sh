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

# SSH key path (default to id_ed25519, can be overridden in config)
SSH_KEY="${SSH_KEY:-${HOME}/.ssh/id_ed25519}"

# Additional pytest arguments passed to this script
PYTEST_ARGS="$@"

echo "Connecting to $HOST_USER@$HOST_IP..."
echo "Running pytest on: $PROJECT_PATH"
echo ""

# SSH into Windows host and run pytest
# -i: specify identity file (SSH key)
# -o StrictHostKeyChecking=ask: prompt on first connection, then remember
# -o PasswordAuthentication=no: force key-based auth only
ssh -i "$SSH_KEY" \
    -o StrictHostKeyChecking=ask \
    -o PasswordAuthentication=no \
    "$HOST_USER@$HOST_IP" \
    "cd $PROJECT_PATH && $PYTEST_PATH $PYTEST_ARGS"

# Capture exit code from pytest
EXIT_CODE=$?

echo ""
echo "Pytest finished with exit code: $EXIT_CODE"
exit $EXIT_CODE
