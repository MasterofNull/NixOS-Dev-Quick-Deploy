#!/usr/bin/env bash
#
# Enable Podman API on TCP port (for container access)
# This is needed for rootless Podman to listen on HTTP instead of just Unix socket
#
set -euo pipefail

echo "Enabling Podman API on TCP port 2375..."

# Create systemd user service for TCP API
mkdir -p ~/.config/systemd/user/

cat > ~/.config/systemd/user/podman-tcp.service <<'EOF'
[Unit]
Description=Podman API Service (TCP)
After=network-online.target
Wants=network-online.target

[Service]
Type=exec
ExecStart=/usr/bin/podman system service --time=0 tcp://127.0.0.1:2375
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF

# Reload systemd
systemctl --user daemon-reload

# Enable and start the service
systemctl --user enable podman-tcp.service
systemctl --user start podman-tcp.service

# Wait a moment for startup
sleep 2

# Test it works
if curl -s http://localhost:2375/v4.0.0/libpod/info > /dev/null 2>&1; then
    echo "✓ Success! Podman API is now listening on http://localhost:2375"
    echo
    echo "Test it:"
    echo "  curl http://localhost:2375/v4.0.0/libpod/info | jq .version"
else
    echo "✗ Failed to start TCP API"
    echo "Check logs: journalctl --user -u podman-tcp.service"
    exit 1
fi
