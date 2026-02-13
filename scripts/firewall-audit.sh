#!/usr/bin/env bash
# Firewall / ingress exposure audit (read-only).
# Reports listening ports and firewall rule hints when available.

set -euo pipefail

CONFIG_PATH="${CONFIG_PATH:-/etc/nixos/configuration.nix}"

info() { echo "ℹ $*"; }
warn() { echo "⚠ $*"; }
pass() { echo "✓ $*"; }

echo "=== Firewall / Ingress Audit ==="

info "Listening TCP/UDP ports (ss -tuln)"
if command -v ss >/dev/null 2>&1; then
  ss -tuln
else
  warn "ss not available; skipping port list"
fi
echo ""

info "Firewall config (NixOS configuration.nix)"
if [[ -r "$CONFIG_PATH" ]]; then
  echo "Path: $CONFIG_PATH"
  echo "Allowed TCP ports:"
  rg -n "allowedTCPPorts" "$CONFIG_PATH" || warn "No allowedTCPPorts entries found"
  echo "Allowed UDP ports:"
  rg -n "allowedUDPPorts" "$CONFIG_PATH" || warn "No allowedUDPPorts entries found"
  echo "Firewall enabled:"
  rg -n "networking.firewall.enable" "$CONFIG_PATH" || warn "No firewall.enable entry found"
else
  warn "Cannot read $CONFIG_PATH (run with sudo if needed)"
fi
echo ""

info "nftables ruleset (if available)"
if command -v nft >/dev/null 2>&1; then
  if nft list ruleset >/dev/null 2>&1; then
    nft list ruleset | head -200
    pass "nft ruleset read"
  else
    warn "nft ruleset not readable (try sudo)"
  fi
else
  warn "nft command not available"
fi

echo ""
info "Checklist:"
echo " - Only required ports are open (dashboard, registry, ingress as needed)"
echo " - K3s API not exposed publicly unless explicitly required"
echo " - Document any public-facing services in SECURITY-SETUP.md"

echo ""
pass "Firewall audit complete"
