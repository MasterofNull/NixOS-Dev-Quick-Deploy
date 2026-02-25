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
  local matched=1
  if [[ "$SEARCH_TOOL" == "rg" ]]; then
    if rg -n "$pattern" "$file" >/dev/null 2>&1; then
      matched=0
    fi
  else
    if grep -nE "$pattern" "$file" >/dev/null 2>&1; then
      matched=0
    fi
  fi

  if [[ $matched -eq 0 ]]; then
    printf '[PASS] %s\n' "$label"
    pass_count=$((pass_count + 1))
  else
    printf '[FAIL] %s\n' "$label"
    fail_count=$((fail_count + 1))
  fi
}

check_absent_pattern() {
  local file="$1"
  local pattern="$2"
  local label="$3"
  local matched=1
  if [[ "$SEARCH_TOOL" == "rg" ]]; then
    if rg -n "$pattern" "$file" >/dev/null 2>&1; then
      matched=0
    fi
  else
    if grep -nE "$pattern" "$file" >/dev/null 2>&1; then
      matched=0
    fi
  fi

  if [[ $matched -eq 0 ]]; then
    printf '[FAIL] %s\n' "$label"
    fail_count=$((fail_count + 1))
  else
    printf '[PASS] %s\n' "$label"
    pass_count=$((pass_count + 1))
  fi
}

echo "[verify] Flake-first roadmap completion checks"

# Flake-first orchestration guardrails (current architecture)
check_pattern "nixos-quick-deploy.sh" 'MODE="switch"' 'Flake-first deploy defaults to switch mode'
check_pattern "nixos-quick-deploy.sh" 'run_roadmap_completion_verification\(\)' 'Roadmap verification hook exists'
check_pattern "nixos-quick-deploy.sh" 'run_readiness_analysis\(\)' 'Readiness analyzer hook exists'
check_pattern "nixos-quick-deploy.sh" 'Skipping imperative runtime orchestration in deploy-clean' 'Imperative runtime orchestration is explicitly skipped'
check_pattern "scripts/deploy-clean.sh" 'is deprecated; use ./nixos-quick-deploy.sh' 'deploy-clean shim is deprecated and forwards to nixos-quick-deploy'

# Host resolution and readiness checks
check_pattern "nixos-quick-deploy.sh" 'resolve_host_from_flake_if_needed\(\)' 'Deploy entrypoint has host auto-resolution helper'
check_pattern "scripts/analyze-clean-deploy-readiness.sh" 'resolve_host_from_flake_if_needed\(\)' 'Readiness analyzer has host auto-resolution helper'

# Lock safety + git declarative parity
check_pattern "nixos-quick-deploy.sh" 'is_locked_password_field\(\)' 'Deploy entrypoint has explicit lock marker detector'
check_pattern "nixos-quick-deploy.sh" 'Could not read password hash state' 'Unreadable password state is non-fatal'
check_pattern "nixos-quick-deploy.sh" 'persist_home_git_credentials_declarative\(\)' 'Declarative git projection helper exists'
check_pattern "nixos-quick-deploy.sh" 'credential.helper = lib.mkForce' 'Declarative git credential helper projection exists'

# Home/Nix wiring for host-scoped declarative overlays
check_pattern "flake.nix" 'hostDeployOptionsPath' 'Root flake includes host deploy options path'
check_pattern "flake.nix" 'hostHomeDeployOptionsPath' 'Root flake includes host home deploy options path'

# Centralized AI port registry + OTEL collector guardrails
check_pattern "nix/modules/core/options.nix" 'ports = \{' 'Centralized port registry exists'
check_pattern "nix/modules/core/options.nix" 'qdrantHttp = lib.mkOption' 'Port registry includes Qdrant HTTP'
check_pattern "nix/modules/core/options.nix" 'qdrantGrpc = lib.mkOption' 'Port registry includes Qdrant gRPC'
check_pattern "nix/modules/core/options.nix" 'otlpGrpc = lib.mkOption' 'Port registry includes OTLP gRPC'
check_pattern "nix/modules/core/options.nix" 'otlpHttp = lib.mkOption' 'Port registry includes OTLP HTTP'
check_pattern "nix/modules/core/options.nix" 'otelCollectorMetrics = lib.mkOption' 'Port registry includes OTEL collector metrics'
check_pattern "nix/modules/services/mcp-servers.nix" 'qdrantUrl = "http://127.0.0.1:\$\{toString ports.qdrantHttp\}"' 'MCP services derive Qdrant URL from port registry'
check_pattern "nix/modules/services/mcp-servers.nix" 'otlpEndpoint = "http://127.0.0.1:\$\{toString ports.otlpGrpc\}"' 'MCP services derive OTLP endpoint from port registry'
check_pattern "nix/modules/services/mcp-servers.nix" 'nop: \{\}' 'OTEL collector uses nop exporter to suppress debug trace dumps'
check_absent_pattern "nix/modules/services/mcp-servers.nix" 'jaeger:4317' 'No hardcoded Jaeger endpoint in declarative MCP services'
check_absent_pattern "nix/modules/services/mcp-servers.nix" 'debug:' 'No debug exporter configured in declarative OTEL collector'
check_pattern "ai-stack/mcp-servers/hybrid-coordinator/server.py" 'AI_STRICT_ENV", "true"' 'Hybrid coordinator defaults to strict env enforcement'
check_pattern "ai-stack/mcp-servers/ralph-wiggum/server.py" 'AI_STRICT_ENV", "true"' 'Ralph defaults to strict env enforcement'
check_pattern "ai-stack/mcp-servers/aidb/settings_loader.py" 'AI_STRICT_ENV", "true"' 'AIDB settings loader defaults to strict env enforcement'

# Supporting reliability improvements that were marked complete
check_pattern "lib/logging.sh" 'append_log_line\(\)' 'Safe append logging helper exists'
check_pattern "lib/validation-input.sh" 'find_existing_parent\(\)' 'Existing-parent path resolver exists'
check_pattern "lib/user-interaction.sh" 'AUTO_CONFIRM' 'Auto-confirm automation guard exists'
check_pattern "scripts/validate-deploy-doc-flags.sh" 'supported quick-deploy flags' 'Deploy docs flag validator exists'

printf '\n[verify] Summary: %d pass, %d fail\n' "$pass_count" "$fail_count"
if (( fail_count > 0 )); then
  exit 1
fi
