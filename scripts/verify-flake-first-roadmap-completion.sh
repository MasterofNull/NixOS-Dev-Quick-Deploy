#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

pass_count=0
fail_count=0

if command -v rg >/dev/null 2>&1; then
  SEARCH_TOOL="rg"
else
  SEARCH_TOOL="grep"
  echo "[verify] ripgrep not found; using grep fallback"
fi

check_pattern() {
  local file="$1"
  local pattern="$2"
  local label="$3"
  if [[ "$SEARCH_TOOL" == "rg" ]]; then
    rg -n "$pattern" "$file" >/dev/null 2>&1
  else
    grep -nE "$pattern" "$file" >/dev/null 2>&1
  fi

  if [[ $? -eq 0 ]]; then
    printf '[PASS] %s\n' "$label"
    pass_count=$((pass_count + 1))
  else
    printf '[FAIL] %s\n' "$label"
    fail_count=$((fail_count + 1))
  fi
}

echo "[verify] Flake-first roadmap completion checks"

# Phase 26/28 flake-first orchestration guardrails
check_pattern "nixos-quick-deploy.sh" 'FLAKE_FIRST_MODE=true' 'Flake-first remains default mode'
check_pattern "nixos-quick-deploy.sh" 'run_flake_first_deployment\(\)' 'Flake-first deployment function exists'
check_pattern "nixos-quick-deploy.sh" 'scripts/deploy-clean.sh' 'Flake-first uses deploy-clean orchestration path'
check_pattern "nixos-quick-deploy.sh" 'Phase 9 imperative stack/model scripts skipped in flake-first' 'Phase-9 imperative AI scripts skipped in flake-first'

# Host resolution and readiness checks
check_pattern "scripts/deploy-clean.sh" 'resolve_host_from_flake_if_needed\(\)' 'Deploy-clean has host auto-resolution helper'
check_pattern "scripts/analyze-clean-deploy-readiness.sh" 'resolve_host_from_flake_if_needed\(\)' 'Readiness analyzer has host auto-resolution helper'

# Lock safety + git declarative parity
check_pattern "scripts/deploy-clean.sh" 'is_locked_password_field\(\)' 'Deploy-clean has explicit lock marker detector'
check_pattern "scripts/deploy-clean.sh" 'Could not read password hash state' 'Unreadable password state is non-fatal'
check_pattern "scripts/deploy-clean.sh" 'persist_home_git_credentials_declarative\(\)' 'Declarative git projection helper exists'
check_pattern "scripts/deploy-clean.sh" 'credential.helper = lib.mkForce' 'Declarative git credential helper projection exists'

# Home/Nix wiring for host-scoped declarative overlays
check_pattern "flake.nix" 'hostDeployOptionsPath' 'Root flake includes host deploy options path'
check_pattern "flake.nix" 'hostHomeDeployOptionsPath' 'Root flake includes host home deploy options path'

# Supporting reliability improvements that were marked complete
check_pattern "lib/logging.sh" 'append_log_line\(\)' 'Safe append logging helper exists'
check_pattern "lib/validation-input.sh" 'find_existing_parent\(\)' 'Existing-parent path resolver exists'
check_pattern "lib/user-interaction.sh" 'AUTO_CONFIRM' 'Auto-confirm automation guard exists'

printf '\n[verify] Summary: %d pass, %d fail\n' "$pass_count" "$fail_count"
if (( fail_count > 0 )); then
  exit 1
fi
