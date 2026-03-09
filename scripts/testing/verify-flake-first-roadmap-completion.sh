#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
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
check_pattern "scripts/deploy/deploy-clean.sh" 'is deprecated; use ./nixos-quick-deploy.sh' 'deploy-clean shim is deprecated and forwards to nixos-quick-deploy'

# Host resolution and readiness checks
check_pattern "nixos-quick-deploy.sh" 'resolve_host_from_flake_if_needed\(\)' 'Deploy entrypoint has host auto-resolution helper'
check_pattern "scripts/governance/analyze-clean-deploy-readiness.sh" 'resolve_host_from_flake_if_needed\(\)' 'Readiness analyzer has host auto-resolution helper'

# Lock safety + git declarative parity
check_pattern "nixos-quick-deploy.sh" 'is_locked_password_field\(\)' 'Deploy entrypoint has explicit lock marker detector'
check_pattern "nixos-quick-deploy.sh" 'Could not read password hash state' 'Unreadable password state is non-fatal'
check_pattern "nixos-quick-deploy.sh" 'persist_home_git_credentials_declarative\(\)' 'Declarative git projection helper exists'
check_pattern "nixos-quick-deploy.sh" 'credential.helper = lib.mkDefault' 'Declarative git credential helper projection exists'

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
check_pattern "nix/modules/core/options.nix" 'remoteModelAliases = \{' 'Switchboard exposes declarative remote model aliases'
check_pattern "nix/modules/core/options.nix" 'remoteBudget = \{' 'Switchboard exposes declarative remote budget controls'
check_pattern "nix/modules/core/options.nix" 'addCheck lib\.types\.int \(value: value >= 0\)' 'Switchboard remote token cap uses portable non-negative int type'
check_pattern "nix/modules/core/options.nix" 'remoteLlmApiKey = lib.mkOption' 'Secrets options expose remote LLM API key name'
check_pattern "nix/modules/core/secrets.nix" 'needsRemoteLlmSecret = swb\.enable && swb\.remoteUrl != null && swb\.remoteApiKeyFile == null;' 'Remote LLM SOPS secret is only required when switchboard remote routing is configured'
check_pattern "nix/modules/core/secrets.nix" 'optionalAttrs needsRemoteLlmSecret' 'SOPS runtime secrets gate remote LLM API key exposure'
check_pattern "nix/modules/services/switchboard.nix" 'sec\.enable && remoteEnabled' 'Switchboard only defaults to declarative remote LLM secret path when remote routing is enabled'
check_pattern "nix/modules/services/switchboard.nix" 'SWB_REMOTE_DAILY_TOKEN_CAP' 'Switchboard injects remote daily token cap env'
check_pattern "nix/modules/services/switchboard.nix" 'remote-free|remote-coding|remote-reasoning' 'Switchboard exposes remote profile lanes'
check_pattern "nix/modules/services/switchboard.nix" '_remote_budget_status|remote_budget_exhausted' 'Switchboard enforces remote budget guardrails'
check_pattern "nix/modules/services/switchboard.nix" 'unitConfig = \{' 'Switchboard declares systemd unit-level settings explicitly'
check_pattern "nix/modules/services/switchboard.nix" 'StartLimitIntervalSec = "300";' 'Switchboard sets restart rate limiting on the unit'
# Phase 21.1 — OTEL exports to Tempo for distributed tracing (replaced nop exporter)
check_pattern "nix/modules/services/mcp-servers.nix" 'otlp/tempo:' 'OTEL collector exports traces to Tempo backend'
check_absent_pattern "nix/modules/services/mcp-servers.nix" 'jaeger:4317' 'No hardcoded Jaeger endpoint in declarative MCP services'
check_absent_pattern "nix/modules/services/mcp-servers.nix" 'debug:' 'No debug exporter configured in declarative OTEL collector'
check_pattern "ai-stack/mcp-servers/hybrid-coordinator/config.py" 'AI_STRICT_ENV", "true"' 'Hybrid coordinator defaults to strict env enforcement'
check_pattern "ai-stack/mcp-servers/ralph-wiggum/server.py" 'AI_STRICT_ENV", "true"' 'Ralph defaults to strict env enforcement'
check_pattern "ai-stack/mcp-servers/aidb/settings_loader.py" 'AI_STRICT_ENV", "true"' 'AIDB settings loader defaults to strict env enforcement'

# Supporting reliability improvements that were marked complete
check_pattern "lib/logging.sh" 'append_log_line\(\)' 'Safe append logging helper exists'
check_pattern "lib/validation-input.sh" 'find_existing_parent\(\)' 'Existing-parent path resolver exists'
check_pattern "lib/user-interaction.sh" 'AUTO_CONFIRM' 'Auto-confirm automation guard exists'
check_pattern "scripts/testing/validate-deploy-doc-flags.sh" 'supported quick-deploy flags' 'Deploy docs flag validator exists'

# Phase 21.2 — LLM performance metrics via llama.cpp --metrics
check_pattern "nix/modules/roles/ai-stack.nix" '"--metrics"' 'llama-server exposes Prometheus metrics endpoint'
check_pattern "nix/modules/services/monitoring.nix" 'job_name = "llama-cpp"' 'Prometheus scrapes llama-cpp inference metrics'
check_pattern "nix/modules/services/monitoring.nix" 'llamacpp_tokens_predicted_total' 'Dashboard tracks LLM token generation rate'
check_pattern "nix/modules/services/monitoring.nix" 'llamacpp_kv_cache_usage_ratio' 'Dashboard tracks KV cache utilization'
check_pattern "nix/modules/services/monitoring.nix" 'llamacpp_request_processing_seconds_bucket' 'Dashboard tracks inference latency histogram'

# Phase 21.3 — Cache intelligence with event-driven invalidation
check_pattern "ai-stack/mcp-servers/hybrid-coordinator/metrics.py" 'EMBEDDING_CACHE_INVALIDATIONS' 'Cache invalidation counter metric defined'
check_pattern "ai-stack/mcp-servers/hybrid-coordinator/metrics.py" 'EMBEDDING_CACHE_SIZE' 'Cache size gauge metric defined'
check_pattern "ai-stack/mcp-servers/hybrid-coordinator/http_server.py" '/cache/invalidate' 'Cache invalidation endpoint registered'
check_pattern "scripts/data/rebuild-qdrant-collections.sh" 'cache/invalidate' 'Rebuild script triggers cache invalidation'
check_pattern "nix/modules/services/monitoring.nix" 'embedding_cache_size_keys' 'Dashboard tracks embedding cache size'
check_pattern "nix/modules/services/monitoring.nix" 'embedding_cache_invalidations_total' 'Dashboard tracks cache invalidation rate'
check_pattern "scripts/automation/post-deploy-converge.sh" '/learning/process' 'Post-deploy convergence triggers learning pattern extraction'
check_pattern "scripts/automation/post-deploy-converge.sh" '/learning/export' 'Post-deploy convergence triggers fine-tuning dataset export'
check_pattern "scripts/automation/post-deploy-converge.sh" 'agent_instructions_import' 'Post-deploy convergence refreshes agent instruction imports'
check_pattern "ai-stack/mcp-servers/hybrid-coordinator/hints_engine.py" 'prompt_coaching' 'Hints engine exposes prompt coaching guidance'
check_pattern "ai-stack/mcp-servers/hybrid-coordinator/hints_engine.py" 'token_discipline' 'Hints engine exposes token-discipline coaching guidance'
check_pattern "ai-stack/mcp-servers/hybrid-coordinator/http_server.py" 'prompt_coaching' 'Workflow plan metadata includes prompt coaching'
check_pattern "ai-stack/mcp-servers/hybrid-coordinator/http_server.py" 'result\["prompt_coaching"\]|metadata\["prompt_coaching"\]' 'Query responses expose prompt coaching guidance'
check_pattern "ai-stack/mcp-servers/hybrid-coordinator/http_server.py" 'provider-side prompt caching|free or provider-routed experimentation' 'Workflow token policy teaches bounded cloud/provider token usage'
check_pattern "scripts/ai/aq-hints" 'Token plan:' 'aq-hints renders token-discipline coaching text'
check_pattern "config/agent-context-cards.json" 'OpenRouter-routed models|provider-side prompt caching' 'Token-discipline context card includes remote/provider budget rules'
check_pattern "ai-stack/mcp-servers/hybrid-coordinator/mcp_handlers.py" 'name="run_qa_check"' 'Hybrid coordinator exposes MCP QA tool'
check_pattern "ai-stack/mcp-servers/hybrid-coordinator/mcp_handlers.py" '_resolve_bash_binary' 'Hybrid QA tool resolves an explicit bash binary for systemd-safe execution'
check_pattern "ai-stack/mcp-servers/hybrid-coordinator/mcp_handlers.py" '_resolve_python3_binary|_build_qa_exec_env' 'Hybrid QA tool resolves python3 and PATH for systemd-safe execution'
check_pattern "ai-stack/mcp-servers/hybrid-coordinator/tooling_manifest.py" 'run_qa_check' 'Tooling manifest surfaces QA tool for validation tasks'
check_pattern "ai-stack/mcp-servers/hybrid-coordinator/http_server.py" 'qa_check", "harness_eval", "health", "learning_stats"' 'Workflow plan validate phase surfaces QA tool'
check_pattern "ai-stack/mcp-servers/hybrid-coordinator/http_server.py" '/qa/check' 'Hybrid coordinator exposes HTTP QA endpoint'
check_pattern "ai-stack/mcp-servers/hybrid-coordinator/harness_sdk.py" 'def query\(' 'Python harness SDK exposes coached query client'
check_pattern "ai-stack/mcp-servers/hybrid-coordinator/harness_sdk.ts" 'query\(' 'TypeScript harness SDK exposes coached query client'
check_pattern "ai-stack/mcp-servers/hybrid-coordinator/harness_sdk.js" 'query\(' 'JavaScript harness SDK exposes coached query client'
check_pattern "ai-stack/mcp-servers/hybrid-coordinator/harness_sdk.d.ts" 'query\(query: string, opts\?: QueryRequestOptions\)' 'TypeScript declaration exposes coached query client'
check_pattern "ai-stack/mcp-servers/hybrid-coordinator/harness_sdk.py" 'def qa_check' 'Python harness SDK exposes QA check client'
check_pattern "ai-stack/mcp-servers/hybrid-coordinator/harness_sdk.ts" 'qaCheck\(' 'TypeScript harness SDK exposes QA check client'
check_pattern "ai-stack/mcp-servers/hybrid-coordinator/harness_sdk.d.ts" 'qaCheck\(' 'TypeScript declaration exposes QA check client'
check_pattern "nix/modules/core/options.nix" 'localSystemPrompt = \{' 'Declarative local system prompt options exist'
check_pattern "nix/modules/services/mcp-servers.nix" 'AI_LOCAL_SYSTEM_PROMPT=' 'Hybrid service injects local system prompt flag'
check_pattern "ai-stack/mcp-servers/hybrid-coordinator/config.py" 'build_local_system_prompt' 'Hybrid config builds local system prompt from declarative rules'
check_pattern "ai-stack/mcp-servers/hybrid-coordinator/route_handler.py" '"role": "system"' 'Local route synthesis prepends a system prompt'
check_pattern "scripts/ai/aq-hints" 'parent\.parent\.parent' 'aq-hints resolves repository root correctly for local engine imports'
check_pattern "scripts/data/import-agent-instructions.sh" 'dirname "\$0"\)/\.\./\.\.' 'Agent instruction import resolves repository root correctly'

# Phase 21.5 — Post-deploy auto Phase 0 validation
check_pattern "nixos-quick-deploy.sh" 'qa_script=.*aq-qa|"\$\{qa_script\}" 0 --json' 'Deploy completion runs aq-qa phase 0 summary'
check_pattern "nixos-quick-deploy.sh" 'verify_repo_backed_ai_services_are_live_if_needed\(\)' 'Deploy entrypoint verifies repo-backed AI services after restart'
check_pattern "nixos-quick-deploy.sh" '/workflow/plan' 'Deploy verification probes workflow plan capability activation'
check_pattern "nixos-quick-deploy.sh" '/qa/check' 'Deploy verification probes hybrid QA endpoint activation'
check_pattern "nixos-quick-deploy.sh" '/learning/export' 'Deploy verification probes learning export activation'
check_pattern "scripts/automation/post-deploy-converge.sh" 'aq-qa" 0 --json' 'Post-deploy convergence runs aq-qa phase 0'

# Phase 4 — Parity scorecard completion (tracks implemented status)
check_pattern "config/parity-scorecard.json" '"status": "implemented"' 'Parity scorecard has implemented tracks'
check_pattern "config/parity-scorecard.json" '"id": "distributed_tracing"' 'Parity scorecard tracks distributed tracing'
check_pattern "config/parity-scorecard.json" '"id": "llm_performance_metrics"' 'Parity scorecard tracks LLM metrics'
check_pattern "config/parity-scorecard.json" '"id": "cache_intelligence"' 'Parity scorecard tracks cache intelligence'

# Phase 5 — Model management enhancement
check_pattern "ai-stack/mcp-servers/hybrid-coordinator/metrics.py" 'MODEL_RELOADS' 'Model reload counter metric defined'
check_pattern "ai-stack/mcp-servers/hybrid-coordinator/metrics.py" 'MODEL_RELOAD_DURATION' 'Model reload duration histogram defined'
check_pattern "ai-stack/mcp-servers/hybrid-coordinator/metrics.py" 'MODEL_ACTIVE_INFO' 'Model active info gauge defined'
check_pattern "ai-stack/mcp-servers/hybrid-coordinator/http_server.py" '/model/status' 'Model status endpoint registered'
check_pattern "nix/modules/services/monitoring.nix" 'model_reloads_total' 'Dashboard tracks model reloads'
check_pattern "config/parity-scorecard.json" '"id": "model_management"' 'Parity scorecard tracks model management'

printf '\n[verify] Summary: %d pass, %d fail\n' "$pass_count" "$fail_count"
if (( fail_count > 0 )); then
  exit 1
fi
