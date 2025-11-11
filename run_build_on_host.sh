#!/bin/bash

# Configuration file location
CONFIG_FILE="${HOME}/.ssh/pytest_host.conf"

# Load configuration
if [ -f "$CONFIG_FILE" ]; then
    source "$CONFIG_FILE"
else
    echo "Error: Configuration file not found at $CONFIG_FILE"
    echo "Please create it with: HOST_USER, HOST_IP, PROJECT_PATH, BUILD_COMMAND"
    exit 1
fi

# Validate required variables
if [ -z "$HOST_USER" ] || [ -z "$HOST_IP" ] || [ -z "$PROJECT_PATH" ] || [ -z "$BUILD_COMMAND" ]; then
    echo "Error: Missing required configuration variables"
    exit 1
fi

# SSH key path (default to id_ed25519, can be overridden in config)
SSH_KEY="${SSH_KEY:-${HOME}/.ssh/id_ed25519}"

# Additional build arguments passed to this script
BUILD_ARGS="$@"

echo "Connecting to $HOST_USER@$HOST_IP..."
echo "Running build on: $PROJECT_PATH"
echo ""

ssh -i "$SSH_KEY" \
    -o StrictHostKeyChecking=ask \
    -o PasswordAuthentication=no \
    "$HOST_USER@$HOST_IP" \
    "cd \"$PROJECT_PATH\" && git pull --ff-only && $BUILD_COMMAND $BUILD_ARGS"

EXIT_CODE=$?

echo ""
echo "Build finished with exit code: $EXIT_CODE"
exit $EXIT_CODE
