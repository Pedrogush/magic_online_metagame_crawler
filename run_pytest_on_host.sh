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

# Additional pytest arguments passed to this script
PYTEST_ARGS="$@"

echo "Connecting to $HOST_USER@$HOST_IP..."
echo "Running pytest on: $PROJECT_PATH"
echo ""

# SSH into Windows host and run pytest
# -i: specify identity file (SSH key)
# -o StrictHostKeyChecking=ask: prompt on first connection, then remember
# -o PasswordAuthentication=no: force key-based auth only
# First pull latest changes, then run pytest
ssh -i "$SSH_KEY" \
    -o StrictHostKeyChecking=ask \
    -o PasswordAuthentication=no \
    "$HOST_USER@$HOST_IP" \
    "cd $PROJECT_PATH && git pull && $PYTEST_PATH $PYTEST_ARGS"

# Capture exit code from pytest
EXIT_CODE=$?

echo ""
echo "Pytest finished with exit code: $EXIT_CODE"
exit $EXIT_CODE
