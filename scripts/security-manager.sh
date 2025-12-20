#!/usr/bin/env bash
# security-manager.sh - Security & Firewall Management Helper
# Part of NixOS-Dev-Quick-Deploy
set -euo pipefail

SCRIPT_NAME="$(basename "$0")"
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
RESET='\033[0m'

usage() {
    cat <<EOF
${CYAN}Security & Firewall Manager for NixOS${RESET}

Usage: ${SCRIPT_NAME} <command>

Commands:
  status          Show firewall and security service status
  rules           Display current iptables rules
  ports           Show open ports and listening services
  dashboards      List available monitoring dashboards
  enable-monitoring   Show how to enable Prometheus/Grafana
  flatseal        Launch Flatseal for Flatpak permissions
  netdata         Open Netdata dashboard
  help            Show this message

Examples:
  ${SCRIPT_NAME} status
  ${SCRIPT_NAME} rules
  ${SCRIPT_NAME} ports

EOF
}

print_section() {
    echo -e "\n${CYAN}━━━ $1 ━━━${RESET}"
}

check_service() {
    local service="$1"
    local name="${2:-$service}"
    if systemctl is-active --quiet "$service" 2>/dev/null; then
        echo -e "  ${GREEN}✓${RESET} $name: RUNNING"
        return 0
    elif systemctl is-enabled --quiet "$service" 2>/dev/null; then
        echo -e "  ${YELLOW}○${RESET} $name: ENABLED (not running)"
        return 1
    else
        echo -e "  ${RED}✗${RESET} $name: DISABLED"
        return 2
    fi
}

subcmd_status() {
    print_section "Firewall Status"
    check_service "firewall" "NixOS Firewall" || true
    
    print_section "Security Services"
    check_service "fail2ban" "Fail2ban (SSH protection)" || true
    
    print_section "Monitoring Services"
    check_service "netdata" "Netdata (real-time monitoring)" || true
    check_service "prometheus" "Prometheus (metrics collection)" || true
    check_service "grafana" "Grafana (dashboards)" || true
    
    print_section "Network Status"
    echo "  Default route:"
    ip route | head -1 | sed 's/^/    /'
    echo "  DNS servers:"
    grep "nameserver" /etc/resolv.conf 2>/dev/null | sed 's/^/    /' || echo "    (none found)"
}

subcmd_rules() {
    print_section "Firewall Rules (requires sudo)"
    echo ""
    echo "INPUT chain (incoming connections):"
    sudo iptables -L INPUT -n -v --line-numbers 2>/dev/null || echo "  (need sudo or iptables not installed)"
    
    echo ""
    echo "FORWARD chain:"
    sudo iptables -L FORWARD -n -v --line-numbers 2>/dev/null | head -20
    
    echo ""
    echo "OUTPUT chain (outgoing connections):"
    sudo iptables -L OUTPUT -n -v --line-numbers 2>/dev/null | head -10
}

subcmd_ports() {
    print_section "Listening Ports & Services"
    echo ""
    echo "TCP Ports:"
    ss -tlnp 2>/dev/null | head -30 || netstat -tlnp 2>/dev/null | head -30
    
    echo ""
    echo "UDP Ports:"
    ss -ulnp 2>/dev/null | head -10 || netstat -ulnp 2>/dev/null | head -10
}

subcmd_dashboards() {
    print_section "Available Monitoring Dashboards"
    echo ""
    
    # Netdata
    if curl -s -o /dev/null -w "" --connect-timeout 1 http://localhost:19999 2>/dev/null; then
        echo -e "  ${GREEN}✓${RESET} Netdata: http://localhost:19999"
    else
        echo -e "  ${RED}✗${RESET} Netdata: Not accessible (service may not be running)"
    fi
    
    # Prometheus
    if curl -s -o /dev/null -w "" --connect-timeout 1 http://localhost:9090 2>/dev/null; then
        echo -e "  ${GREEN}✓${RESET} Prometheus: http://localhost:9090"
    else
        echo -e "  ${YELLOW}○${RESET} Prometheus: Not enabled (see 'enable-monitoring' command)"
    fi
    
    # Grafana
    if curl -s -o /dev/null -w "" --connect-timeout 1 http://localhost:3001 2>/dev/null; then
        echo -e "  ${GREEN}✓${RESET} Grafana: http://localhost:3001"
    else
        echo -e "  ${YELLOW}○${RESET} Grafana: Not enabled (see 'enable-monitoring' command)"
    fi
    
    # Gitea
    if curl -s -o /dev/null -w "" --connect-timeout 1 http://localhost:3000 2>/dev/null; then
        echo -e "  ${GREEN}✓${RESET} Gitea: http://localhost:3000"
    fi
    
    echo ""
    echo "To open dashboards in browser:"
    echo "  nix-shell -p firefox --run 'firefox http://localhost:19999'"
}

subcmd_enable_monitoring() {
    print_section "How to Enable Full Monitoring Stack"
    echo ""
    echo "Edit /etc/nixos/configuration.nix and change these settings:"
    echo ""
    cat <<'NIXCODE'
  # Enable Prometheus
  services.prometheus = {
    enable = true;
    exporters.node.enable = true;
  };

  # Enable Grafana
  services.grafana = {
    enable = true;
    settings.server.http_port = 3001;
    settings.security.admin_password = "changeme";  # CHANGE THIS!
  };

  # Enable Fail2ban
  services.fail2ban = {
    enable = true;
    maxretry = 3;
    bantime = "1h";
  };
NIXCODE
    echo ""
    echo "Then rebuild NixOS:"
    echo "  sudo nixos-rebuild switch"
}

subcmd_flatseal() {
    print_section "Launching Flatseal"
    if flatpak list | grep -q "Flatseal"; then
        flatpak run com.github.tchx84.Flatseal &
        disown
        echo "Flatseal launched. Use it to manage Flatpak app permissions."
    else
        echo -e "${RED}Flatseal not installed.${RESET}"
        echo "Install with: flatpak install flathub com.github.tchx84.Flatseal"
    fi
}

subcmd_netdata() {
    print_section "Opening Netdata Dashboard"
    if curl -s -o /dev/null --connect-timeout 1 http://localhost:19999 2>/dev/null; then
        # Try native firefox first
        if command -v firefox &>/dev/null; then
            firefox http://localhost:19999 &
        else
            nix-shell -p firefox --run "firefox http://localhost:19999" &
        fi
        disown
        echo "Opening Netdata at http://localhost:19999"
    else
        echo -e "${RED}Netdata not running.${RESET}"
        echo "Start with: sudo systemctl start netdata"
    fi
}

# Main
case "${1:-help}" in
    status)
        subcmd_status
        ;;
    rules)
        subcmd_rules
        ;;
    ports)
        subcmd_ports
        ;;
    dashboards)
        subcmd_dashboards
        ;;
    enable-monitoring)
        subcmd_enable_monitoring
        ;;
    flatseal)
        subcmd_flatseal
        ;;
    netdata)
        subcmd_netdata
        ;;
    help|-h|--help)
        usage
        ;;
    *)
        echo -e "${RED}Unknown command: $1${RESET}" >&2
        usage >&2
        exit 1
        ;;
esac


