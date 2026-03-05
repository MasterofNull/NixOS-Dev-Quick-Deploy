#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

log() {
  printf '[quick-deploy-fast-verify] %s\n' "$*"
}

log "Shell syntax checks"
bash -n nixos-quick-deploy.sh scripts/automation/post-deploy-converge.sh scripts/security/npm-security-monitor.sh

log "Quick deploy lint (fast)"
bash scripts/governance/quick-deploy-lint.sh --mode fast --flake-ref . --nixos-target nixos-ai-dev

log "NixOS flake dry build"
nix --extra-experimental-features 'nix-command flakes' build --no-link \
  .#nixosConfigurations."nixos-ai-dev".config.system.build.toplevel

log "No-switch preflight loop"
PRIME_SUDO_EARLY=false \
KEEP_SUDO_ALIVE=false \
PRECHECK_SHADOW_WITH_SUDO_PROMPT=false \
./nixos-quick-deploy.sh \
  --preflight-only \
  --skip-readiness-check \
  --skip-roadmap-verification \
  --skip-discovery

log "Fast verification completed"
