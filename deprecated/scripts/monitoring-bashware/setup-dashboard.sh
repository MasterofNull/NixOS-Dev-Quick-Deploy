#!/run/current-system/sw/bin/bash
# Dashboard Setup Script for NixOS Quick Deploy
# Installs and configures the System Command Center dashboard
# as part of the deployment process

set -euo pipefail

# Colors
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
USER_HOME="${HOME}"
DATA_DIR="${USER_HOME}/.local/share/nixos-system-dashboard"
SYSTEMD_USER_DIR="${USER_HOME}/.config/systemd/user"

# Source centralized service endpoints (optional)
# shellcheck source=config/service-endpoints.sh
if [[ -f "${SCRIPT_DIR}/config/service-endpoints.sh" ]]; then
    source "${SCRIPT_DIR}/config/service-endpoints.sh"
fi

detect_runtime() {
    if command -v kubectl >/dev/null 2>&1; then
        if [[ -n "${KUBECONFIG:-}" ]] || [[ -f /etc/rancher/k3s/k3s.yaml ]]; then
            echo "k8s"
            return
        fi
    fi
    if command -v podman >/dev/null 2>&1; then
        echo "podman"
        return
    fi
    if command -v docker >/dev/null 2>&1; then
        echo "docker"
        return
    fi
    echo ""
}

RUNTIME_MODE="$(detect_runtime)"

echo -e "${CYAN}🎛️  Setting up System Command Center Dashboard...${NC}"

# Create directories
mkdir -p "$DATA_DIR"
mkdir -p "$SYSTEMD_USER_DIR"

# Create systemd service for data collection
cat > "$SYSTEMD_USER_DIR/dashboard-collector.service" <<EOF
[Unit]
Description=System Dashboard Data Collector
After=network.target

[Service]
Type=oneshot
ExecStart=${SCRIPT_DIR}/scripts/generate-dashboard-data.sh
Environment="DASHBOARD_MODE=${RUNTIME_MODE}"
Environment="AI_STACK_NAMESPACE=${AI_STACK_NAMESPACE:-ai-stack}"
Environment="KUBECONFIG=${KUBECONFIG:-/etc/rancher/k3s/k3s.yaml}"
Environment="PATH=/run/current-system/sw/bin:/usr/bin:/bin:%h/.nix-profile/bin:%h/.local/state/nix/profiles/home-manager/bin"
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
LockPersonality=true
MemoryDenyWriteExecute=true
UMask=0077

[Install]
WantedBy=default.target
EOF

# Create systemd timer for periodic collection
cat > "$SYSTEMD_USER_DIR/dashboard-collector.timer" <<EOF
[Unit]
Description=Run dashboard collector every 15 seconds

[Timer]
OnBootSec=10s
OnUnitActiveSec=15s
AccuracySec=2s
RandomizedDelaySec=2s
Persistent=true

[Install]
WantedBy=timers.target
EOF

# Create systemd service for dashboard HTTP server
cat > "$SYSTEMD_USER_DIR/dashboard-server.service" <<EOF
[Unit]
Description=System Dashboard HTTP Server
After=network.target

[Service]
Type=simple
WorkingDirectory=${SCRIPT_DIR}
ExecStart=${SCRIPT_DIR}/scripts/serve-dashboard.sh
Restart=on-failure
RestartSec=5s
Environment="DASHBOARD_PORT=${DASHBOARD_PORT:-8888}"
Environment="DASHBOARD_BIND_ADDRESS=${DASHBOARD_BIND_ADDRESS:-127.0.0.1}"
Environment="SERVICE_HOST=${SERVICE_HOST:-localhost}"
Environment="DASHBOARD_MODE=${RUNTIME_MODE}"
Environment="AI_STACK_NAMESPACE=${AI_STACK_NAMESPACE:-ai-stack}"
Environment="KUBECONFIG=${KUBECONFIG:-/etc/rancher/k3s/k3s.yaml}"
Environment="PATH=/run/current-system/sw/bin:/usr/bin:/bin:%h/.nix-profile/bin"
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
LockPersonality=true
MemoryDenyWriteExecute=true
UMask=0077

[Install]
WantedBy=default.target
EOF

# Create systemd service for dashboard FastAPI backend (host mode only)
if [[ "$RUNTIME_MODE" != "k8s" ]]; then
cat > "$SYSTEMD_USER_DIR/dashboard-api.service" <<EOF
[Unit]
Description=System Dashboard FastAPI Backend
After=network.target

[Service]
Type=simple
WorkingDirectory=${SCRIPT_DIR}/dashboard/backend
ExecStart=${SCRIPT_DIR}/scripts/serve-dashboard-api.sh
Restart=on-failure
RestartSec=5s
Environment="DASHBOARD_API_PORT=8889"
Environment="DASHBOARD_API_BIND_ADDRESS=${DASHBOARD_API_BIND_ADDRESS:-127.0.0.1}"
Environment="PATH=/run/current-system/sw/bin:/usr/bin:/bin:%h/.nix-profile/bin"
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
LockPersonality=true
MemoryDenyWriteExecute=true
UMask=0077

[Install]
WantedBy=default.target
EOF
else
# K3s mode: use in-cluster dashboard-api and a port-forward if needed
cat > "$SYSTEMD_USER_DIR/dashboard-api-proxy.service" <<EOF
[Unit]
Description=System Dashboard API K3s Port Forward
After=network.target

[Service]
Type=simple
ExecStart=/run/current-system/sw/bin/kubectl --request-timeout=60s --address=${DASHBOARD_API_BIND_ADDRESS:-127.0.0.1} -n ${AI_STACK_NAMESPACE:-ai-stack} port-forward svc/dashboard-api ${DASHBOARD_API_PORT:-8889}:8889
Restart=on-failure
RestartSec=5s
Environment="PATH=/run/current-system/sw/bin:/usr/bin:/bin:%h/.nix-profile/bin"
Environment="KUBECONFIG=${KUBECONFIG:-/etc/rancher/k3s/k3s.yaml}"
Environment="DASHBOARD_API_BIND_ADDRESS=${DASHBOARD_API_BIND_ADDRESS:-127.0.0.1}"
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
LockPersonality=true
MemoryDenyWriteExecute=true
UMask=0077

[Install]
WantedBy=default.target
EOF
fi

echo -e "${GREEN}✅ Systemd service files created${NC}"

# Reload systemd user daemon
systemctl --user daemon-reload

# Enable services (but don't start yet - let user decide)
systemctl --user enable dashboard-collector.timer
systemctl --user enable dashboard-server.service
if [[ "$RUNTIME_MODE" == "k8s" ]]; then
    systemctl --user enable dashboard-api-proxy.service
else
    systemctl --user enable dashboard-api.service
fi

echo -e "${GREEN}✅ Systemd services enabled${NC}"

# Generate initial dashboard data
echo -e "${CYAN}📊 Generating initial dashboard data...${NC}"
"$SCRIPT_DIR/scripts/generate-dashboard-data.sh"
echo -e "${GREEN}✅ Initial data generated${NC}"

# Create desktop launcher (if in desktop environment)
if [[ -n "${XDG_DATA_HOME:-}" ]] || [[ -d "${USER_HOME}/.local/share/applications" ]]; then
    APPS_DIR="${XDG_DATA_HOME:-${USER_HOME}/.local/share}/applications"
    mkdir -p "$APPS_DIR"

    cat > "$APPS_DIR/nixos-dashboard.desktop" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=NixOS System Dashboard
Comment=Cyberpunk-themed system monitoring dashboard
Exec=xdg-open http://${SERVICE_HOST:-localhost}:${DASHBOARD_PORT:-8888}/dashboard.html
Icon=utilities-system-monitor
Terminal=false
Categories=System;Monitor;
StartupNotify=false
EOF

    chmod +x "$APPS_DIR/nixos-dashboard.desktop"
    echo -e "${GREEN}✅ Desktop launcher created${NC}"
fi

# Create convenience alias
SHELL_RC="${USER_HOME}/.zshrc"
if [[ -f "$SHELL_RC" && -w "$SHELL_RC" ]] && ! grep -q "alias dashboard=" "$SHELL_RC"; then
    if [[ "$RUNTIME_MODE" == "k8s" ]]; then
        cat >> "$SHELL_RC" <<EOF

# NixOS System Dashboard
alias dashboard='cd ${SCRIPT_DIR} && ./launch-dashboard.sh'
alias dashboard-start='systemctl --user start dashboard-collector.timer dashboard-server.service dashboard-api-proxy.service'
alias dashboard-stop='systemctl --user stop dashboard-collector.timer dashboard-server.service dashboard-api-proxy.service'
alias dashboard-status='systemctl --user status dashboard-collector.timer dashboard-server.service dashboard-api-proxy.service'
EOF
    else
        cat >> "$SHELL_RC" <<EOF

# NixOS System Dashboard
alias dashboard='cd ${SCRIPT_DIR} && ./launch-dashboard.sh'
alias dashboard-start='systemctl --user start dashboard-collector.timer dashboard-server.service dashboard-api.service'
alias dashboard-stop='systemctl --user stop dashboard-collector.timer dashboard-server.service dashboard-api.service'
alias dashboard-status='systemctl --user status dashboard-collector.timer dashboard-server.service dashboard-api.service'
EOF
    fi
    echo -e "${GREEN}✅ Shell aliases added to ${SHELL_RC}${NC}"
elif [[ -f "$SHELL_RC" && ! -w "$SHELL_RC" ]]; then
    echo -e "${YELLOW}⚠️  ${SHELL_RC} is not writable; skipped alias install.${NC}"
fi

echo ""
echo -e "${CYAN}╔═══════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║                                                       ║${NC}"
echo -e "${CYAN}║  ${GREEN}✅ System Dashboard Setup Complete!${CYAN}                ║${NC}"
echo -e "${CYAN}║                                                       ║${NC}"
echo -e "${CYAN}║  ${YELLOW}Quick Start:${NC}                                      ${CYAN}║${NC}"
echo -e "${CYAN}║  ${NC}1. Start services:${NC}                                ${CYAN}║${NC}"
echo -e "${CYAN}║     ${NC}systemctl --user start dashboard-server${NC}        ${CYAN}║${NC}"
if [[ "$RUNTIME_MODE" == "k8s" ]]; then
echo -e "${CYAN}║     ${NC}systemctl --user start dashboard-api-proxy${NC}     ${CYAN}║${NC}"
else
echo -e "${CYAN}║     ${NC}systemctl --user start dashboard-api${NC}            ${CYAN}║${NC}"
fi
echo -e "${CYAN}║     ${NC}systemctl --user start dashboard-collector.timer${NC} ${CYAN}║${NC}"
echo -e "${CYAN}║                                                       ║${NC}"
echo -e "${CYAN}║  ${NC}2. Open dashboard:${NC}                                ${CYAN}║${NC}"
echo -e "${CYAN}║     ${NC}xdg-open http://${SERVICE_HOST:-localhost}:${DASHBOARD_PORT:-8888}/dashboard.html${NC}  ${CYAN}║${NC}"
echo -e "${CYAN}║                                                       ║${NC}"
echo -e "${CYAN}║  ${YELLOW}Or use the quick launcher:${NC}                       ${CYAN}║${NC}"
echo -e "${CYAN}║     ${NC}./launch-dashboard.sh${NC}                           ${CYAN}║${NC}"
echo -e "${CYAN}║                                                       ║${NC}"
echo -e "${CYAN}║  ${YELLOW}Shell Aliases:${NC}                                    ${CYAN}║${NC}"
echo -e "${CYAN}║     ${NC}dashboard        # Launch dashboard${NC}             ${CYAN}║${NC}"
echo -e "${CYAN}║     ${NC}dashboard-start  # Start services${NC}               ${CYAN}║${NC}"
echo -e "${CYAN}║     ${NC}dashboard-stop   # Stop services${NC}                ${CYAN}║${NC}"
echo -e "${CYAN}║     ${NC}dashboard-status # Check status${NC}                 ${CYAN}║${NC}"
echo -e "${CYAN}║                                                       ║${NC}"
echo -e "${CYAN}╚═══════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}📚 Documentation:${NC}"
echo -e "   • Quick Start: ${SCRIPT_DIR}/DASHBOARD-QUICKSTART.md"
echo -e "   • Complete Guide: ${SCRIPT_DIR}/SYSTEM-DASHBOARD-GUIDE.md"
echo ""
