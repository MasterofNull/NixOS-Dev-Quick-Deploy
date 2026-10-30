#!/usr/bin/env bash
# Full NixOS system update: bring this machine to origin/main, then optionally clean old generations.
#
# Flake inputs are no longer updated here. An in-place `nix flake update` left an uncommitted
# flake.lock that no commit describes (2026-10-29, backlog FLAKE-LOCK-UNCOMMITTED-UPDATE), so lock
# refreshes land through a flake-refresh PR and this script deploys whatever origin/main pins.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

"${SCRIPT_DIR}/aq-deploy-current" "$@"
[[ " $* " == *" --dry-run "* ]] && exit 0

GENERATIONS=$(nixos-rebuild list-generations | wc -l)
echo "[system-update-full] ${GENERATIONS} system generations present."
read -p "Clean generations older than 30 days? (y/N) " -n 1 -r
echo
if [[ ${REPLY} =~ ^[Yy]$ ]]; then
    sudo nix-collect-garbage --delete-older-than 30d
fi
