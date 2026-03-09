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

check_path_absent() {
  local path="$1"
  local label="$2"
  if [[ -e "$path" ]]; then
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
check_absent_pattern "scripts/governance/manage-secrets.py" 'This script is deprecated' 'Secrets manager entrypoint is active, not deprecated'
check_pattern "scripts/governance/manage-secrets.py" 'Manage external SOPS secrets for the AI stack' 'Secrets manager exposes a real CLI parser'
check_pattern "scripts/governance/manage-secrets.py" 'ensure-local-config' 'Secrets manager can refresh gitignored local host wiring'
check_pattern "scripts/governance/manage-secrets.py" 'subparsers\.add_parser\("bootstrap"' 'Secrets manager exposes delegated bootstrap flow'
check_pattern "scripts/governance/manage-secrets.py" 'subparsers\.add_parser\("doctor"' 'Secrets manager exposes readiness doctor flow'
check_pattern "scripts/governance/manage-secrets.py" 'Requested secret set ready:' 'Secrets manager doctor reports readiness summary'
check_pattern "scripts/governance/manage-secrets.py" '"next_steps": next_steps|--format", choices=\["text", "json"\]' 'Secrets manager doctor exposes machine-readable readiness output'
check_pattern "scripts/governance/manage-secrets.py" 'print_post_action_doctor_summary\(' 'Secrets manager reuses readiness summary after mutating commands'
check_pattern "scripts/governance/manage-secrets.py" 'resolve_runtime_context\(' 'Secrets manager centralizes host/path runtime context loading'
check_pattern "scripts/governance/manage-secrets.py" 'ensure_secret_wiring\(' 'Secrets manager centralizes age+sops+local override wiring'
check_pattern "scripts/governance/manage-secrets.py" 'Core ready:|All managed secrets ready:' 'Secrets manager status distinguishes core vs full readiness'
check_pattern "scripts/governance/manage-secrets.py" 'status_parser\.add_argument\("--format", choices=\["text", "json"\]' 'Secrets manager status exposes machine-readable JSON output'
check_pattern "scripts/governance/audit-deprecated-script-usage.py" 'Rank deprecated scripts by active repo references and classify keep vs archive' 'Deprecated-script auditor exists for keep-vs-archive prioritization'
check_pattern "docs/operations/deprecated-script-audit.md" '## Keep As Shim' 'Deprecated-script audit report records keep-as-shim classification'
check_pattern "docs/operations/deprecated-script-audit.md" '## Archive Or Remove' 'Deprecated-script audit report records archive-or-remove classification'
check_path_absent "scripts/governance/lint-timeouts.sh" 'Low-signal deprecated lint-timeouts shim has been removed'
check_path_absent "scripts/governance/manage-cache.sh" 'Low-signal deprecated manage-cache shim has been removed'
check_path_absent "scripts/governance/smart-config-gen.sh" 'Low-signal deprecated smart-config-gen shim has been removed'
check_path_absent "scripts/governance/smart_config_gen.sh" 'Low-signal deprecated smart_config_gen compatibility shim has been removed'
check_path_absent "scripts/testing/verify-pytorch-fix.sh" 'Low-signal deprecated verify-pytorch-fix shim has been removed'
check_path_absent "scripts/data/generate-nginx-certs.sh" 'Low-signal deprecated generate-nginx-certs shim has been removed'
check_path_absent "scripts/data/init-package-database.sh" 'Low-signal deprecated init-package-database shim has been removed'
check_path_absent "scripts/data/generate-test-telemetry.sh" 'Low-signal deprecated generate-test-telemetry shim has been removed'
check_path_absent "scripts/deploy/local-registry.sh" 'Low-signal deprecated local-registry shim has been removed'
check_path_absent "scripts/data/download-lemonade-models.sh" 'Low-signal deprecated download-lemonade-models shim has been removed'
check_path_absent "scripts/data/initialize-qdrant-collections.sh" 'Low-signal deprecated initialize-qdrant-collections shim has been removed'
check_path_absent "scripts/data/populate-knowledge-base.py" 'Low-signal deprecated populate-knowledge-base stub has been removed'
check_path_absent "scripts/data/populate-knowledge-from-web.py" 'Low-signal deprecated populate-knowledge-from-web stub has been removed'
check_path_absent "scripts/data/populate-qdrant-with-embeddings.py" 'Low-signal deprecated populate-qdrant-with-embeddings stub has been removed'
check_path_absent "scripts/data/populate-qdrant-collections.sh" 'Low-signal deprecated populate-qdrant-collections stub has been removed'
check_path_absent "scripts/data/sync-npm-ai-tools.sh" 'Low-signal deprecated sync-npm-ai-tools shim has been removed'
check_path_absent "scripts/deploy/install-lemonade-gui.sh" 'Low-signal deprecated install-lemonade-gui shim has been removed'
check_path_absent "scripts/deploy/setup-dvc-remote.sh" 'Low-signal deprecated setup-dvc-remote shim has been removed'
check_path_absent "scripts/deploy/setup-hybrid-learning.sh" 'Low-signal deprecated setup-hybrid-learning shim has been removed'
check_path_absent "scripts/governance/analyze-test-results.sh" 'Low-signal deprecated analyze-test-results shim has been removed'
check_path_absent "scripts/governance/lint-skills-podman.sh" 'Low-signal deprecated lint-skills-podman shim has been removed'
check_path_absent "scripts/automation/run-dashboard-collector-full.sh" 'Low-signal deprecated run-dashboard-collector-full shim has been removed'
check_path_absent "scripts/automation/run-dashboard-collector-lite.sh" 'Low-signal deprecated run-dashboard-collector-lite shim has been removed'
check_path_absent "scripts/deploy/fast-rebuild.sh" 'Low-signal deprecated fast-rebuild shim has been removed'
check_path_absent "scripts/governance/comprehensive-mcp-search.py" 'Low-signal deprecated comprehensive-mcp-search stub has been removed'
check_pattern "docs/development/SECRETS-MANAGEMENT-GUIDE.md" '~/.local/share/nixos-quick-deploy/secrets/<host>/secrets\.sops\.yaml' 'Secrets guide documents external bundle location'
check_pattern "docs/development/SECRETS-MANAGEMENT-GUIDE.md" 'manage-secrets\.sh bootstrap --host' 'Secrets guide documents delegated quick-deploy bootstrap flow'
check_pattern "docs/development/SECRETS-MANAGEMENT-GUIDE.md" 'manage-secrets\.sh doctor --host' 'Secrets guide documents doctor-based readiness workflow'
check_pattern "docs/development/SECRETS-MANAGEMENT-GUIDE.md" 'manage-secrets\.sh doctor --host nixos --format json' 'Secrets guide documents doctor JSON output for automation'
check_pattern "docs/development/SECRETS-MANAGEMENT-GUIDE.md" 'print a readiness summary with the next commands to run|end with the same readiness summary used by `doctor`' 'Secrets guide documents post-action readiness summaries'
check_pattern "docs/development/SECRETS-MANAGEMENT-GUIDE.md" 'core readiness for deploy-critical secrets|all-managed readiness including optional and remote-routing secrets' 'Secrets guide documents status scope distinction'
check_pattern "docs/development/SECRETS-MANAGEMENT-GUIDE.md" 'manage-secrets\.sh status --host nixos --format json' 'Secrets guide documents status JSON output for automation'
check_pattern "scripts/data/generate-api-secrets.sh" 'compatibility shim over scripts/governance/manage-secrets\.sh' 'API secret generator delegates to declarative secrets manager'
check_pattern "scripts/security/rotate-api-key.sh" 'compatibility shim over scripts/governance/manage-secrets\.sh' 'API key rotation shim delegates to declarative secrets manager'
check_pattern "scripts/data/generate-passwords.sh" 'compatibility shim over scripts/governance/manage-secrets\.sh' 'Password generator delegates to declarative secrets manager'
check_pattern "scripts/data/generate-api-key.sh" 'service_to_secret' 'Single API key generator maps services into declarative secret names'
check_pattern "scripts/security/security-scan.sh" 'compatibility shim over supported security tooling' 'Security scan shim delegates to supported audit tooling'
check_pattern "scripts/security/renew-tls-certificate.sh" 'compatibility shim for declarative ingress TLS' 'TLS renewal shim points to declarative ingress flow'
check_pattern "scripts/observability/collect-ai-metrics.sh" 'ai_metrics\.json' 'AI metrics collector refreshes the legacy dashboard cache file'
check_pattern "scripts/data/generate-dashboard-data.sh" 'compatibility shim over collect-ai-metrics\.sh' 'Legacy dashboard data generator delegates to the supported cache refresh flow'
check_pattern "scripts/data/generate-dashboard-data-lite.sh" 'compatibility shim over generate-dashboard-data\.sh' 'Legacy lite dashboard generator delegates to the main dashboard refresh shim'
check_pattern "scripts/governance/manage-dashboard-collectors.sh" 'compatibility shim over the dashboard service and collect-ai-metrics\.sh' 'Legacy dashboard collector manager delegates to declarative service control and cache refresh'
check_pattern "scripts/ai/ai-metrics-auto-updater.sh" 'compatibility shim over collect-ai-metrics\.sh' 'Legacy AI metrics auto updater delegates to the supported cache refresh flow'
check_pattern "scripts/security/apply-tls-certificates.sh" 'compatibility shim over renew-tls-certificate\.sh' 'TLS apply shim delegates to the revived TLS renewal flow'
check_pattern "scripts/testing/check-ai-stack-health.sh" 'compatibility shim over ai-stack-health\.sh' 'Legacy AI stack health check delegates to declarative health tooling'
check_pattern "scripts/testing/telemetry-smoke-test.sh" 'compatibility shim over current observability smoke checks' 'Telemetry smoke shim delegates to supported observability checks'
check_pattern "scripts/testing/check-ai-stack-health-v2.py" 'Compatibility shim over the current declarative AI stack health checks|compatibility shim over check-ai-stack-health\.sh' 'Legacy AI stack health v2 shim delegates to current health tooling'
check_pattern "scripts/testing/test-ai-stack-health.sh" 'compatibility shim over check-ai-stack-health\.sh' 'Legacy AI stack health test shim delegates to current health tooling'
check_pattern "scripts/testing/check-tls-log-warnings.sh" 'compatibility shim over declarative TLS status and journal scans' 'Legacy TLS log warning check delegates to current TLS status and journald scan'
check_pattern "scripts/testing/test-container-recovery.sh" 'compatibility shim over aq-runtime-act and aq-system-act' 'Legacy container recovery test delegates to bounded runtime tooling'
check_pattern "scripts/ai/ai-model-manager.sh" 'compatibility shim over current model tooling' 'Legacy AI model manager delegates to supported model tooling'
check_pattern "scripts/ai/llama-model-cli.sh" 'compatibility shim over ai-model-manager\.sh and systemd logs' 'Legacy llama model CLI delegates to current model tooling'
check_pattern "scripts/ai/ai-stack-e2e-test.sh" 'compatibility shim over aq-qa and real-world workflow smoke tests' 'Legacy AI stack E2E test delegates to declarative validation paths'
check_pattern "scripts/ai/ai-model-setup.sh" 'compatibility shim over current declarative model tooling' 'Legacy AI model setup delegates to current model lifecycle tooling'
check_pattern "scripts/ai/ai-model-setup.sh" 'ai-model-manager\.sh status|update-llama-cpp\.sh' 'Legacy AI model setup exposes current status and update flows'
check_pattern "scripts/ai/ai-stack-feature-scenario.sh" 'compatibility shim over current feature-planning and workflow smoke tooling' 'Legacy AI feature scenario delegates to current planning and smoke tooling'
check_pattern "scripts/ai/ai-stack-feature-scenario.sh" 'aq-context-bootstrap|test-real-world-workflows\.sh' 'Legacy AI feature scenario uses bootstrap and workflow smoke tools'
check_pattern "scripts/ai/ai-stack-resume-recovery.sh" 'compatibility shim over current bounded runtime recovery tooling' 'Legacy AI resume/recovery delegates to bounded runtime tooling'
check_pattern "scripts/ai/ai-stack-resume-recovery.sh" 'aq-system-act|aq-runtime-act' 'Legacy AI resume/recovery uses current runtime recovery entrypoints'
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
check_pattern "nixos-quick-deploy.sh" 'manage-secrets\.sh|manage_secrets_cmd.*bootstrap --host' 'Quick deploy delegates AI secrets bootstrap to the shared secrets manager'
check_pattern "nixos-quick-deploy.sh" 'should_manage_repo_backed_ai_services\(\)' 'Quick deploy centralizes repo-backed AI runtime gating'
check_pattern "nixos-quick-deploy.sh" 'systemd_unit_declared\(\)' 'Quick deploy centralizes systemd unit declaration checks'
check_pattern "nixos-quick-deploy.sh" 'systemd_unit_enabled_or_running\(\)' 'Quick deploy centralizes systemd unit state checks'
check_pattern "nixos-quick-deploy.sh" 'should_manage_repo_backed_ai_services "service restart"' 'Quick deploy reuses repo-backed AI gating for service restarts'
check_pattern "nixos-quick-deploy.sh" 'should_manage_repo_backed_ai_services "capability verification"' 'Quick deploy reuses repo-backed AI gating for capability verification'
check_pattern "nixos-quick-deploy.sh" 'ai_service_health_targets\(\)' 'Quick deploy centralizes AI service readiness targets'
check_pattern "nixos-quick-deploy.sh" 'done < <\(ai_service_health_targets\)' 'Quick deploy iterates AI readiness checks from the shared target table'
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
