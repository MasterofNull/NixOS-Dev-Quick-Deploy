#!/usr/bin/env bash
set -euo pipefail

# curate-residual-gaps.sh
# Lightweight curated imports for persistent low-frequency NixOS/system topics.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
source "${REPO_ROOT}/config/service-endpoints.sh"

AIDB_KEY_FILE="${AIDB_API_KEY_FILE:-/run/secrets/aidb_api_key}"
PG_PASS_FILE="${POSTGRES_PASSWORD_FILE:-/run/secrets/postgres_password}"

AIDB_KEY="${AIDB_API_KEY:-}"
[[ -z "$AIDB_KEY" && -r "$AIDB_KEY_FILE" ]] && AIDB_KEY="$(tr -d '[:space:]' < "$AIDB_KEY_FILE")"
PG_PASS=""
[[ -r "$PG_PASS_FILE" ]] && PG_PASS="$(tr -d '[:space:]' < "$PG_PASS_FILE")"

retry_curl() {
  local url="$1"
  local method="$2"
  local data="$3"
  local attempts="${4:-4}"
  local delay="${5:-2}"
  local n=1
  while [[ $n -le $attempts ]]; do
    if curl -fsS -X "$method" "$url" \
      --connect-timeout 3 \
      --max-time 12 \
      -H "Content-Type: application/json" \
      -H "X-API-Key: ${AIDB_KEY}" \
      --data "$data" >/dev/null; then
      return 0
    fi
    sleep "$delay"
    n=$((n + 1))
  done
  return 1
}

post_doc() {
  local title="$1"
  local rel="$2"
  local content="$3"
  local payload
  payload="$(jq -cn --arg t "$title" --arg p "knowledge" --arg r "$rel" --arg c "$content" \
    '{title:$t,project:$p,relative_path:$r,content:$c}')"
  retry_curl "${AIDB_URL}/documents" POST "$payload"
}

delete_gap() {
  local text="$1"
  PGPASSWORD="$PG_PASS" psql -h "${POSTGRES_HOST:-127.0.0.1}" -p "${POSTGRES_PORT:-5432}" -U aidb -d aidb \
    -c "DELETE FROM query_gaps WHERE query_text ILIKE '%${text//\'/''}%';" >/dev/null
}

[[ -n "$AIDB_KEY" ]] || { printf 'ERROR: AIDB API key missing\n' >&2; exit 1; }
[[ -n "$PG_PASS" ]] || { printf 'ERROR: Postgres password missing\n' >&2; exit 1; }

if ! curl -fsS -m 2 "${AIDB_URL}/health" >/dev/null 2>&1; then
  printf 'WARN: AIDB not healthy at %s; skipping residual gap curation for now.\n' "${AIDB_URL}" >&2
  exit 0
fi

post_doc "lib.mkIf and lib.mkForce quick reference" \
  "knowledge/nixos-mkif-mkforce-quick-reference.md" \
  "lib.mkIf conditionally applies module config when condition is true. lib.mkForce overrides previously merged values with highest precedence. Use mkIf for conditional composition and mkForce only when you must override defaults or lower-priority merges. Prefer narrow scope to avoid surprising module interactions."
delete_gap "lib.mkForce"
delete_gap "lib.mkIf"

post_doc "Nix flake follows lock quick reference" \
  "knowledge/nix-flake-follows-lock-quick-reference.md" \
  "In flake inputs, follows reuses another input's locked revision (commonly nixpkgs). This keeps dependency graph aligned and avoids duplicate pins. Update lock with nix flake update, then verify input graph with nix flake metadata and ensure follows edges point to intended roots."
delete_gap "flake inputs follows"

post_doc "NixOS module options quick reference" \
  "knowledge/nixos-module-options-quick-reference.md" \
  "NixOS module options are declared with lib.mkOption under options and consumed under config. Types enforce shape, defaults provide baseline values, and mkIf/mkDefault/mkForce control merge precedence. Inspect options via nixos-option or nix eval on nixosConfigurations.<host>.options."
delete_gap "NixOS module options"

post_doc "NixOS systemd service options quick reference" \
  "knowledge/nixos-systemd-service-options-quick-reference.md" \
  "Define systemd units declaratively under systemd.services.<name>.serviceConfig. Use wantedBy/after/requires for dependencies, and keep runtime state in StateDirectory/RuntimeDirectory where possible. Inject endpoints and ports via module options + environment variables instead of hardcoded literals."
delete_gap "NixOS systemd service options"
delete_gap "configure NixOS services"
delete_gap "how do I configure a NixOS systemd service"

post_doc "PostgreSQL NixOS module setup quick reference" \
  "knowledge/postgresql-nixos-module-setup-quick-reference.md" \
  "Enable PostgreSQL with services.postgresql.enable = true; set package/version, authentication, and initial databases/users declaratively. For app services, pass DSN parts by env vars or secret files and avoid embedding credentials in unit files. Use systemctl status postgresql and journalctl -u postgresql for validation."
delete_gap "postgresql NixOS module setup"

post_doc "TC3 feedback validation quick reference" \
  "knowledge/tc3-feedback-validation-quick-reference.md" \
  "TC3 feedback validation should verify: service health checks pass, routing split counters are present and non-zero, hint injection shows injected and successful counts, and no failed critical units remain. Use check-mcp-health, aq-report, and failed-unit classification to confirm."
delete_gap "tc3 feedback validation"
delete_gap "tc3 final feedback loop validation"

post_doc "Hybrid coordinator routing quick reference" \
  "knowledge/hybrid-coordinator-routing-quick-reference.md" \
  "Hybrid coordinator routes queries by blending lexical search, semantic retrieval, optional tree search, and runtime provider selection. It applies capability discovery and hints context, then chooses local or remote backend using policy, health, and confidence thresholds. Routing split metrics come from hybrid_llm_backend_selections_total with backend labels local and remote."
delete_gap "how does the hybrid coordinator route queries"

post_doc "What is NixOS quick reference" \
  "knowledge/what-is-nixos-quick-reference.md" \
  "NixOS is a Linux distribution built on the Nix package manager with declarative system configuration. The whole system state is defined in reproducible configuration files, enabling atomic upgrades, rollbacks, and consistent environment rebuilds across machines."
delete_gap "what is NixOS"

post_doc "NixOS flake build system quick reference" \
  "knowledge/nixos-flake-build-system-quick-reference.md" \
  "The NixOS flake build system evaluates outputs from flake.nix, then builds a host configuration such as nixosConfigurations.<host>.config.system.build.toplevel. Use nix flake show to inspect outputs, nix build .#nixosConfigurations.<host>.config.system.build.toplevel for a pure build, and nixos-rebuild switch --flake .#<host> to activate. Keep host-specific overrides out of tracked defaults when they contain secrets or machine-local settings."
delete_gap "NixOS flake build system"

post_doc "Continue chat hang diagnosis workflow quick reference" \
  "knowledge/continue-chat-hang-diagnosis-quick-reference.md" \
  "Diagnose Continue chat hangs by checking the hybrid coordinator, switchboard, local model service, and routing endpoints in that order. Start with aq-qa 0, aq-qa 2, and aq-hints for the failing symptom, then inspect aq-report, hybrid /workflow/plan, and recent tool-audit logs. Narrow whether the hang is UI-side, routing-side, model-load-side, or remote-provider-side before changing prompts or model settings."
delete_gap "create a workflow plan for diagnosing continue chat hangs"

post_doc "Switchboard profile routing header verification quick reference" \
  "knowledge/switchboard-profile-routing-header-verification-quick-reference.md" \
  "Verify switchboard profile routing headers by sending explicit requests through the hybrid or switchboard HTTP path and checking response metadata plus logged backend/profile selection. Confirm that x-ai-profile or equivalent routing intent maps to the expected local, remote-free, remote-coding, or remote-reasoning lane, and validate with aq-report plus tool-audit metadata rather than assuming header parsing alone."
delete_gap "verify switchboard response headers for profile routing"

post_doc "Progressive disclosure token efficiency defaults quick reference" \
  "knowledge/progressive-disclosure-token-efficiency-defaults-quick-reference.md" \
  "Reduce token overhead by making compact responses the default across prompts, hints, plans, and query flows. Start with the minimum sufficient objective, constraints, concrete repo context, and validation checks, then expand only when a failure, ambiguity, or explicit user request justifies more context. Prefer retrieval and narrow references over prompt stuffing, keep tool catalogs and coaching summaries compact by default, and move verbose diagnostics behind explicit debug or deep-detail opt-ins. Route simple work locally first, escalate to remote only when scope, context length, or prior failures require it, and keep reusable prefixes short so provider-side prompt caching stays effective."
delete_gap "reduce token overhead through progressive disclosure defaults"

post_doc "Workflow run start intent contract quick reference" \
  "knowledge/workflow-run-start-intent-contract-quick-reference.md" \
  "Start workflow execution with a compact intent contract that states the objective, constraints, context scope, validation checks, and requested depth. Use minimum depth by default, add explicit files or services only when they are relevant, and keep routing intent separate from implementation details so the workflow can expand context later if needed. The contract should be concise enough to guide planning without front-loading every diagnostic or recovery step into the initial payload."
delete_gap "intent contract fields for workflow start"
delete_gap "show workflow run start intent contract requirements"

post_doc "Qdrant and hybrid routing configuration quick reference" \
  "knowledge/qdrant-and-hybrid-routing-configuration-quick-reference.md" \
  "Configure Qdrant and hybrid routing declaratively through Nix options rather than hardcoded URLs. Define ports in nix/modules/core/options.nix, wire them into nix/modules/roles/ai-stack.nix and nix/modules/services/mcp-servers.nix, and let the hybrid coordinator consume injected environment variables such as QDRANT_URL and related service endpoints. Validate with aq-qa 0, check-mcp-health, hybrid /health, and aq-report so storage, retrieval, and routing all confirm the same effective configuration."
delete_gap "how to configure qdrant and hybrid routing in this repo"

post_doc "Declarative runtime tool security policy quick reference" \
  "knowledge/declarative-runtime-tool-security-policy-quick-reference.md" \
  "Define runtime tool security policy declaratively in ai.aiHarness.runtime.toolSecurity.policy. Configure blocked tools, blocked endpoint patterns, blocked parameter keys, and max parameter string length from Nix options. Keep enforcement enabled and persist safe-audit cache to reduce repeat scanning."
delete_gap "NixOS declarative runtime tool security policy pattern for hybrid coor"

post_doc "Semantic tool calling and metadata verification quick reference" \
  "knowledge/semantic-tool-calling-metadata-verification-quick-reference.md" \
  "Verify semantic tool calling by checking discovery/workflow plan availability, tool execution success telemetry, and hint adoption outcomes. Ensure tool metadata includes safety annotations and runtime policy validation before first-use execution."
delete_gap "verify semantic tool calling and tool security metadata"

printf 'Residual gap curation complete.\n'
