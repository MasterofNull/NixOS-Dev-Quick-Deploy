#!/usr/bin/env bash
set -euo pipefail

################################################################################
# Setup Claude API Proxy
#
# This script:
# 1. Installs the systemd user service for claude-api-proxy
# 2. Updates claude-wrapper to set ANTHROPIC_BASE_URL
# 3. Configures shell environment
# 4. Starts the proxy service
################################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
# shellcheck source=../config/service-endpoints.sh
source "${PROJECT_ROOT}/config/service-endpoints.sh"
SYSTEMD_USER_DIR="${HOME}/.config/systemd/user"
WRAPPER_PATH="${HOME}/.npm-global/bin/claude-wrapper"
WRAPPER_BACKUP="${WRAPPER_PATH}.backup-$(date +%Y%m%d-%H%M%S)"

echo "========================================================================"
echo "Claude API Proxy Setup"
echo "========================================================================"
echo ""

# Step 1: Check prerequisites
echo "📋 Checking prerequisites..."

if [ ! -f "${PROJECT_ROOT}/scripts/claude-api-proxy.py" ]; then
    echo "❌ ERROR: claude-api-proxy.py not found"
    exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo "❌ ERROR: python3 not found"
    exit 1
fi

if [ ! -f "${WRAPPER_PATH}" ]; then
    echo "⚠️  WARNING: claude-wrapper not found at ${WRAPPER_PATH}"
    echo "   The proxy will work, but you'll need to manually set ANTHROPIC_BASE_URL"
    WRAPPER_EXISTS=0
else
    WRAPPER_EXISTS=1
fi

echo "✅ Prerequisites OK"
echo ""

# Step 2: Install systemd service
echo "📦 Installing systemd user service..."

mkdir -p "${SYSTEMD_USER_DIR}"

cat > "${SYSTEMD_USER_DIR}/claude-api-proxy.service" <<EOF
[Unit]
Description=Claude API Proxy - Routes Claude Code through local AI stack
After=network.target
Wants=network.target

[Service]
Type=simple
WorkingDirectory=${PROJECT_ROOT}
ExecStart=/usr/bin/env python3 ${PROJECT_ROOT}/scripts/claude-api-proxy.py
Restart=on-failure
RestartSec=5s

# Environment
Environment="HYBRID_COORDINATOR_URL=${HYBRID_URL}"
Environment="AIDB_MCP_URL=${AIDB_URL}"

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=claude-api-proxy

[Install]
WantedBy=default.target
EOF

echo "✅ Service file created: ${SYSTEMD_USER_DIR}/claude-api-proxy.service"
echo ""

# Step 3: Enable and start service
echo "🚀 Enabling and starting service..."

systemctl --user daemon-reload
systemctl --user enable claude-api-proxy.service
systemctl --user start claude-api-proxy.service

sleep 2

if systemctl --user is-active --quiet claude-api-proxy.service; then
    echo "✅ Service running"
else
    echo "❌ Service failed to start. Check logs:"
    echo "   journalctl --user -u claude-api-proxy.service -n 50"
    exit 1
fi

echo ""

# Step 4: Update claude-wrapper (if exists)
if [ "${WRAPPER_EXISTS}" = "1" ]; then
    echo "🔧 Updating claude-wrapper..."

    # Backup original
    cp "${WRAPPER_PATH}" "${WRAPPER_BACKUP}"
    echo "   Backup created: ${WRAPPER_BACKUP}"

    # Check if already configured
    if grep -q "ANTHROPIC_BASE_URL" "${WRAPPER_PATH}"; then
        echo "   Already configured (skipping)"
    else
        # Add environment variable before exec line
        sed -i '/^exec "${NODE_BIN}"/i \
# Route Claude API calls through local AI stack proxy\
export ANTHROPIC_BASE_URL="${ANTHROPIC_PROXY_URL}"\
' "${WRAPPER_PATH}"

        echo "✅ Wrapper updated"
    fi
    echo ""
fi

# Step 5: Configure shell environment (optional)
echo "💡 Optional: Add to your shell profile for manual Claude usage"
echo ""
echo "   For bash (~/.bashrc):"
echo "   echo 'export ANTHROPIC_BASE_URL=${ANTHROPIC_PROXY_URL}' >> ~/.bashrc"
echo ""
echo "   For zsh (~/.zshrc):"
echo "   echo 'export ANTHROPIC_BASE_URL=${ANTHROPIC_PROXY_URL}' >> ~/.zshrc"
echo ""

# Step 6: Verify setup
echo "========================================================================"
echo "✅ Setup Complete!"
echo "========================================================================"
echo ""
echo "📊 Service Status:"
systemctl --user status claude-api-proxy.service --no-pager -l | head -15
echo ""
echo "📝 Next Steps:"
echo ""
echo "1. Test the proxy manually:"
echo "   curl ${ANTHROPIC_PROXY_URL}/health"
echo ""
echo "2. View proxy logs:"
echo "   journalctl --user -u claude-api-proxy.service -f"
echo ""
echo "3. Restart VSCode/VSCodium for wrapper changes to take effect"
echo ""
echo "4. Monitor telemetry:"
echo "   tail -f ~/.local/share/nixos-ai-stack/telemetry/events-$(date +%Y-%m-%d).jsonl"
echo ""
echo "5. Check token savings on dashboard:"
echo "   ${DASHBOARD_URL}/dashboard.html"
echo ""
echo "🔧 Management Commands:"
echo "   systemctl --user status claude-api-proxy"
echo "   systemctl --user stop claude-api-proxy"
echo "   systemctl --user restart claude-api-proxy"
echo "   systemctl --user disable claude-api-proxy"
echo ""
echo "========================================================================"
