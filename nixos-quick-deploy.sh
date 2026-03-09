#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "${SCRIPT_DIR}/flake.nix" && -d "${SCRIPT_DIR}/nix" ]]; then
  REPO_ROOT="${SCRIPT_DIR}"
else
  REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
fi

HOST_NAME="${HOSTNAME_OVERRIDE:-$(hostname -s 2>/dev/null || hostname)}"
PRIMARY_USER="${PRIMARY_USER_OVERRIDE:-${SUDO_USER:-${USER:-$(id -un)}}}"
PROFILE="${PROFILE_OVERRIDE:-ai-dev}"
FLAKE_REF="path:${REPO_ROOT}"
MODE="switch" # switch|build|boot
RUN_HEALTH_CHECK=true
RUN_DISCOVERY=true
UPDATE_FLAKE_LOCK=false
RUN_PHASE0_DISKO=false
RUN_SECUREBOOT_ENROLL=false
RUN_FLATPAK_SYNC=true
RUN_READINESS_ANALYSIS=true
RUN_AI_SECRETS_BOOTSTRAP=true
FORCE_AI_SECRETS_BOOTSTRAP=false
ENFORCE_PRE_DEPLOY_DRY_RUN=true
ENFORCE_PRE_DEPLOY_HOME_DRY_RUN=true
PRE_DEPLOY_PREFLIGHT_ONLY=false
SELF_CHECK_ONLY=false
PRE_DEPLOY_LOOP_MAX_PASSES="${PRE_DEPLOY_LOOP_MAX_PASSES:-3}"
PRE_DEPLOY_LOOP_RETRY_SECONDS="${PRE_DEPLOY_LOOP_RETRY_SECONDS:-2}"
ENABLE_PREFLIGHT_AUTO_REMEDIATION=false
ANALYZE_ONLY=false
SKIP_ROADMAP_VERIFICATION=false
RECOVERY_MODE=false
ALLOW_PREVIOUS_BOOT_FSCK_FAILURE=false
PRIME_SUDO_EARLY="${PRIME_SUDO_EARLY:-true}"
KEEP_SUDO_ALIVE="${KEEP_SUDO_ALIVE:-true}"
PRE_DEPLOY_PARALLEL_VALIDATION="${PRE_DEPLOY_PARALLEL_VALIDATION:-true}"
DISCOVERY_CACHE_TTL_SECONDS="${DISCOVERY_CACHE_TTL_SECONDS:-1800}"
PRECHECK_SHADOW_WITH_SUDO_PROMPT="${PRECHECK_SHADOW_WITH_SUDO_PROMPT:-false}"
SKIP_SYSTEM_SWITCH=false
SKIP_HOME_SWITCH=false
NIXOS_TARGET_OVERRIDE=""
HM_TARGET_OVERRIDE=""
HOST_EXPLICIT=false
AUTO_GUI_SWITCH_FALLBACK="${AUTO_GUI_SWITCH_FALLBACK:-false}"
ALLOW_GUI_SWITCH="${ALLOW_GUI_SWITCH:-true}"
HOME_MANAGER_BACKUP_EXTENSION="${HOME_MANAGER_BACKUP_EXTENSION:-backup-$(date +%Y%m%d%H%M%S)}"
REQUIRE_HOME_MANAGER_CLI="${REQUIRE_HOME_MANAGER_CLI:-false}"
PREFER_NIX_RUN_HOME_MANAGER="${PREFER_NIX_RUN_HOME_MANAGER:-true}"
HOME_MANAGER_NIX_RUN_REF="${HOME_MANAGER_NIX_RUN_REF:-github:nix-community/home-manager/release-25.11#home-manager}"
AI_SECRETS_BOOTSTRAP_STATUS="not-evaluated"
SUDO_KEEPALIVE_PID=""
AI_STACK_DATA_DIR="${AI_STACK_DATA_DIR:-/var/lib/ai-stack}"
DEPLOY_START_EPOCH="$(date +%s)"
declare -a PHASE_TIMINGS=()
POST_FLIGHT_MODE="${POST_FLIGHT_MODE:-declarative}" # declarative|inline|both
POST_FLIGHT_REBUILD_TIMEOUT_SECONDS="${POST_FLIGHT_REBUILD_TIMEOUT_SECONDS:-900}"
POST_FLIGHT_REPORT_TIMEOUT_SECONDS="${POST_FLIGHT_REPORT_TIMEOUT_SECONDS:-60}"
POST_FLIGHT_SEED_TIMEOUT_SECONDS="${POST_FLIGHT_SEED_TIMEOUT_SECONDS:-120}"
POST_FLIGHT_CONVERGE_START_DELAY_SECONDS="${POST_FLIGHT_CONVERGE_START_DELAY_SECONDS:-2}"
POST_SWITCH_REPO_SERVICE_RESTART_TIMEOUT_SECONDS="${POST_SWITCH_REPO_SERVICE_RESTART_TIMEOUT_SECONDS:-90}"
POST_SWITCH_REPO_CAPABILITY_VERIFY_TIMEOUT_SECONDS="${POST_SWITCH_REPO_CAPABILITY_VERIFY_TIMEOUT_SECONDS:-45}"
POST_SWITCH_REPO_CAPABILITY_RETRY_COUNT="${POST_SWITCH_REPO_CAPABILITY_RETRY_COUNT:-2}"
COMPLETION_PRINT_TEST_RESULTS="${COMPLETION_PRINT_TEST_RESULTS:-true}"
COMPLETION_TEST_MODE="${COMPLETION_TEST_MODE:-summary}" # summary|full|off
COMPLETION_TEST_HEALTH_TIMEOUT_SECONDS="${COMPLETION_TEST_HEALTH_TIMEOUT_SECONDS:-45}"
COMPLETION_TEST_REPORT_TIMEOUT_SECONDS="${COMPLETION_TEST_REPORT_TIMEOUT_SECONDS:-45}"
UI_COLOR_RESET=""
UI_COLOR_INFO=""
UI_COLOR_SECTION=""
UI_COLOR_SUCCESS=""
UI_COLOR_WARN=""
UI_COLOR_ERROR=""

AUTO_STAGED_FLAKE_PATH=""
# Tracks untracked files we temporarily add so Nix can evaluate local git flakes.
# We unstage them on exit to avoid leaving a dirty index that blocks `git pull --rebase`.
declare -a AUTO_STAGED_FLAKE_FILES=()

# Generated host file restore policy:
#   auto  -> restore only for --analyze-only runs
#   true  -> always restore generated files on exit (temporary projection)
#   false -> persist generated files to repo (declarative update)
RESTORE_GENERATED_REPO_FILES="${RESTORE_GENERATED_REPO_FILES:-auto}"
GENERATED_FILE_SNAPSHOT_DIR=""
declare -a GENERATED_FILE_SNAPSHOT_TARGETS=()

usage() {
  cat <<'USAGE'
Usage: ./nixos-quick-deploy.sh [options]

Flake-first deployment entrypoint for both:
- fresh NixOS bootstrap (minimal host, missing optional tooling)
- ongoing updates/upgrades on already-deployed systems

No template rendering. No legacy phase path.

Options:
  --host NAME             Hostname for flake target (default: current host)
  --user NAME             Home Manager user (default: current user)
  --profile NAME          Profile: ai-dev | gaming | minimal (default: ai-dev)
  --nixos-target NAME     Explicit nixosConfigurations target override
  --home-target NAME      Explicit homeConfigurations target override
  --flake-ref REF         Flake ref (default: path:<repo-root>)
  --update-lock           Update flake.lock before build/switch
  --boot                  Build and stage next boot generation (no live switch)
  --recovery-mode         Force recovery-safe facts (root fsck skip + initrd emergency shell)
  --allow-prev-fsck-fail  Continue even if previous boot had root fsck failure
  --phase0-disko          Run optional disko pre-install partition/apply step (destructive)
  --enroll-secureboot-keys
                          Run optional sbctl key enrollment when secure boot is enabled
  --build-only            Run dry-build/home build instead of switch
  --allow-gui-switch      Allow live switch from graphical session
  --no-gui-fallback       Disable auto-fallback to --boot in graphical session
  --skip-system-switch    Skip system apply/build action
  --skip-home-switch      Skip Home Manager apply/build action
  --skip-health-check     Skip post-switch health check script
  --require-home-manager-cli
                          Fail if home-manager binary is not already in PATH
  --skip-discovery        Skip hardware facts discovery
  --skip-flatpak-sync     Skip declarative Flatpak profile sync
  --skip-readiness-check  Skip bootstrap/deploy readiness analysis preflight
  --skip-ai-secrets-bootstrap
                          Skip interactive AI stack secrets bootstrap prompt
  --ai-secrets-bootstrap  Enable interactive AI stack secrets bootstrap prompt
  --force-ai-secrets-bootstrap
                          Force interactive AI stack secrets bootstrap prompt
  --analyze-only          Run readiness analysis and exit (no build/switch)
  --skip-pre-deploy-dry-run
                          Skip mandatory nixos/home dry-build preflight gate
                          (emergency use only)
  --skip-pre-deploy-home-dry-run
                          Skip Home Manager dry-build during preflight gate
  --preflight-only        Run mandatory pre-deploy validation loop and exit
                          (no switch/boot/home activation)
  --self-check            Validate script runtime contract (function wiring/order)
                          and exit without sudo/build/switch
  --enable-preflight-auto-remediation
                          Run scripts/governance/preflight-auto-remediate.sh between
                          failed preflight loop passes when available
  --preflight-loop-max-passes N
                          Maximum preflight loop passes (default: 3)
  --preflight-loop-retry-seconds N
                          Delay between failed preflight passes (default: 2)
  --skip-roadmap-verification
                          Skip flake-first roadmap completion verification preflight
  --restore-generated-files
                          Restore generated host files on exit (temporary run projection)
  --persist-generated-files
                          Persist generated host files after run (declarative update)
  --post-flight-mode MODE
                          Post-flight behavior: declarative | inline | both
  -h, --help              Show this help

Environment overrides:
  ALLOW_GUI_SWITCH=true     Allow live switch from graphical session (default)
  AUTO_GUI_SWITCH_FALLBACK=false
                            Keep switch mode in graphical sessions (default)
  ENFORCE_PRE_DEPLOY_DRY_RUN=true
                            Require nixos/home dry-build preflight before switch/boot
                            (recommended default)
  ENFORCE_PRE_DEPLOY_HOME_DRY_RUN=true
                            Include Home Manager dry-build in preflight gate (default)
  PRE_DEPLOY_LOOP_MAX_PASSES=3
                            Number of dry-run/fix/retry passes before failing
  PRE_DEPLOY_LOOP_RETRY_SECONDS=2
                            Sleep seconds between failed preflight passes
  ENABLE_PREFLIGHT_AUTO_REMEDIATION=false
                            Run scripts/governance/preflight-auto-remediate.sh between passes
  PRIME_SUDO_EARLY=true
                            Prompt for sudo once early to avoid mid-run stalls
  KEEP_SUDO_ALIVE=true      Keep sudo ticket alive during long preflight/build
  PRE_DEPLOY_PARALLEL_VALIDATION=true
                            Run system + Home Manager preflight builds in parallel
  DISCOVERY_CACHE_TTL_SECONDS=1800
                            Skip rediscovery when host/profile facts were refreshed recently
  PRECHECK_SHADOW_WITH_SUDO_PROMPT=false
                            Allow password prompt for /etc/shadow prechecks
  HOME_MANAGER_BACKUP_EXTENSION=backup-<timestamp>
                            Backup suffix used for Home Manager file collisions.
                            Default is timestamped per run to prevent clobbering
                            existing *.backup files.
  REQUIRE_HOME_MANAGER_CLI=false
                            Require home-manager command in PATH (disable fallback paths)
  PREFER_NIX_RUN_HOME_MANAGER=true
                            Try `nix run` home-manager before activation fallback when CLI missing
  HOME_MANAGER_NIX_RUN_REF=github:nix-community/home-manager/release-25.11#home-manager
                            Flake ref used for nix-run Home Manager fallback
  POST_FLIGHT_MODE=declarative
                            Post-flight behavior: declarative|inline|both
                            declarative (default): trigger ai-post-deploy-converge service
                            inline: run seed/reindex/report directly in this script
                            both: trigger service and run inline fallbacks
  POST_FLIGHT_SEED_TIMEOUT_SECONDS=120
                            Timeout for inline routing seed task
  POST_SWITCH_REPO_SERVICE_RESTART_TIMEOUT_SECONDS=90
                            Timeout for mutable repo-backed AI service restarts
  POST_SWITCH_REPO_CAPABILITY_VERIFY_TIMEOUT_SECONDS=45
                            Timeout for each mutable repo-backed capability probe
  POST_SWITCH_REPO_CAPABILITY_RETRY_COUNT=2
                            Maximum restart+verify attempts for repo-backed AI services
  POST_FLIGHT_REBUILD_TIMEOUT_SECONDS=900
                            Timeout for inline Qdrant rebuild task
  POST_FLIGHT_REPORT_TIMEOUT_SECONDS=60
                            Timeout for inline aq-report generation
  COMPLETION_PRINT_TEST_RESULTS=true
                            Print completion test output before exit
  COMPLETION_TEST_MODE=summary
                            completion test output: summary|full|off
  COMPLETION_TEST_HEALTH_TIMEOUT_SECONDS=45
                            Timeout for completion MCP health check
  COMPLETION_TEST_REPORT_TIMEOUT_SECONDS=45
                            Timeout for completion ai report print
  ALLOW_ROOT_DEPLOY=true    Allow running this script as root (not recommended)
  BOOT_ESP_MIN_FREE_MB=128  Override minimum required free space on ESP
  RESTORE_GENERATED_REPO_FILES=auto
                            auto: restore only for --analyze-only runs
                            true: always restore generated files on exit
                            false: persist generated files after run
USAGE
}

log() {
  printf '[clean-deploy] %b%s%b\n' "${UI_COLOR_INFO}" "$*" "${UI_COLOR_RESET}"
}

die() {
  printf '[clean-deploy] %bERROR%b: %s\n' "${UI_COLOR_ERROR}" "${UI_COLOR_RESET}" "$*" >&2
  exit 1
}

section() {
  printf '\n[clean-deploy] %b%s%b\n' "${UI_COLOR_SECTION}" "==== $* ====" "${UI_COLOR_RESET}"
}

log_success() {
  printf '[clean-deploy] %bOK%b: %s\n' "${UI_COLOR_SUCCESS}" "${UI_COLOR_RESET}" "$*"
}

log_warn() {
  printf '[clean-deploy] %bWARN%b: %s\n' "${UI_COLOR_WARN}" "${UI_COLOR_RESET}" "$*"
}

setup_ui() {
  UI_COLOR_RESET=""
  UI_COLOR_INFO=""
  UI_COLOR_SECTION=""
  UI_COLOR_SUCCESS=""
  UI_COLOR_WARN=""
  UI_COLOR_ERROR=""
  if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
    UI_COLOR_RESET=$'\033[0m'
    UI_COLOR_INFO=$'\033[1;37m'
    UI_COLOR_SECTION=$'\033[1;36m'
    UI_COLOR_SUCCESS=$'\033[1;32m'
    UI_COLOR_WARN=$'\033[1;33m'
    UI_COLOR_ERROR=$'\033[1;31m'
  fi
}

has_timeout_cmd() {
  command -v timeout >/dev/null 2>&1
}

run_with_timeout_if_available() {
  local timeout_secs="$1"
  shift
  if has_timeout_cmd && [[ "${timeout_secs}" =~ ^[0-9]+$ ]] && (( timeout_secs > 0 )); then
    timeout "${timeout_secs}" "$@"
  else
    "$@"
  fi
}

run_timed_step() {
  local label="$1"
  shift
  local start_epoch end_epoch rc duration
  log ">> ${label} (start)"
  start_epoch="$(date +%s)"
  set +e
  "$@"
  rc=$?
  set -e
  end_epoch="$(date +%s)"
  duration=$(( end_epoch - start_epoch ))
  PHASE_TIMINGS+=("${label}:${duration}:${rc}")
  if [[ "${rc}" -eq 0 ]]; then
    log_success "${label} completed in ${duration}s"
  else
    log_warn "${label} failed in ${duration}s (rc=${rc})"
  fi
  return "${rc}"
}

discovery_cache_file() {
  local cache_root host_s profile_s
  cache_root="${XDG_CACHE_HOME:-${HOME}/.cache}/nixos-quick-deploy"
  host_s="$(printf '%s' "${HOST_NAME}" | tr -c '[:alnum:]._-' '_')"
  profile_s="$(printf '%s' "${PROFILE}" | tr -c '[:alnum:]._-' '_')"
  printf '%s/discovery-%s-%s.stamp\n' "${cache_root}" "${host_s}" "${profile_s}"
}

should_skip_discovery_by_cache() {
  [[ "${RUN_DISCOVERY}" == true ]] || return 1
  [[ "${DISCOVERY_CACHE_TTL_SECONDS}" =~ ^[0-9]+$ ]] || return 1
  (( DISCOVERY_CACHE_TTL_SECONDS > 0 )) || return 1

  # Any explicit AI override means discovery should run and refresh facts.
  if [[ -n "${AI_STACK_ENABLED_OVERRIDE:-}" || -n "${AI_BACKEND_OVERRIDE:-}" || -n "${AI_MODELS_OVERRIDE:-}" ||
        -n "${AI_UI_ENABLED_OVERRIDE:-}" || -n "${AI_VECTOR_DB_ENABLED_OVERRIDE:-}" ]]; then
    return 1
  fi

  local facts_file cache_file last_run now_epoch age
  facts_file="${REPO_ROOT}/nix/hosts/${HOST_NAME}/facts.nix"
  [[ -f "${facts_file}" ]] || return 1

  cache_file="$(discovery_cache_file)"
  [[ -f "${cache_file}" ]] || return 1
  last_run="$(cat "${cache_file}" 2>/dev/null || true)"
  [[ "${last_run}" =~ ^[0-9]+$ ]] || return 1

  now_epoch="$(date +%s)"
  age=$(( now_epoch - last_run ))
  (( age < DISCOVERY_CACHE_TTL_SECONDS ))
}

mark_discovery_cache() {
  local cache_file cache_root
  cache_file="$(discovery_cache_file)"
  cache_root="$(dirname "${cache_file}")"
  mkdir -p "${cache_root}" 2>/dev/null || true
  date +%s > "${cache_file}" 2>/dev/null || true
}

print_deploy_completion_summary() {
  local end_epoch elapsed
  end_epoch="$(date +%s)"
  elapsed=$(( end_epoch - DEPLOY_START_EPOCH ))
  log "Execution time: ${elapsed}s"

  local telemetry_dir latest_report latest_converge latest_tooling
  telemetry_dir="${AI_STACK_DATA_DIR}/hybrid/telemetry"
  latest_report="${telemetry_dir}/latest-aq-report.json"
  latest_converge="${telemetry_dir}/post-deploy-converge-latest.json"
  latest_tooling="${telemetry_dir}/ai-tooling-prime-latest.json"

  if [[ -f "${latest_report}" ]]; then
    log "Latest report snapshot: ${latest_report}"
  fi
  if [[ -f "${latest_converge}" ]]; then
    log "Latest convergence summary: ${latest_converge}"
  fi
  if [[ -f "${latest_tooling}" ]]; then
    log "Latest tooling snapshot: ${latest_tooling}"
  fi

  if (( ${#PHASE_TIMINGS[@]} > 0 )); then
    log "Phase timings:"
    printf '[clean-deploy]   %-38s %-8s %-6s\n' "Step" "Duration" "RC"
    printf '[clean-deploy]   %-38s %-8s %-6s\n' "--------------------------------------" "--------" "------"
    local item label duration rc
    for item in "${PHASE_TIMINGS[@]}"; do
      label="${item%%:*}"
      duration="$(printf '%s' "${item}" | cut -d: -f2)"
      rc="$(printf '%s' "${item}" | cut -d: -f3)"
      printf '[clean-deploy]   %-38s %-8s %-6s\n' "${label}" "${duration}s" "${rc}"
    done
  fi
}

print_completion_test_results() {
  [[ "${RUN_HEALTH_CHECK}" == true ]] || return 0
  [[ "${COMPLETION_PRINT_TEST_RESULTS}" == "true" ]] || return 0
  [[ "${COMPLETION_TEST_MODE}" != "off" ]] || return 0

  local health_script="${REPO_ROOT}/scripts/testing/check-mcp-health.sh"
  local report_script="${REPO_ROOT}/scripts/ai/aq-report"
  local qa_script="${REPO_ROOT}/scripts/ai/aq-qa"
  local output

  _print_report_summary_from_json() {
    local json="$1"
    local routing_local routing_remote cache_hit hint_rate eval_latest eval_trend
    local intent_cov security_cache recommendations top_hint top_hint_count
    local semantic_route_calls hint_diversity_status hint_dominant_share hint_unique
    local i=0

    routing_local="$(printf '%s' "${json}" | jq -r '.routing.local_n // 0')"
    routing_remote="$(printf '%s' "${json}" | jq -r '.routing.remote_n // 0')"
    cache_hit="$(printf '%s' "${json}" | jq -r '.cache.hit_pct // 0')"
    hint_rate="$(printf '%s' "${json}" | jq -r '.hint_adoption.adoption_pct // 0')"
    eval_latest="$(printf '%s' "${json}" | jq -r '.eval_trend.latest_pct // "n/a"')"
    eval_trend="$(printf '%s' "${json}" | jq -r '.eval_trend.trend // "unknown"')"
    intent_cov="$(printf '%s' "${json}" | jq -r '.intent_contract_compliance.contract_coverage_pct // "n/a"')"
    security_cache="$(printf '%s' "${json}" | jq -r '.tool_security_auditor.cache_hit_pct // "n/a"')"
    semantic_route_calls="$(printf '%s' "${json}" | jq -r '.semantic_tooling_autorun.route_calls // 0')"
    hint_unique="$(printf '%s' "${json}" | jq -r '.hint_diversity.unique_hints // 0')"
    hint_dominant_share="$(printf '%s' "${json}" | jq -r '.hint_diversity.dominant_share_pct // "n/a"')"
    hint_diversity_status="$(printf '%s' "${json}" | jq -r '.hint_diversity.status // "unknown"')"
    top_hint="$(printf '%s' "${json}" | jq -r '.hint_adoption.top_hints[0][0] // "none"')"
    top_hint_count="$(printf '%s' "${json}" | jq -r '.hint_adoption.top_hints[0][1] // 0')"
    recommendations="$(printf '%s' "${json}" | jq -r '.recommendations[0:3][]?')"

    log "AI stack report (summary):"
    printf '  %-28s %s\n' "Routing" "local=${routing_local} remote=${routing_remote}"
    printf '  %-28s %s%%\n' "Semantic cache hit rate" "${cache_hit}"
    printf '  %-28s %s%%\n' "Hint adoption success" "${hint_rate}"
    printf '  %-28s %s (unique=%s dominant=%s%%)\n' "Hint diversity" "${hint_diversity_status}" "${hint_unique}" "${hint_dominant_share}"
    printf '  %-28s %s%% (%s)\n' "Eval latest" "${eval_latest}" "${eval_trend}"
    printf '  %-28s %s%%\n' "Intent-contract coverage" "${intent_cov}"
    printf '  %-28s %s%%\n' "Security-auditor cache hit" "${security_cache}"
    printf '  %-28s %s\n' "Semantic autorun route calls" "${semantic_route_calls}"
    printf '  %-28s %sx %s\n' "Top hint" "${top_hint_count}" "${top_hint}"

    if [[ -n "${recommendations}" ]]; then
      log "Top recommended next actions:"
      while IFS= read -r rec; do
        [[ -z "${rec}" ]] && continue
        i=$((i + 1))
        if (( ${#rec} > 180 )); then
          rec="${rec:0:177}..."
        fi
        printf '  %d. %s\n' "${i}" "${rec}"
      done <<< "${recommendations}"
    fi
  }

  section "Completion Tests"

  if [[ -x "${health_script}" ]]; then
    if [[ "${COMPLETION_TEST_MODE}" == "full" ]]; then
      log "MCP health (full):"
      run_with_timeout_if_available "${COMPLETION_TEST_HEALTH_TIMEOUT_SECONDS}" \
        "${health_script}" --optional || true
    else
      output="$(
        run_with_timeout_if_available "${COMPLETION_TEST_HEALTH_TIMEOUT_SECONDS}" \
          "${health_script}" --optional 2>&1 || true
      )"
      log "MCP health (summary):"
      printf '%s\n' "${output}" | awk '/^Result:|^All required MCP services are healthy\.|^Optional:/{print}'
    fi
  fi

  if [[ -x "${report_script}" ]]; then
    if [[ "${COMPLETION_TEST_MODE}" == "full" ]]; then
      log "AI stack report (full):"
      run_with_timeout_if_available "${COMPLETION_TEST_REPORT_TIMEOUT_SECONDS}" \
        "${report_script}" --since=7d --format=text 2>/dev/null || true
    else
      if command -v jq >/dev/null 2>&1; then
        output="$(
          run_with_timeout_if_available "${COMPLETION_TEST_REPORT_TIMEOUT_SECONDS}" \
            "${report_script}" --since=7d --format=json 2>/dev/null || true
        )"
        if [[ -n "${output}" ]] && printf '%s' "${output}" | jq -e '.' >/dev/null 2>&1; then
          _print_report_summary_from_json "${output}"
        else
          log_warn "AI report JSON summary unavailable; using text fallback."
          output="$(
            run_with_timeout_if_available "${COMPLETION_TEST_REPORT_TIMEOUT_SECONDS}" \
              "${report_script}" --since=7d --format=text 2>/dev/null || true
          )"
          log "AI stack report (summary):"
          printf '%s\n' "${output}" \
            | awk '/^\[ 2\. Routing Split \]/, /^\[ 3\./ { if ($0 !~ /^\[ 3\./) print }'
          printf '%s\n' "${output}" \
            | awk '/^\[ 3\. Semantic Cache \]/, /^\[ 4\./ { if ($0 !~ /^\[ 4\./) print }'
          printf '%s\n' "${output}" \
            | awk '/^\[ 9\. Hint Adoption/, /^\[ 10\./ { if ($0 !~ /^\[ 10\./) print }'
        fi
      else
        output="$(
          run_with_timeout_if_available "${COMPLETION_TEST_REPORT_TIMEOUT_SECONDS}" \
            "${report_script}" --since=7d --format=text 2>/dev/null || true
        )"
        log "AI stack report (summary):"
        printf '%s\n' "${output}" \
          | awk '/^\[ 2\. Routing Split \]/, /^\[ 3\./ { if ($0 !~ /^\[ 3\./) print }'
        printf '%s\n' "${output}" \
          | awk '/^\[ 3\. Semantic Cache \]/, /^\[ 4\./ { if ($0 !~ /^\[ 4\./) print }'
        printf '%s\n' "${output}" \
          | awk '/^\[ 9\. Hint Adoption/, /^\[ 10\./ { if ($0 !~ /^\[ 10\./) print }'
      fi
    fi
  fi

  if [[ -x "${qa_script}" ]]; then
    output="$(
      run_with_timeout_if_available "${COMPLETION_TEST_HEALTH_TIMEOUT_SECONDS}" \
        "${qa_script}" 0 --json 2>/dev/null || true
    )"
    if [[ -n "${output}" ]] && command -v jq >/dev/null 2>&1 && printf '%s' "${output}" | jq -e '.' >/dev/null 2>&1; then
      log "AI stack QA phase 0:"
      printf '  %-28s %s\n' "Pass" "$(printf '%s' "${output}" | jq -r '.pass // 0')"
      printf '  %-28s %s\n' "Fail" "$(printf '%s' "${output}" | jq -r '.fail // 0')"
      printf '  %-28s %s\n' "Skip" "$(printf '%s' "${output}" | jq -r '.skip // 0')"
    else
      log_warn "AI stack QA phase 0 summary unavailable."
    fi
  fi
}

run_script_runtime_contract_check() {
  local required=(
    run_timed_step
    persist_home_git_credentials_declarative
    run_discovery_step
    run_pre_deploy_validation_loop
    prime_sudo_session
  )
  local missing=()
  local fn
  for fn in "${required[@]}"; do
    if ! declare -F "${fn}" >/dev/null 2>&1; then
      missing+=("${fn}")
    fi
  done
  if (( ${#missing[@]} > 0 )); then
    die "Script runtime contract failed: missing functions: ${missing[*]}"
  fi
  log "Script runtime contract validated: ${#required[@]} required functions present"
}

load_service_endpoints() {
  local endpoints_file="${REPO_ROOT}/config/service-endpoints.sh"
  if [[ -f "${endpoints_file}" ]]; then
    # shellcheck source=config/service-endpoints.sh
    source "${endpoints_file}"
  fi
}

resolve_hybrid_api_key() {
  local key="${HYBRID_API_KEY:-}"
  local key_file="${HYBRID_API_KEY_FILE:-/run/secrets/hybrid_coordinator_api_key}"
  if [[ -z "${key}" && -r "${key_file}" ]]; then
    key="$(tr -d '[:space:]' < "${key_file}")"
  fi
  if [[ -z "${key}" && -r "/run/secrets/hybrid_api_key" ]]; then
    key="$(tr -d '[:space:]' < /run/secrets/hybrid_api_key)"
  fi
  printf '%s' "${key}"
}

hybrid_post_json_capture() {
  local endpoint="$1"
  local payload="$2"
  local output_file="$3"
  local api_key="$4"
  local -a curl_args=(
    -sS
    -o "${output_file}"
    -w "%{http_code}"
    --connect-timeout 3
    --max-time "${POST_SWITCH_REPO_CAPABILITY_VERIFY_TIMEOUT_SECONDS}"
    -H "Content-Type: application/json"
    -X POST
  )
  if [[ -n "${api_key}" ]]; then
    curl_args+=(-H "X-API-Key: ${api_key}")
  fi
  curl "${curl_args[@]}" "${HYBRID_URL%/}${endpoint}" -d "${payload}"
}

verify_repo_backed_ai_service_capabilities_once() {
  load_service_endpoints

  if ! command -v curl >/dev/null 2>&1; then
    die "curl is required to verify repo-backed AI service capabilities."
  fi
  if ! command -v python3 >/dev/null 2>&1; then
    die "python3 is required to verify repo-backed AI service capabilities."
  fi

  if ! systemd_unit_declared ai-hybrid-coordinator.service; then
    log "Skipping repo-backed AI capability verification: ai-hybrid-coordinator.service is not declared"
    return 0
  fi

  if ! systemd_unit_enabled_or_running ai-hybrid-coordinator.service; then
    log "Skipping repo-backed AI capability verification: ai-hybrid-coordinator.service is not enabled for this host"
    return 0
  fi

  local hybrid_api_key workflow_plan_body qa_check_body learning_export_body http_code
  hybrid_api_key="$(resolve_hybrid_api_key)"
  if [[ -z "${hybrid_api_key}" ]]; then
    die "Unable to verify repo-backed AI service capabilities: missing hybrid coordinator API key."
  fi

  workflow_plan_body="$(mktemp)"
  qa_check_body="$(mktemp)"
  learning_export_body="$(mktemp)"
  chmod 0600 "${workflow_plan_body}" "${qa_check_body}" "${learning_export_body}"

  http_code="$(hybrid_post_json_capture \
    "/workflow/plan" \
    '{"query":"validate deploy health and smoke checks after patch"}' \
    "${workflow_plan_body}" \
    "${hybrid_api_key}" || true)"
  if [[ ! "${http_code}" =~ ^2 ]]; then
    log_warn "Repo-backed AI capability check failed: /workflow/plan returned HTTP ${http_code}"
    sed -n '1,40p' "${workflow_plan_body}" >&2 || true
    rm -f "${workflow_plan_body}" "${qa_check_body}" "${learning_export_body}"
    return 1
  fi
  if ! python3 - "${workflow_plan_body}" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as handle:
    payload = json.load(handle)

phases = payload.get("phases", [])
validate_phase = next((phase for phase in phases if phase.get("id") == "validate"), {})
tools = set()
for tool in validate_phase.get("tools", []):
    if isinstance(tool, str):
        name = tool.strip()
    elif isinstance(tool, dict):
        name = str(tool.get("name", "")).strip()
    else:
        name = ""
    if name:
        tools.add(name)
metadata = payload.get("metadata", {})
prompt_coaching = metadata.get("prompt_coaching")

if "qa_check" not in tools:
    raise SystemExit(1)
if not isinstance(prompt_coaching, dict):
    raise SystemExit(2)
PY
  then
    log_warn "Repo-backed AI capability check failed: /workflow/plan is missing validate.qa_check or metadata.prompt_coaching"
    sed -n '1,80p' "${workflow_plan_body}" >&2 || true
    rm -f "${workflow_plan_body}" "${qa_check_body}" "${learning_export_body}"
    return 1
  fi

  http_code="$(hybrid_post_json_capture \
    "/qa/check" \
    '{"phase":"0","format":"json","timeout_seconds":30}' \
    "${qa_check_body}" \
    "${hybrid_api_key}" || true)"
  if [[ ! "${http_code}" =~ ^2 ]]; then
    log_warn "Repo-backed AI capability check failed: /qa/check returned HTTP ${http_code}"
    sed -n '1,80p' "${qa_check_body}" >&2 || true
    rm -f "${workflow_plan_body}" "${qa_check_body}" "${learning_export_body}"
    return 1
  fi
  if ! python3 - "${qa_check_body}" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as handle:
    payload = json.load(handle)

if payload.get("status") != "ok":
    raise SystemExit(1)
PY
  then
    log_warn "Repo-backed AI capability check failed: /qa/check did not return status=ok"
    sed -n '1,80p' "${qa_check_body}" >&2 || true
    rm -f "${workflow_plan_body}" "${qa_check_body}" "${learning_export_body}"
    return 1
  fi

  http_code="$(hybrid_post_json_capture \
    "/learning/export" \
    '{}' \
    "${learning_export_body}" \
    "${hybrid_api_key}" || true)"
  if [[ ! "${http_code}" =~ ^2 ]]; then
    log_warn "Repo-backed AI capability check failed: /learning/export returned HTTP ${http_code}"
    sed -n '1,80p' "${learning_export_body}" >&2 || true
    rm -f "${workflow_plan_body}" "${qa_check_body}" "${learning_export_body}"
    return 1
  fi
  if ! python3 - "${learning_export_body}" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as handle:
    payload = json.load(handle)

dataset_path = payload.get("dataset_path")
if payload.get("status") != "ok":
    raise SystemExit(1)
if not isinstance(dataset_path, str) or not dataset_path.strip():
    raise SystemExit(2)
PY
  then
    log_warn "Repo-backed AI capability check failed: /learning/export did not return status=ok with dataset_path"
    sed -n '1,80p' "${learning_export_body}" >&2 || true
    rm -f "${workflow_plan_body}" "${qa_check_body}" "${learning_export_body}"
    return 1
  fi

  rm -f "${workflow_plan_body}" "${qa_check_body}" "${learning_export_body}"
  log "Repo-backed AI capability verification passed: workflow plan, qa_check, learning export"
}

resolve_configured_repo_path() {
  nix_eval_raw_safe "${FLAKE_REF}#nixosConfigurations.\"${NIXOS_TARGET}\".config.mySystem.mcpServers.repoPath" 2>/dev/null || true
}

systemd_unit_declared() {
  local unit="$1"
  systemctl list-unit-files "${unit}" >/dev/null 2>&1
}

systemd_unit_enabled_or_running() {
  local unit="$1"
  systemctl is-enabled --quiet "${unit}" 2>/dev/null || \
    systemctl is-active --quiet "${unit}" 2>/dev/null || \
    systemctl is-activating --quiet "${unit}" 2>/dev/null
}

should_manage_repo_backed_ai_services() {
  local action_label="${1:-repo-backed AI service action}"
  local configured_repo="" current_repo=""

  [[ "${MODE}" == "switch" ]] || return 1
  [[ "${SKIP_SYSTEM_SWITCH}" == false ]] || return 1

  if ! command -v systemctl >/dev/null 2>&1; then
    return 1
  fi

  configured_repo="$(resolve_configured_repo_path)"
  current_repo="$(readlink -f "${REPO_ROOT}" 2>/dev/null || printf '%s\n' "${REPO_ROOT}")"

  if [[ -z "${configured_repo}" ]]; then
    log "Skipping mutable repo-backed AI ${action_label}: unable to resolve configured repoPath"
    return 1
  fi

  configured_repo="$(readlink -f "${configured_repo}" 2>/dev/null || printf '%s\n' "${configured_repo}")"
  if [[ "${configured_repo}" != "${current_repo}" ]]; then
    log "Skipping mutable repo-backed AI ${action_label}: configured repoPath (${configured_repo}) does not match deploy repo (${current_repo})"
    return 1
  fi

  return 0
}

restart_repo_backed_ai_services_if_needed() {
  if ! should_manage_repo_backed_ai_services "service restart"; then
    return 0
  fi

  local -a candidates=(
    "ai-aidb.service"
    "ai-hybrid-coordinator.service"
    "ai-ralph-wiggum.service"
    "ai-aider-wrapper.service"
    "ai-nixos-docs.service"
  )
  local -a restart_units=()
  local unit=""

  for unit in "${candidates[@]}"; do
    if ! systemd_unit_declared "${unit}"; then
      continue
    fi
    if systemd_unit_enabled_or_running "${unit}"; then
      restart_units+=("${unit}")
    fi
  done

  if (( ${#restart_units[@]} == 0 )); then
    log "No mutable repo-backed AI services required restart"
    return 0
  fi

  log "Restarting mutable repo-backed AI services so live processes pick up checkout changes"
  if has_timeout_cmd && [[ "${POST_SWITCH_REPO_SERVICE_RESTART_TIMEOUT_SECONDS}" =~ ^[0-9]+$ ]] && \
     (( POST_SWITCH_REPO_SERVICE_RESTART_TIMEOUT_SECONDS > 0 )); then
    if run_privileged timeout "${POST_SWITCH_REPO_SERVICE_RESTART_TIMEOUT_SECONDS}" \
        systemctl restart "${restart_units[@]}"; then
      log "Mutable repo-backed AI services restarted: ${restart_units[*]}"
    else
      die "Mutable repo-backed AI service restart failed: ${restart_units[*]}"
    fi
  elif run_privileged systemctl restart "${restart_units[@]}"; then
    log "Mutable repo-backed AI services restarted: ${restart_units[*]}"
  else
    die "Mutable repo-backed AI service restart failed: ${restart_units[*]}"
  fi
}

verify_repo_backed_ai_services_are_live_if_needed() {
  local attempts attempt
  if ! should_manage_repo_backed_ai_services "capability verification"; then
    return 0
  fi

  attempts="${POST_SWITCH_REPO_CAPABILITY_RETRY_COUNT}"
  if [[ ! "${attempts}" =~ ^[0-9]+$ ]] || (( attempts < 1 )); then
    attempts=1
  fi

  for (( attempt=1; attempt<=attempts; attempt++ )); do
    if verify_repo_backed_ai_service_capabilities_once; then
      return 0
    fi

    if (( attempt < attempts )); then
      log_warn "Repo-backed AI capability verification failed on attempt ${attempt}/${attempts}; restarting services and retrying"
      restart_repo_backed_ai_services_if_needed
      wait_for_ai_services
    fi
  done

  die "Mutable repo-backed AI service capability verification failed after ${attempts} attempt(s)."
}

run_declarative_postflight_converge() {
  [[ "${MODE}" != "build" ]] || return 0
  [[ "${RUN_HEALTH_CHECK}" == true ]] || return 0

  if ! command -v systemctl >/dev/null 2>&1; then
    return 1
  fi
  if ! systemctl list-unit-files ai-post-deploy-converge.service >/dev/null 2>&1; then
    return 1
  fi

  log "Dispatching declarative post-flight convergence service"
  if run_privileged systemctl start --no-block ai-post-deploy-converge.service; then
    sleep "${POST_FLIGHT_CONVERGE_START_DELAY_SECONDS}"
    log "Declarative convergence service triggered asynchronously"
    return 0
  fi

  log "WARNING: Failed to trigger ai-post-deploy-converge.service; falling back to inline post-flight tasks."
  return 1
}

run_nonfatal_postflight_check() {
  local start_message="$1"
  local success_message="$2"
  local failure_message="$3"
  shift 3

  log "${start_message}"
  if "$@"; then
    log "${success_message}"
  else
    log "${failure_message}"
  fi
}

run_inline_postflight_script_if_present() {
  local script_path="$1"
  local start_message="$2"
  local timeout_seconds="$3"
  shift 3

  [[ -x "${script_path}" ]] || return 0
  log "${start_message}"
  run_with_timeout_if_available "${timeout_seconds}" "${script_path}" "$@" 2>/dev/null || true
}

run_postflight_convergence() {
  local run_inline_postflight=true

  section "Post-flight Convergence"
  if [[ "${POST_FLIGHT_MODE}" == "declarative" || "${POST_FLIGHT_MODE}" == "both" ]]; then
    if run_declarative_postflight_converge; then
      if [[ "${POST_FLIGHT_MODE}" == "declarative" ]]; then
        run_inline_postflight=false
      fi
    fi
  fi

  if [[ "${run_inline_postflight}" != true ]]; then
    return 0
  fi

  run_inline_postflight_script_if_present \
    "${REPO_ROOT}/scripts/automation/prime-ai-tooling-defaults.sh" \
    "Priming AI harness tooling defaults..." \
    "${POST_FLIGHT_REPORT_TIMEOUT_SECONDS}"

  # Sends a small batch of queries through hybrid-coordinator so routing split
  # and semantic cache metrics are populated after each deploy.
  run_inline_postflight_script_if_present \
    "${REPO_ROOT}/scripts/data/seed-routing-traffic.sh" \
    "Seeding routing traffic (bootstrap §2/§3 metrics)..." \
    "${POST_FLIGHT_SEED_TIMEOUT_SECONDS}" \
    --count 4

  # Re-indexes any documents that were imported but not yet embedded.
  run_inline_postflight_script_if_present \
    "${REPO_ROOT}/scripts/data/rebuild-qdrant-collections.sh" \
    "Rebuilding Qdrant vector index from AIDB documents..." \
    "${POST_FLIGHT_REBUILD_TIMEOUT_SECONDS}"

  run_inline_postflight_script_if_present \
    "${REPO_ROOT}/scripts/ai/aq-report" \
    "AI stack performance digest (last 7d):" \
    "${POST_FLIGHT_REPORT_TIMEOUT_SECONDS}" \
    --since=7d --format=text
}

current_system_generation() {
  readlink -f /nix/var/nix/profiles/system 2>/dev/null || true
}

current_home_generation() {
  local home_profile="${HOME_MANAGER_PROFILE_PATH:-$HOME/.local/state/nix/profiles/home-manager}"
  readlink -f "$home_profile" 2>/dev/null || true
}

assert_post_switch_desktop_outcomes() {
  [[ "${MODE}" == "switch" ]] || return 0
  [[ "${SKIP_SYSTEM_SWITCH}" == false ]] || return 0

  local desktop_enabled="false"
  desktop_enabled="$(nix_eval_raw_safe "${FLAKE_REF}#nixosConfigurations.${NIXOS_TARGET}.config.mySystem.roles.desktop.enable" 2>/dev/null || true)"
  if [[ "${desktop_enabled}" != "true" ]]; then
    return 0
  fi

  local cosmic_session="/run/current-system/sw/share/wayland-sessions/cosmic.desktop"
  if [[ ! -f "${cosmic_session}" ]]; then
    die "Desktop role is enabled but COSMIC session file is missing (${cosmic_session}). nixos-rebuild switch may not have applied the intended desktop generation."
  fi

  if command -v systemctl >/dev/null 2>&1; then
    if ! systemctl is-enabled --quiet display-manager 2>/dev/null; then
      die "Desktop role is enabled but display-manager is not enabled after switch."
    fi
  fi
}

assert_non_root_entrypoint() {
  if [[ "${EUID:-$(id -u)}" -eq 0 && "${ALLOW_ROOT_DEPLOY:-false}" != "true" ]]; then
    die "Do not run nixos-quick-deploy.sh as root/sudo. Run as your normal user; the script escalates only privileged steps. Override only if required: ALLOW_ROOT_DEPLOY=true."
  fi
}

require_command() {
  local cmd="$1"
  command -v "$cmd" >/dev/null 2>&1 || die "'${cmd}' is required"
}

run_git_safe() {
  if command -v git >/dev/null 2>&1; then
    git "$@"
    return
  fi

  if [[ -x "${REPO_ROOT}/scripts/governance/git-safe.sh" ]]; then
    "${REPO_ROOT}/scripts/governance/git-safe.sh" "$@"
    return
  fi

  if command -v nix >/dev/null 2>&1; then
    nix --extra-experimental-features 'nix-command flakes' shell nixpkgs#git --command git "$@"
    return
  fi

  return 127
}

resolve_local_flake_path() {
  local ref="${1:-}"
  case "$ref" in
    path:*) printf '%s\n' "${ref#path:}" ;;
    /*) printf '%s\n' "$ref" ;;
    .|./*|../*)
      (cd "$ref" >/dev/null 2>&1 && pwd) || true
      ;;
    *) ;;
  esac
}


list_flake_hosts() {
  local flake_path
  flake_path="$(resolve_local_flake_path "$FLAKE_REF")"
  [[ -n "$flake_path" && -d "$flake_path/nix/hosts" ]] || return 0

  find "$flake_path/nix/hosts" -mindepth 1 -maxdepth 1 -type d -printf '%f\n'     | while IFS= read -r host; do
        [[ -f "$flake_path/nix/hosts/$host/default.nix" ]] && printf '%s\n' "$host"
      done     | sort -u
}

resolve_host_from_flake_if_needed() {
  [[ "$HOST_EXPLICIT" == true ]] && return 0

  local flake_path host_dir
  flake_path="$(resolve_local_flake_path "$FLAKE_REF")"
  [[ -n "$flake_path" ]] || return 0

  host_dir="$flake_path/nix/hosts/$HOST_NAME"
  if [[ -d "$host_dir" && -f "$host_dir/default.nix" ]]; then
    return 0
  fi

  local -a detected_hosts=()
  mapfile -t detected_hosts < <(list_flake_hosts)
  if [[ ${#detected_hosts[@]} -eq 1 ]]; then
    log "Host '${HOST_NAME}' not found in flake; using discovered host '${detected_hosts[0]}'"
    HOST_NAME="${detected_hosts[0]}"
  fi
}

list_configuration_names() {
  local attrset="$1"
  nix eval --json "${FLAKE_REF}#${attrset}" --apply 'x: builtins.attrNames x' 2>/dev/null \
    | tr -d '[]\" ' | tr ',' ' '
}

has_configuration_name() {
  local attrset="$1"
  local target="$2"
  local names
  names="$(list_configuration_names "$attrset")"
  [[ " ${names} " == *" ${target} "* ]]
}

ensure_flake_visible_to_nix() {
  local ref="${1:-}"
  local flake_path
  flake_path="$(resolve_local_flake_path "$ref")"
  [[ -n "$flake_path" ]] || return 0
  [[ -d "$flake_path" ]] || return 0

  if ! run_git_safe -C "$flake_path" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    return 0
  fi

  local -a scope=(flake.nix flake.lock nix)
  local -a untracked=()

  while IFS= read -r path; do
    [[ -n "${path}" ]] || continue
    untracked+=("${path}")
  done < <(run_git_safe -C "$flake_path" ls-files --others --exclude-standard -- "${scope[@]}" 2>/dev/null || true)

  if (( ${#untracked[@]} == 0 )); then
    return 0
  fi

  log "Temporarily staging ${#untracked[@]} untracked flake file(s) so Nix can evaluate local config"
  run_git_safe -C "$flake_path" add -- "${untracked[@]}"
  AUTO_STAGED_FLAKE_PATH="$flake_path"
  AUTO_STAGED_FLAKE_FILES=("${untracked[@]}")
}

cleanup_auto_staged_flake_files() {
  if [[ -z "${AUTO_STAGED_FLAKE_PATH}" || ${#AUTO_STAGED_FLAKE_FILES[@]} -eq 0 ]]; then
    return 0
  fi

  if run_git_safe -C "${AUTO_STAGED_FLAKE_PATH}" restore --staged -- "${AUTO_STAGED_FLAKE_FILES[@]}" >/dev/null 2>&1; then
    log "Restored git index after temporary flake staging"
    return 0
  fi

  if run_git_safe -C "${AUTO_STAGED_FLAKE_PATH}" reset -q -- "${AUTO_STAGED_FLAKE_FILES[@]}" >/dev/null 2>&1; then
    log "Restored git index after temporary flake staging"
    return 0
  fi

  log "Could not automatically unstage temporary flake files; run: git -C '${AUTO_STAGED_FLAKE_PATH}' restore --staged -- ${AUTO_STAGED_FLAKE_FILES[*]}"
}


snapshot_generated_repo_files() {
  [[ "${RESTORE_GENERATED_REPO_FILES}" == "true" ]] || return 0

  local flake_path host_dir
  flake_path="$(resolve_local_flake_path "${FLAKE_REF}")"
  [[ -n "${flake_path}" && -d "${flake_path}" ]] || return 0

  if ! run_git_safe -C "${flake_path}" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    return 0
  fi

  host_dir="${flake_path}/nix/hosts/${HOST_NAME}"
  [[ -d "${host_dir}" ]] || return 0

  GENERATED_FILE_SNAPSHOT_DIR="$(mktemp -d)"
  GENERATED_FILE_SNAPSHOT_TARGETS=(
    "${host_dir}/facts.nix"
    "${host_dir}/home-deploy-options.nix"
  )

  local target key
  for target in "${GENERATED_FILE_SNAPSHOT_TARGETS[@]}"; do
    key="$(printf '%s' "${target}" | sha256sum | awk '{print $1}')"
    if [[ -f "${target}" ]]; then
      cp -f "${target}" "${GENERATED_FILE_SNAPSHOT_DIR}/${key}.snapshot"
      printf 'present\n' > "${GENERATED_FILE_SNAPSHOT_DIR}/${key}.state"
    else
      printf 'absent\n' > "${GENERATED_FILE_SNAPSHOT_DIR}/${key}.state"
    fi
  done
}

restore_generated_repo_files() {
  [[ "${RESTORE_GENERATED_REPO_FILES}" == "true" ]] || return 0
  [[ -n "${GENERATED_FILE_SNAPSHOT_DIR}" && -d "${GENERATED_FILE_SNAPSHOT_DIR}" ]] || return 0

  local target key state
  for target in "${GENERATED_FILE_SNAPSHOT_TARGETS[@]}"; do
    key="$(printf '%s' "${target}" | sha256sum | awk '{print $1}')"
    state="$(cat "${GENERATED_FILE_SNAPSHOT_DIR}/${key}.state" 2>/dev/null || echo absent)"

    if [[ "${state}" == "present" ]]; then
      if ! install -m 0644 "${GENERATED_FILE_SNAPSHOT_DIR}/${key}.snapshot" "${target}"; then
        log "WARNING: Failed to restore generated file snapshot: ${target}"
      fi
    else
      if ! rm -f "${target}" >/dev/null 2>&1; then
        log "WARNING: Failed to remove generated file on cleanup: ${target}"
      fi
    fi
  done

  rm -rf "${GENERATED_FILE_SNAPSHOT_DIR}" >/dev/null 2>&1 || true
  GENERATED_FILE_SNAPSHOT_DIR=""
  return 0
}

cleanup_on_exit() {
  if [[ -n "${SUDO_KEEPALIVE_PID}" ]] && kill -0 "${SUDO_KEEPALIVE_PID}" >/dev/null 2>&1; then
    kill "${SUDO_KEEPALIVE_PID}" >/dev/null 2>&1 || true
  fi
  cleanup_auto_staged_flake_files
  restore_generated_repo_files
}

on_unexpected_error() {
  local rc="${1:-1}"
  local line="${2:-unknown}"
  local cmd="${3:-unknown}"

  log "Deployment failed at line ${line} (exit=${rc}): ${cmd}"
  log "Cleanup trap executed (temporary git index / generated file projections restored as configured)."

  if [[ "${MODE:-switch}" == "switch" ]]; then
    log "Rollback guidance: sudo nixos-rebuild switch --rollback"
    log "If system is degraded, reboot and select a previous generation in the boot menu."
  elif [[ "${MODE:-switch}" == "boot" ]]; then
    log "Boot mode rollback guidance: reboot and select a previous generation in the boot menu."
    log "Optional: sudo nixos-rebuild switch --rollback after boot."
  fi
}

run_roadmap_completion_verification() {
  [[ "${SKIP_ROADMAP_VERIFICATION}" == true ]] && return 0

  local verifier="${REPO_ROOT}/scripts/testing/verify-flake-first-roadmap-completion.sh"
  if [[ ! -x "$verifier" ]]; then
    log "Roadmap-completion verifier missing/not executable (${verifier}); skipping verification."
    return 0
  fi

  log "Running roadmap-completion verification preflight"
  "$verifier"
}

run_readiness_analysis() {
  local analyzer="${REPO_ROOT}/scripts/governance/analyze-clean-deploy-readiness.sh"
  [[ "${RUN_READINESS_ANALYSIS}" == true ]] || return 0

  if [[ ! -x "$analyzer" ]]; then
    log "Readiness analyzer not executable (${analyzer}); skipping readiness preflight."
    return 0
  fi

  local -a args=(
    --host "${HOST_NAME}"
    --profile "${PROFILE}"
    --flake-ref "${FLAKE_REF}"
  )

  if [[ "${UPDATE_FLAKE_LOCK}" == true ]]; then
    args+=(--update-lock)
  fi

  log "Running readiness analysis preflight"
  "${analyzer}" "${args[@]}"
}

run_pre_deploy_validation_loop() {
  [[ "${ENFORCE_PRE_DEPLOY_DRY_RUN}" == true ]] || {
    log "Pre-deploy dry-run gate is disabled (ENFORCE_PRE_DEPLOY_DRY_RUN=false)."
    return 0
  }

  [[ "${SKIP_SYSTEM_SWITCH}" == false ]] || {
    log "Skipping pre-deploy dry-run gate (--skip-system-switch)."
    return 0
  }

  [[ "${MODE}" != "build" ]] || return 0

  [[ "${PRE_DEPLOY_LOOP_MAX_PASSES}" =~ ^[0-9]+$ ]] || die "PRE_DEPLOY_LOOP_MAX_PASSES must be an integer (got '${PRE_DEPLOY_LOOP_MAX_PASSES}')"
  [[ "${PRE_DEPLOY_LOOP_RETRY_SECONDS}" =~ ^[0-9]+$ ]] || die "PRE_DEPLOY_LOOP_RETRY_SECONDS must be an integer (got '${PRE_DEPLOY_LOOP_RETRY_SECONDS}')"
  (( PRE_DEPLOY_LOOP_MAX_PASSES >= 1 )) || die "PRE_DEPLOY_LOOP_MAX_PASSES must be >= 1"

  local remediation_hook="${REPO_ROOT}/scripts/governance/preflight-auto-remediate.sh"
  local pass failed
  for ((pass=1; pass<=PRE_DEPLOY_LOOP_MAX_PASSES; pass++)); do
    failed=0
    if [[ "${PRE_DEPLOY_PARALLEL_VALIDATION}" == "true" &&
          "${SKIP_HOME_SWITCH}" == false &&
          "${ENFORCE_PRE_DEPLOY_HOME_DRY_RUN}" == true ]]; then
      log "Pre-deploy validation loop pass ${pass}/${PRE_DEPLOY_LOOP_MAX_PASSES}: parallel system + Home Manager dry-build"
      local system_pid home_pid system_rc=0 home_rc=0
      (
        nix --extra-experimental-features 'nix-command flakes' build --no-link \
          "${FLAKE_REF}#nixosConfigurations.\"${NIXOS_TARGET}\".config.system.build.toplevel"
      ) &
      system_pid=$!
      ( home_build "${HM_TARGET}" ) &
      home_pid=$!

      wait "${system_pid}" || system_rc=$?
      wait "${home_pid}" || home_rc=$?
      if [[ ${system_rc} -ne 0 || ${home_rc} -ne 0 ]]; then
        failed=1
      fi
    else
      log "Pre-deploy validation loop pass ${pass}/${PRE_DEPLOY_LOOP_MAX_PASSES}: system dry-run"
      if ! nix --extra-experimental-features 'nix-command flakes' build --no-link \
        "${FLAKE_REF}#nixosConfigurations.\"${NIXOS_TARGET}\".config.system.build.toplevel"; then
        failed=1
      fi

      if [[ ${failed} -eq 0 && "${SKIP_HOME_SWITCH}" == false && "${ENFORCE_PRE_DEPLOY_HOME_DRY_RUN}" == true ]]; then
        log "Pre-deploy validation loop pass ${pass}/${PRE_DEPLOY_LOOP_MAX_PASSES}: Home Manager dry-build"
        if ! home_build "${HM_TARGET}"; then
          failed=1
        fi
      elif [[ ${failed} -eq 0 && "${SKIP_HOME_SWITCH}" == false ]]; then
        log "Skipping Home Manager pre-deploy dry-run gate (ENFORCE_PRE_DEPLOY_HOME_DRY_RUN=false)."
      fi
    fi

    if [[ ${failed} -eq 0 ]]; then
      log "Pre-deploy validation loop pass ${pass}/${PRE_DEPLOY_LOOP_MAX_PASSES}: declarative validation"
      if ! bash "${REPO_ROOT}/scripts/testing/validate-runtime-declarative.sh"; then
        failed=1
      fi
    fi

    if [[ ${failed} -eq 0 ]]; then
      log "Pre-deploy validation loop passed on pass ${pass}/${PRE_DEPLOY_LOOP_MAX_PASSES}."
      return 0
    fi

    if [[ "${ENABLE_PREFLIGHT_AUTO_REMEDIATION}" == "true" && -x "${remediation_hook}" ]]; then
      log "Running preflight auto-remediation hook: ${remediation_hook}"
      if ! "${remediation_hook}"; then
        log "Preflight auto-remediation hook failed; continuing to next pass."
      fi
    fi

    if (( pass < PRE_DEPLOY_LOOP_MAX_PASSES )); then
      log "Pre-deploy validation loop failed on pass ${pass}; retrying in ${PRE_DEPLOY_LOOP_RETRY_SECONDS}s."
      sleep "${PRE_DEPLOY_LOOP_RETRY_SECONDS}"
    fi
  done

  die "Pre-deploy validation loop failed after ${PRE_DEPLOY_LOOP_MAX_PASSES} pass(es). Fix errors and rerun preflight before deploy."
}

# ---------------------------------------------------------------------------
# Free blocked AI stack ports — prevents systemd service failures when
# manual processes are left running from previous debugging/testing sessions.
# ---------------------------------------------------------------------------
free_blocked_ai_ports() {
  local ports_to_check=(8080 8081 8085 8092 8002)
  local port pid process_name killed_any
  killed_any=false

  for port in "${ports_to_check[@]}"; do
    local port_info
    port_info="$(ss -H -ltnp "sport = :${port}" 2>/dev/null | head -1 || true)"
    [[ -n "${port_info}" ]] || continue

    pid="$(printf '%s\n' "${port_info}" | sed -n 's/.*pid=\([0-9]*\).*/\1/p' | head -1)"
    process_name="$(printf '%s\n' "${port_info}" | sed -n 's/.*("\([^"]*\)".*/\1/p' | head -1)"
    [[ -n "${pid}" ]] || continue

    # Skip systemd-managed service processes.
    if [[ -r "/proc/${pid}/cgroup" ]] && grep -qE '\.service|\.slice' "/proc/${pid}/cgroup"; then
      continue
    fi

    # Only kill known dev-runtime blockers (python/node/java) to avoid collateral damage.
    if ps -p "${pid}" -o comm= 2>/dev/null | grep -Eq "python|node|java"; then
      log "Port ${port} is blocked by manual process '${process_name}' (PID ${pid}) — killing..."
      kill "${pid}" 2>/dev/null || true
      sleep 1
      if ps -p "${pid}" >/dev/null 2>&1; then
        log "Process ${pid} still running, sending SIGKILL..."
        kill -9 "${pid}" 2>/dev/null || true
      fi
      killed_any=true
    fi
  done

  # Give systemd a moment to reclaim ports only when we actually killed blockers.
  if [[ "${killed_any}" == true ]]; then
    sleep 2
  fi
}

enable_flakes_runtime() {
  local feature_line="experimental-features = nix-command flakes"
  if [[ -n "${NIX_CONFIG:-}" ]]; then
    export NIX_CONFIG="${NIX_CONFIG}"$'\n'"${feature_line}"
  else
    export NIX_CONFIG="${feature_line}"
  fi
}

nix_eval_raw_safe() {
  local expr="$1"
  run_nix_eval_with_timeout nix eval --raw "${expr}"
}

nix_eval_bool_safe() {
  local expr="$1"
  local raw
  raw="$(run_nix_eval_with_timeout nix eval --json "${expr}")" || return 1
  case "$raw" in
    true|false) printf '%s\n' "$raw" ;;
    *) return 1 ;;
  esac
}

run_nix_eval_with_timeout() {
  local timeout_secs="${NIX_EVAL_TIMEOUT_SECONDS:-60}"
  local retry_timeout_secs="${NIX_EVAL_RETRY_TIMEOUT_SECONDS:-$((timeout_secs * 2))}"

  if ! command -v timeout >/dev/null 2>&1; then
    "$@"
    return $?
  fi

  timeout "${timeout_secs}" "$@"
  local rc=$?
  if [[ $rc -ne 124 && $rc -ne 137 ]]; then
    return $rc
  fi

  timeout "${retry_timeout_secs}" "$@"
}

is_interactive_tty() {
  [[ -t 0 && -t 1 ]]
}

bootstrap_ai_stack_secrets_if_needed() {
  [[ "${RUN_AI_SECRETS_BOOTSTRAP}" == true ]] || return 0
  [[ "${SKIP_SYSTEM_SWITCH}" == false ]] || return 0

  local ai_enabled secrets_enabled profile_hint
  if ! ai_enabled="$(nix_eval_raw_safe "${FLAKE_REF}#nixosConfigurations.\"${NIXOS_TARGET}\".config.mySystem.roles.aiStack.enable" 2>/dev/null)"; then
    ai_enabled="unknown"
  fi
  if ! secrets_enabled="$(nix_eval_raw_safe "${FLAKE_REF}#nixosConfigurations.\"${NIXOS_TARGET}\".config.mySystem.secrets.enable" 2>/dev/null)"; then
    secrets_enabled="unknown"
  fi
  if [[ "${ai_enabled}" == "unknown" ]]; then
    profile_hint="$(nix_eval_raw_safe "${FLAKE_REF}#nixosConfigurations.\"${NIXOS_TARGET}\".config.mySystem.profile" 2>/dev/null || true)"
    if [[ "${profile_hint}" == "ai-dev" ]]; then
      ai_enabled="true"
      log "AI secrets bootstrap fallback: profile '${profile_hint}' implies aiStack enabled."
    else
      ai_enabled="false"
      log "AI secrets bootstrap fallback: unable to evaluate aiStack role; defaulting to disabled."
    fi
  fi
  if [[ "${secrets_enabled}" == "unknown" ]]; then
    # Fallback 1: check deploy-options.local.nix for secrets.enable = true
    local _local_opts="${REPO_ROOT}/nix/hosts/${HOST_NAME}/deploy-options.local.nix"
    if grep -qE 'secrets\.enable\s*=.*true' "${_local_opts}" 2>/dev/null; then
      secrets_enabled="true"
      log "AI secrets bootstrap fallback: secrets.enable=true found in deploy-options.local.nix."
    # Fallback 2: sops secrets file already exists → already bootstrapped
    elif [[ -f "/home/${PRIMARY_USER}/.local/share/nixos-quick-deploy/secrets/${HOST_NAME}/secrets.sops.yaml" ]]; then
      secrets_enabled="true"
      log "AI secrets bootstrap fallback: secrets file exists — already bootstrapped."
    else
      secrets_enabled="false"
      log "AI secrets bootstrap fallback: unable to evaluate secrets role; defaulting to disabled."
    fi
  fi
  log "AI secrets bootstrap check: aiStack=${ai_enabled}, secrets=${secrets_enabled}"

  if [[ "${ai_enabled}" != "true" && "${FORCE_AI_SECRETS_BOOTSTRAP}" != "true" ]]; then
    AI_SECRETS_BOOTSTRAP_STATUS="skipped:ai-stack-disabled"
    return 0
  fi
  local manage_secrets_cmd="${REPO_ROOT}/scripts/governance/manage-secrets.sh"

  if [[ "${secrets_enabled}" == "true" && "${FORCE_AI_SECRETS_BOOTSTRAP}" != "true" ]]; then
    if [[ -x "${manage_secrets_cmd}" ]]; then
      "${manage_secrets_cmd}" ensure-local-config --host "${HOST_NAME}" >/dev/null 2>&1 || true
    fi
    log "AI stack secrets already enabled; skipping bootstrap prompt."
    AI_SECRETS_BOOTSTRAP_STATUS="skipped:already-enabled"
    return 0
  fi

  if ! is_interactive_tty; then
    log "WARNING: AI stack API key protection is not configured. All AI stack services (AIDB, hybrid"
    log "coordinator, embeddings, aider-wrapper) are reachable without authentication. To enable"
    log "protection, rerun interactively or set mySystem.secrets in deploy-options.local.nix."
    AI_SECRETS_BOOTSTRAP_STATUS="skipped:no-tty"
    return 0
  fi

  local choice paths_output bundle_path override_path

  printf '\n'
  printf '[clean-deploy] ── AI Stack Security Setup ──────────────────────────────────────────\n'
  printf '  The AI stack services on %s have no API key protection configured.\n' "${NIXOS_TARGET}"
  printf '  Without protection, any local process can call AIDB, the hybrid coordinator,\n'
  printf '  embeddings, aider-wrapper, and other services without a password or API key.\n'
  printf '\n'
  printf '  Enable protection now (recommended):\n'
  printf '    Generates encrypted API keys and passwords for each service.\n'
  printf '    Services will reject requests that do not present the correct key.\n'
  printf '\n'
  printf '  Skip protection (not recommended for shared or networked machines):\n'
  printf '    Services start without authentication. You can enable protection\n'
  printf '    later by rerunning with: --force-ai-secrets-bootstrap\n'
  printf '[clean-deploy] ─────────────────────────────────────────────────────────────────────\n'
  printf '\n'
  read -r -p "Enable AI stack API key protection? [Y/n] (default: Yes — recommended): " choice
  choice="${choice:-Y}"
  if [[ ! "${choice}" =~ ^[Yy]$ && "${FORCE_AI_SECRETS_BOOTSTRAP}" != "true" ]]; then
    printf '\n'
    log "AI stack API key protection was skipped. Services will run WITHOUT authentication."
    log "To enable protection at any time, rerun with: --force-ai-secrets-bootstrap"
    AI_SECRETS_BOOTSTRAP_STATUS="skipped:declined"
    return 0
  fi

  [[ -x "${manage_secrets_cmd}" ]] || die "Missing secrets manager: ${manage_secrets_cmd}"
  log "Bootstrapping AI stack secrets via manage-secrets.sh"
  "${manage_secrets_cmd}" bootstrap --host "${HOST_NAME}" || die "AI stack secrets bootstrap failed."

  paths_output="$("${manage_secrets_cmd}" paths --host "${HOST_NAME}" 2>/dev/null || true)"
  bundle_path="$(printf '%s\n' "${paths_output}" | awk -F= '$1=="bundle"{print $2; exit}')"
  override_path="$(printf '%s\n' "${paths_output}" | awk -F= '$1=="deploy_options_local"{print $2; exit}')"

  printf '\n[clean-deploy] Initial AI stack secrets have been configured.\n'
  if [[ -n "${bundle_path}" ]]; then
    printf '[clean-deploy] Encrypted secrets file: %s\n' "${bundle_path}"
  fi
  if [[ -n "${override_path}" ]]; then
    printf '[clean-deploy] Local override ensured at: %s\n' "${override_path}"
  fi
  printf '[clean-deploy] Manage or rotate secrets later with: ./scripts/governance/manage-secrets.sh\n'
  AI_SECRETS_BOOTSTRAP_STATUS="configured"
}

update_flake_lock() {
  local ref="$1"
  local -a targets=()
  local target=""

  if [[ "$ref" == path:* ]]; then
    targets+=("$ref" "${ref#path:}")
  else
    targets+=("$ref")
  fi

  for target in "${targets[@]}"; do
    [[ -n "$target" ]] || continue

    log "Updating flake lock: ${target}"
    if nix flake update --flake "$target"; then
      return 0
    fi

    log "Flake lock update failed for '${target}', retrying with ephemeral git toolchain"
    if nix shell nixpkgs#git --command nix flake update --flake "$target"; then
      return 0
    fi
  done

  die "Unable to update flake lock for '${ref}'."
}

run_privileged() {
  if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
    "$@"
  else
    require_command sudo
    sudo "$@"
  fi
}

prime_sudo_session() {
  [[ "${EUID:-$(id -u)}" -eq 0 ]] && return 0
  [[ "${PRIME_SUDO_EARLY}" == "true" ]] || return 0

  require_command sudo
  if ! sudo -n true >/dev/null 2>&1; then
    section "Privilege Auth"
    log "Requesting sudo authentication once upfront to avoid mid-run stalls..."
    sudo -v
  fi

  if [[ "${KEEP_SUDO_ALIVE}" == "true" && -z "${SUDO_KEEPALIVE_PID}" ]]; then
    (
      while true; do
        sleep 45
        sudo -n true >/dev/null 2>&1 || exit 0
      done
    ) &
    SUDO_KEEPALIVE_PID="$!"
  fi
}

nix_escape_string() {
  local value="${1:-}"
  value="${value//\\/\\\\}"
  value="${value//\"/\\\"}"
  printf '%s' "$value"
}

nix_eval_expr_raw_safe() {
  local expr="$1"
  run_nix_eval_with_timeout nix eval --impure --raw --expr "$expr"
}

is_locked_password_field() {
  local value="${1:-}"
  [[ "$value" == "!" || "$value" == "*" || "$value" == "!!" || "$value" == \!* || "$value" == \** ]]
}

read_shadow_hash() {
  local account="$1"
  # shellcheck disable=SC2016
  local -a cmd=(awk -F: -v user="$account" '$1 == user { print $2; found = 1; exit } END { if (!found) exit 1 }' /etc/shadow)
  if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
    "${cmd[@]}" 2>/dev/null
    return $?
  fi

  if [[ "${PRECHECK_SHADOW_WITH_SUDO_PROMPT}" == "true" ]]; then
    run_privileged "${cmd[@]}" 2>/dev/null
    return $?
  fi

  if command -v sudo >/dev/null 2>&1; then
    sudo -n "${cmd[@]}" 2>/dev/null
    return $?
  fi
  return 1
}

assert_runtime_account_unlocked() {
  local account="$1"
  local strict="${2:-true}"
  local hash=""

  if ! getent passwd "$account" >/dev/null 2>&1; then
    if [[ "$strict" == "true" ]]; then
      die "Account '${account}' does not exist on this host. Refusing deploy."
    fi
    log "Account '${account}' not present on this host; skipping lock check."
    return 0
  fi

  if ! hash="$(read_shadow_hash "$account" 2>/dev/null || true)"; then
    hash=""
  fi

  if [[ -z "$hash" ]]; then
    log "Could not read password hash state for '${account}' (insufficient privileges or non-shadow auth); skipping lock assertion."
    return 0
  fi

  if is_locked_password_field "$hash"; then
    die "Account '${account}' is locked on the running system. Unlock/reset it before deploy (example: sudo passwd ${account}; sudo usermod -U ${account})."
  fi
}

# snapshot_password_hash: read and store the current shadow hash for an
# account so we can detect if it changed after nixos-rebuild switch.
# Stored in a shell variable named _PWHASH_SNAPSHOT_<sanitised_user>.
# Non-fatal if /etc/shadow is unreadable (non-root context).
snapshot_password_hash() {
  local account="$1"
  local hash=""
  if hash="$(read_shadow_hash "$account" 2>/dev/null || true)" && [[ -n "$hash" ]]; then
    # Sanitise: replace non-alphanumeric chars with underscore for var name.
    local var_name="_PWHASH_SNAPSHOT_${account//[^a-zA-Z0-9]/_}"
    printf -v "$var_name" '%s' "$hash"
  fi
}

# assert_password_unchanged: compare current shadow hash to the snapshot.
# Emits a hard warning (not a fatal error) if the hash changed, so the
# operator knows the deploy unexpectedly modified the login password.
# With users.mutableUsers = true (our default) this should NEVER fire.
assert_password_unchanged() {
  local account="$1"
  local var_name="_PWHASH_SNAPSHOT_${account//[^a-zA-Z0-9]/_}"
  local before="${!var_name:-}"
  [[ -z "$before" ]] && return 0  # no snapshot — skip

  local after=""
  after="$(read_shadow_hash "$account" 2>/dev/null || true)"
  [[ -z "$after" ]] && return 0  # cannot read — skip

  if [[ "$before" != "$after" ]]; then
    log "WARNING: password hash for '${account}' changed during nixos-rebuild switch."
    log "  This should not happen with users.mutableUsers = true."
    log "  If your password stopped working, run: passwd ${account}"
    log "  Check that no NixOS module sets hashedPassword/initialPassword for this user."
  fi
}

ensure_host_facts_access() {
  local facts_file="${REPO_ROOT}/nix/hosts/${HOST_NAME}/facts.nix"
  [[ -e "$facts_file" ]] || return 0

  if [[ -r "$facts_file" && -w "$facts_file" ]]; then
    return 0
  fi

  local target_user target_group
  target_user="${SUDO_USER:-${USER:-$(id -un)}}"
  target_group="$(id -gn "$target_user" 2>/dev/null || id -gn 2>/dev/null || echo users)"

  log "Repairing permissions for '${facts_file}' so flake evaluation can read host facts"
  run_privileged chown "${target_user}:${target_group}" "$facts_file" || true
  run_privileged chmod 0644 "$facts_file" || true

  [[ -r "$facts_file" ]] || die "facts file is not readable after permission repair: ${facts_file}"
}

assert_target_account_guardrails() {
  local escaped_flake escaped_target escaped_user expr result
  escaped_flake="$(nix_escape_string "$FLAKE_REF")"
  escaped_target="$(nix_escape_string "$NIXOS_TARGET")"
  escaped_user="$(nix_escape_string "$PRIMARY_USER")"

  read -r -d '' expr <<EOF || true
let
  flake = builtins.getFlake "${escaped_flake}";
  cfg = flake.nixosConfigurations."${escaped_target}".config;
  users = cfg.users.users or {};
  primaryName = "${escaped_user}";
  hasPrimary = builtins.hasAttr primaryName users;
  primary = if hasPrimary then builtins.getAttr primaryName users else {};
  hasRoot = builtins.hasAttr "root" users;
  rootUser = if hasRoot then users.root else {};
  hasPassword = u:
    (u ? hashedPassword)
    || (u ? hashedPasswordFile)
    || (u ? initialPassword)
    || (u ? initialHashedPassword)
    || (u ? passwordFile);
  isLocked = u:
    (u ? hashedPassword)
    && (u.hashedPassword != null)
    && (builtins.isString u.hashedPassword)
    && ((builtins.match "^[!*].*" u.hashedPassword) != null);
  mutableUsers = cfg.users.mutableUsers or true;
  initrdEmergencyAccess =
    if cfg ? mySystem && cfg.mySystem ? deployment && cfg.mySystem.deployment ? initrdEmergencyAccess then
      cfg.mySystem.deployment.initrdEmergencyAccess
    else
      false;
in
  if isLocked primary then "primary-hash-locked"
  else if (!mutableUsers && !hasPrimary) then "missing-primary-user"
  else if (!mutableUsers && hasPrimary && !hasPassword primary) then "missing-primary-password"
  else if (initrdEmergencyAccess && hasRoot && isLocked rootUser) then "root-hash-locked"
  else if (initrdEmergencyAccess && hasRoot && !hasPassword rootUser) then "root-missing-password"
  else "ok"
EOF

  local eval_err
  eval_err="$(mktemp)"
  if ! result="$(nix_eval_expr_raw_safe "$expr" 2>"${eval_err}")"; then
    result=""
  fi

  case "$result" in
    ok)
      ;;
    primary-hash-locked)
      rm -f "${eval_err}" >/dev/null 2>&1 || true
      die "Target config declares locked hashedPassword for primary user '${PRIMARY_USER}'. Refusing deploy."
      ;;
    missing-primary-user)
      rm -f "${eval_err}" >/dev/null 2>&1 || true
      die "Target config sets users.mutableUsers=false but does not declare primary user '${PRIMARY_USER}'. Refusing deploy."
      ;;
    missing-primary-password)
      rm -f "${eval_err}" >/dev/null 2>&1 || true
      die "Target config declares primary user '${PRIMARY_USER}' without a password while users.mutableUsers=false. Refusing deploy."
      ;;
    root-hash-locked)
      rm -f "${eval_err}" >/dev/null 2>&1 || true
      die "Target config declares a locked root hashedPassword while initrd emergency access is enabled. Refusing deploy."
      ;;
    root-missing-password)
      rm -f "${eval_err}" >/dev/null 2>&1 || true
      die "Target config enables initrd emergency access but root user is declared without a password directive. Refusing deploy."
      ;;
    *)
      local reason=""
      reason="$(tr '\n' ' ' < "${eval_err}" 2>/dev/null | sed -E 's/[[:space:]]+/ /g; s/^ //; s/ $//')"
      if [[ -n "${reason}" ]]; then
        log "Account guardrail preflight could not fully evaluate target config; continuing with runtime checks (${reason})."
      else
        log "Account guardrail preflight could not fully evaluate target config; continuing with runtime checks."
      fi
      ;;
  esac

  rm -f "${eval_err}" >/dev/null 2>&1 || true
}

extract_host_fs_field() {
  local host_hw_file="$1"
  local field="$2"
  sed -n '/fileSystems\."\/"[[:space:]]*=/,/};/ s/.*'"${field}"'[[:space:]]*=[[:space:]]*"\([^"]*\)".*/\1/p' "${host_hw_file}" | head -n1
}

assert_previous_boot_fsck_clean() {
  [[ "${ALLOW_PREVIOUS_BOOT_FSCK_FAILURE}" == true ]] && return 0
  command -v journalctl >/dev/null 2>&1 || return 0

  local previous_log fsck_unit_log
  previous_log="$(journalctl -b -1 --no-pager 2>/dev/null || true)"
  fsck_unit_log="$(journalctl -b -1 -u systemd-fsck-root.service --no-pager 2>/dev/null || true)"

  if [[ -z "${previous_log}" && "${EUID:-$(id -u)}" -ne 0 ]] && command -v sudo >/dev/null 2>&1; then
    previous_log="$(sudo -n journalctl -b -1 --no-pager 2>/dev/null || true)"
    fsck_unit_log="$(sudo -n journalctl -b -1 -u systemd-fsck-root.service --no-pager 2>/dev/null || true)"
  fi

  [[ -n "${previous_log}${fsck_unit_log}" ]] || return 0

  if echo "${previous_log}${fsck_unit_log}" | grep -Eiq \
    "Failed to start File System Check on|Dependency failed for /sysroot|You are in emergency mode|systemd-fsck.*failed|systemd-fsck.*status=[14]|status=1/FAILURE|status=4|has unrepaired errors, please fix them manually|mounting fs with errors, running e2fsck is recommended|error count since last fsck"; then
    if [[ "${MODE}" == "switch" ]]; then
      die "Previous boot shows root filesystem integrity warnings/failures. Refusing live switch. Run offline fsck first (e2fsck -f /dev/disk/by-uuid/<root-uuid>). Use '--recovery-mode --boot' only as temporary fallback."
    fi
    die "Previous boot recorded root filesystem integrity warnings/failures. Run offline fsck first (for ext4: e2fsck -f /dev/disk/by-uuid/<root-uuid>) or rerun with --allow-prev-fsck-fail to bypass."
  fi
}

assert_host_storage_config() {
  local host_dir="${REPO_ROOT}/nix/hosts/${HOST_NAME}"
  local facts_file="${host_dir}/facts.nix"
  local host_hw_file="${host_dir}/hardware-configuration.nix"
  local disk_layout="none"

  if [[ -f "${facts_file}" ]]; then
    disk_layout="$(sed -n 's/^[[:space:]]*layout[[:space:]]*=[[:space:]]*"\([^"]*\)".*/\1/p' "${facts_file}" | head -n1)"
    [[ -n "${disk_layout}" ]] || disk_layout="none"
  fi

  if [[ "${disk_layout}" == "none" && ! -f "${host_hw_file}" ]]; then
    die "Host '${HOST_NAME}' uses disk layout 'none' but '${host_hw_file}' is missing. Re-run discovery with HOST_HARDWARE_CONFIG_SOURCE=<path> if your hardware config lives outside /etc/nixos, or set --phase0-disko with a disko layout."
  fi

  if [[ "${disk_layout}" == "none" ]]; then
    local host_root_device host_root_fstype
    host_root_device="$(extract_host_fs_field "${host_hw_file}" "device")"
    host_root_fstype="$(extract_host_fs_field "${host_hw_file}" "fsType")"
    [[ -n "${host_root_device}" ]] || die "Host hardware config is missing fileSystems.\"/\".device in '${host_hw_file}'."

    if [[ "${host_root_device}" == /dev/disk/by-uuid/* && ! -e "${host_root_device}" ]]; then
      die "Host root device '${host_root_device}' from '${host_hw_file}' does not exist on this machine. Regenerate/copy hardware-configuration.nix from the running system."
    fi

    local runtime_root_source runtime_root_uuid runtime_root_uuid_path runtime_root_fstype
    runtime_root_source="$(findmnt -no SOURCE / 2>/dev/null || true)"
    runtime_root_uuid=""
    runtime_root_uuid_path=""
    if [[ -n "${runtime_root_source}" ]] && command -v blkid >/dev/null 2>&1; then
      local runtime_root_real
      runtime_root_real="$(readlink -f "${runtime_root_source}" 2>/dev/null || echo "${runtime_root_source}")"
      if [[ -b "${runtime_root_real}" ]]; then
        # Try blkid without sudo first; fall back to sudo -n for non-root callers.
        runtime_root_uuid="$(blkid -s UUID -o value "${runtime_root_real}" 2>/dev/null \
          || sudo -n blkid -s UUID -o value "${runtime_root_real}" 2>/dev/null \
          || true)"
        [[ -n "${runtime_root_uuid}" ]] && runtime_root_uuid_path="/dev/disk/by-uuid/${runtime_root_uuid}"
      fi
    fi
    runtime_root_fstype="$(findmnt -no FSTYPE / 2>/dev/null || true)"

    # Resolve the host's by-uuid symlink to a canonical device path.
    # This covers the case where blkid is unavailable or requires root:
    # if /dev/disk/by-uuid/<uuid> → /dev/nvme0n1p2 and findmnt reports
    # /dev/nvme0n1p2 as the running root, the deploy is safe even if blkid
    # could not derive runtime_root_uuid_path (NIX-ISSUE: fix-duplicate-flatpaks).
    local host_root_via_symlink=""
    if [[ "${host_root_device}" == /dev/disk/by-uuid/* && -L "${host_root_device}" ]]; then
      host_root_via_symlink="$(readlink -f "${host_root_device}" 2>/dev/null || true)"
    fi

    if [[ -n "${runtime_root_source}" \
        && "${host_root_device}" != "${runtime_root_source}" \
        && "${host_root_device}" != "${runtime_root_uuid_path}" \
        && ( -z "${host_root_via_symlink}" || "${host_root_via_symlink}" != "${runtime_root_source}" ) ]]; then
      die "Host hardware root device '${host_root_device}' does not match running root '${runtime_root_source}'. Refusing deploy to avoid unbootable generation."
    fi

    if [[ -n "${host_root_fstype}" && -n "${runtime_root_fstype}" && "${host_root_fstype}" != "${runtime_root_fstype}" ]]; then
      die "Host hardware root fsType '${host_root_fstype}' does not match running root fsType '${runtime_root_fstype}'. Refusing deploy."
    fi
  fi
}

assert_bootloader_preflight() {
  [[ "${RUN_PHASE0_DISKO}" == true ]] && return 0

  local systemd_boot_enabled grub_enabled
  if ! systemd_boot_enabled="$(nix_eval_bool_safe "${FLAKE_REF}#nixosConfigurations.\"${NIXOS_TARGET}\".config.boot.loader.systemd-boot.enable" 2>/dev/null)"; then
    log "Bootloader preflight: unable to evaluate systemd-boot enable flag; skipping strict bootloader assertion."
    return 0
  fi

  if ! grub_enabled="$(nix_eval_bool_safe "${FLAKE_REF}#nixosConfigurations.\"${NIXOS_TARGET}\".config.boot.loader.grub.enable" 2>/dev/null)"; then
    log "Bootloader preflight: unable to evaluate grub enable flag; skipping strict bootloader assertion."
    return 0
  fi

  if [[ "${systemd_boot_enabled}" != "true" && "${grub_enabled}" != "true" ]]; then
    die "Target '${NIXOS_TARGET}' does not enable a supported bootloader (systemd-boot/grub). Refusing deploy."
  fi

  [[ "${systemd_boot_enabled}" == "true" ]] || return 0

  local bootctl_cmd=""
  if command -v bootctl >/dev/null 2>&1; then
    bootctl_cmd="$(command -v bootctl)"
  elif [[ -x /run/current-system/sw/bin/bootctl ]]; then
    bootctl_cmd="/run/current-system/sw/bin/bootctl"
  fi

  local strict_bootloader_checks=true
  if [[ -z "${bootctl_cmd}" ]]; then
    log "Bootloader preflight: systemd-boot target detected but 'bootctl' is unavailable in this runtime; skipping strict bootloader checks."
    strict_bootloader_checks=false
  elif [[ ! -d /sys/firmware/efi ]]; then
    log "Bootloader preflight: host runtime does not expose EFI firmware; skipping strict bootloader checks."
    strict_bootloader_checks=false
  else
    local bootctl_status_ok=false
    if "${bootctl_cmd}" status >/dev/null 2>&1; then
      bootctl_status_ok=true
    elif command -v sudo >/dev/null 2>&1 && sudo -n "${bootctl_cmd}" status >/dev/null 2>&1; then
      bootctl_status_ok=true
    fi

    if [[ "${bootctl_status_ok}" != "true" ]]; then
      log "Bootloader preflight: bootctl status failed in current runtime (including sudo -n fallback); skipping strict bootloader checks."
      strict_bootloader_checks=false
    fi
  fi

  [[ "${strict_bootloader_checks}" == "true" ]] || return 0

  local esp_mount esp_min_free_mb esp_free_mb
  esp_mount="$(nix_eval_raw_safe "${FLAKE_REF}#nixosConfigurations.\"${NIXOS_TARGET}\".config.boot.loader.efi.efiSysMountPoint" 2>/dev/null || echo /boot)"
  [[ -n "${esp_mount}" ]] || esp_mount="/boot"
  esp_min_free_mb="${BOOT_ESP_MIN_FREE_MB:-$(nix_eval_raw_safe "${FLAKE_REF}#nixosConfigurations.\"${NIXOS_TARGET}\".config.mySystem.deployment.bootloaderEspMinFreeMb" 2>/dev/null || echo 128)}"
  [[ "${esp_min_free_mb}" =~ ^[0-9]+$ ]] || esp_min_free_mb=128

  if ! findmnt "${esp_mount}" >/dev/null 2>&1; then
    die "Configured EFI mount '${esp_mount}' is not mounted on this host."
  fi

  esp_free_mb="$(df -Pm "${esp_mount}" 2>/dev/null | awk 'NR==2 {print $4}')"
  [[ "${esp_free_mb}" =~ ^[0-9]+$ ]] || die "Unable to determine free space for EFI mount '${esp_mount}'."

  if (( esp_free_mb < esp_min_free_mb )); then
    die "EFI partition low on space: ${esp_free_mb}MB free on '${esp_mount}' (minimum ${esp_min_free_mb}MB required)."
  fi
}

assert_target_boot_mode() {
  [[ "${MODE}" == "build" ]] && return 0
  [[ "${ALLOW_HEADLESS_TARGET:-false}" == "true" ]] && return 0
  command -v systemctl >/dev/null 2>&1 || return 0

  if ! systemctl is-active --quiet display-manager 2>/dev/null; then
    return 0
  fi

  local target_default_unit
  if ! target_default_unit="$(nix_eval_raw_safe "${FLAKE_REF}#nixosConfigurations.\"${NIXOS_TARGET}\".config.systemd.defaultUnit" 2>/dev/null)"; then
    if [[ "${MODE}" == "switch" && "${AUTO_GUI_SWITCH_FALLBACK}" == true ]]; then
      MODE="boot"
      log "Unable to evaluate target default unit for '${NIXOS_TARGET}' in graphical context. Auto-fallback: mode set to 'boot'."
      return 0
    fi
    die "Unable to evaluate target default unit for '${NIXOS_TARGET}'. Refusing deploy on a graphical host."
  fi

  if [[ -z "${target_default_unit}" ]]; then
    if [[ "${MODE}" == "switch" && "${AUTO_GUI_SWITCH_FALLBACK}" == true ]]; then
      MODE="boot"
      log "Target '${NIXOS_TARGET}' default unit resolved empty in graphical context. Auto-fallback: mode set to 'boot'."
      return 0
    fi
    die "Target '${NIXOS_TARGET}' default unit resolved empty. Refusing deploy on a graphical host."
  fi

  if [[ "${target_default_unit}" != "graphical.target" ]]; then
    die "Target '${NIXOS_TARGET}' default unit is '${target_default_unit}' while this host is currently graphical. Refusing deploy to avoid headless login regression. Set ALLOW_HEADLESS_TARGET=true to override."
  fi
}

assert_targets_exist() {
  local nixos_target="${1:?missing nixos target}"
  local hm_target="${2:?missing home target}"
  local available_nixos available_home
  local eval_err reason

  available_nixos="$(list_configuration_names "nixosConfigurations" || true)"
  if ! has_configuration_name "nixosConfigurations" "${nixos_target}"; then
    die "NixOS target '${nixos_target}' not found in flake. Available nixosConfigurations: ${available_nixos:-<unavailable>}."
  fi

  eval_err="$(mktemp)"
  if ! nix_eval_raw_safe "${FLAKE_REF}#nixosConfigurations.\"${nixos_target}\".config.system.stateVersion" >/dev/null 2>"${eval_err}"; then
    reason="$(tr '\n' ' ' < "${eval_err}" 2>/dev/null | sed -E 's/[[:space:]]+/ /g; s/^ //; s/ $//')"
    rm -f "${eval_err}" >/dev/null 2>&1 || true
    die "NixOS target '${nixos_target}' exists but failed to evaluate. ${reason:-Check target module syntax/import errors.}"
  fi
  rm -f "${eval_err}" >/dev/null 2>&1 || true

  [[ "${SKIP_HOME_SWITCH}" == false ]] || return 0

  available_home="$(list_configuration_names "homeConfigurations" || true)"
  if ! has_configuration_name "homeConfigurations" "${hm_target}"; then
    die "Home target '${hm_target}' not found in flake. Available homeConfigurations: ${available_home:-<unavailable>}."
  fi

  eval_err="$(mktemp)"
  if ! nix_eval_raw_safe "${FLAKE_REF}#homeConfigurations.\"${hm_target}\".activationPackage.drvPath" >/dev/null 2>"${eval_err}"; then
    reason="$(tr '\n' ' ' < "${eval_err}" 2>/dev/null | sed -E 's/[[:space:]]+/ /g; s/^ //; s/ $//')"
    rm -f "${eval_err}" >/dev/null 2>&1 || true
    die "Home target '${hm_target}' exists but failed to evaluate. ${reason:-Check Home Manager module syntax/import errors.}"
  fi
  rm -f "${eval_err}" >/dev/null 2>&1 || true
}

assert_safe_switch_context() {
  [[ "${MODE}" == "switch" ]] || return 0
  [[ "${ALLOW_GUI_SWITCH}" == "true" ]] && return 0

  if [[ -n "${DISPLAY:-}" || -n "${WAYLAND_DISPLAY:-}" ]]; then
    if [[ "${AUTO_GUI_SWITCH_FALLBACK}" == true ]]; then
      MODE="boot"
      log "Graphical session detected. Auto-fallback: switching deploy mode to 'boot' to avoid live-switch black screen. Reboot required to apply."
      return 0
    fi
    die "Refusing live switch from a graphical session. Re-run from a TTY (Ctrl+Alt+F3) or use --boot. Set ALLOW_GUI_SWITCH=true to override."
  fi
}

home_build() {
  local hm_target="$1"
  if command -v home-manager >/dev/null 2>&1; then
    home-manager build --flake "${FLAKE_REF}#${hm_target}"
    return
  fi

  if [[ "${REQUIRE_HOME_MANAGER_CLI}" == "true" ]]; then
    die "home-manager CLI is required but not found in PATH. Install it or re-run without --require-home-manager-cli."
  fi

  if [[ "${PREFER_NIX_RUN_HOME_MANAGER}" == "true" ]] && command -v nix >/dev/null 2>&1; then
    if nix run --accept-flake-config "${HOME_MANAGER_NIX_RUN_REF}" -- build --flake "${FLAKE_REF}#${hm_target}"; then
      return
    fi
    log "nix run Home Manager build fallback failed (${HOME_MANAGER_NIX_RUN_REF}); using activationPackage build path."
  fi

  nix build "${FLAKE_REF}#homeConfigurations.\"${hm_target}\".activationPackage"
}

verify_home_manager_cli_post_switch() {
  # Surface actionable guidance after activation so operators understand whether
  # the CLI is now available or still only accessible via nix run.
  if command -v home-manager >/dev/null 2>&1; then
    log "home-manager CLI available in PATH: $(command -v home-manager)"
    return 0
  fi

  if [[ "${PREFER_NIX_RUN_HOME_MANAGER}" == "true" ]] && command -v nix >/dev/null 2>&1; then
    if nix run --accept-flake-config "${HOME_MANAGER_NIX_RUN_REF}" -- --version >/dev/null 2>&1; then
      log "home-manager CLI is not in PATH yet. You can run it via: nix run --accept-flake-config ${HOME_MANAGER_NIX_RUN_REF} -- <args>"
      return 0
    fi
  fi

  log "home-manager CLI remains unavailable after activation. Ensure programs.home-manager.enable is set or install home-manager into your user profile."
  return 0
}

home_switch() {
  local hm_target="$1"
  if command -v home-manager >/dev/null 2>&1; then
    home-manager switch -b "${HOME_MANAGER_BACKUP_EXTENSION}" --flake "${FLAKE_REF}#${hm_target}"
    verify_home_manager_cli_post_switch
    return
  fi

  if [[ "${REQUIRE_HOME_MANAGER_CLI}" == "true" ]]; then
    die "home-manager CLI is required but not found in PATH. Install it or re-run without --require-home-manager-cli."
  fi

  if [[ "${PREFER_NIX_RUN_HOME_MANAGER}" == "true" ]] && command -v nix >/dev/null 2>&1; then
    if nix run --accept-flake-config "${HOME_MANAGER_NIX_RUN_REF}" -- switch -b "${HOME_MANAGER_BACKUP_EXTENSION}" --flake "${FLAKE_REF}#${hm_target}"; then
      verify_home_manager_cli_post_switch
      return
    fi
    log "nix run Home Manager switch fallback failed (${HOME_MANAGER_NIX_RUN_REF}); using activationPackage fallback."
  fi

  local out_link
  out_link="/tmp/home-activation-${hm_target//[^a-zA-Z0-9_.-]/_}-$$"
  nix build --out-link "$out_link" "${FLAKE_REF}#homeConfigurations.\"${hm_target}\".activationPackage"
  # home-manager CLI may be unavailable on fresh systems; mirror `-b <ext>` by
  # exporting HOME_MANAGER_BACKUP_EXT for direct activationPackage execution.
  HOME_MANAGER_BACKUP_EXT="${HOME_MANAGER_BACKUP_EXTENSION}" "${out_link}/activate"
  verify_home_manager_cli_post_switch
}

# persist_home_git_credentials_declarative: project git identity into
# host-scoped Home Manager options so git credentials remain declarative.
persist_home_git_credentials_declarative() {
  local host_dir="${REPO_ROOT}/nix/hosts/${HOST_NAME}"
  [[ -d "$host_dir" ]] || return 0

  local git_name="${GIT_USER_NAME:-${GIT_AUTHOR_NAME:-}}"
  local git_email="${GIT_USER_EMAIL:-${GIT_AUTHOR_EMAIL:-}}"
  local git_helper="${GIT_CREDENTIAL_HELPER:-}"

  if command -v git >/dev/null 2>&1; then
    if [[ "${EUID:-$(id -u)}" -eq 0 && -n "${PRIMARY_USER:-}" ]]; then
      git_name="${git_name:-$(sudo -u "$PRIMARY_USER" git config --global user.name 2>/dev/null || true)}"
      git_email="${git_email:-$(sudo -u "$PRIMARY_USER" git config --global user.email 2>/dev/null || true)}"
      git_helper="${git_helper:-$(sudo -u "$PRIMARY_USER" git config --global credential.helper 2>/dev/null || true)}"
    else
      git_name="${git_name:-$(git config --global user.name 2>/dev/null || true)}"
      git_email="${git_email:-$(git config --global user.email 2>/dev/null || true)}"
      git_helper="${git_helper:-$(git config --global credential.helper 2>/dev/null || true)}"
    fi

    if [[ -n "${REPO_ROOT:-}" && -d "${REPO_ROOT}/.git" ]]; then
      if [[ "${EUID:-$(id -u)}" -eq 0 && -n "${PRIMARY_USER:-}" ]]; then
        git_name="${git_name:-$(sudo -u "$PRIMARY_USER" git -C "$REPO_ROOT" config --get user.name 2>/dev/null || true)}"
        git_email="${git_email:-$(sudo -u "$PRIMARY_USER" git -C "$REPO_ROOT" config --get user.email 2>/dev/null || true)}"
        git_helper="${git_helper:-$(sudo -u "$PRIMARY_USER" git -C "$REPO_ROOT" config --get credential.helper 2>/dev/null || true)}"
      else
        git_name="${git_name:-$(git -C "$REPO_ROOT" config --get user.name 2>/dev/null || true)}"
        git_email="${git_email:-$(git -C "$REPO_ROOT" config --get user.email 2>/dev/null || true)}"
        git_helper="${git_helper:-$(git -C "$REPO_ROOT" config --get credential.helper 2>/dev/null || true)}"
      fi
    fi
  fi

  # Guard against projecting unavailable credential helpers (for example
  # manager-core on Linux without Git Credential Manager installed).
  if [[ -n "$git_helper" ]]; then
    local helper_cmd helper_name helper_is_available=1
    helper_cmd="${git_helper%% *}"
    helper_name="${helper_cmd#git-credential-}"
    if [[ "$helper_cmd" == "manager-core" || "$helper_cmd" == "manager" ]]; then
      if ! command -v "git-credential-${helper_cmd}" >/dev/null 2>&1; then
        helper_is_available=0
      fi
    elif [[ "$helper_cmd" != "!"* && "$helper_cmd" != /* ]]; then
      if ! git "credential-${helper_name}" -h >/dev/null 2>&1; then
        helper_is_available=0
      fi
    fi

    if [[ "$helper_is_available" -ne 1 ]]; then
      git_helper="cache --timeout=28800"
      log "Git credential helper unavailable; using declarative fallback: ${git_helper}"
    fi
  fi

  if [[ -z "$git_name" || -z "$git_email" ]]; then
    # Non-critical: git identity is optional for the deploy to succeed.
    # Only surface the hint in verbose mode to avoid noisy output.
    [[ "${VERBOSE_MODE:-false}" == "true" ]] && \
      log "Declarative git identity not updated (set GIT_USER_NAME/GIT_USER_EMAIL or git config --global user.name/user.email)."
    return 0
  fi

  local escaped_helper target helper_block=""
  escaped_helper="$(nix_escape_string "$git_helper")"

  # Write user.name/email directly to ~/.gitconfig (mutable — survives switches)
  # rather than via home-manager's programs.git.settings which overwrites the
  # git config on every switch and prevents post-switch `git config` changes.
  # Use --file ~/.gitconfig (not --global) to bypass XDG ~/.config/git/config
  # which is home-manager-managed and read-only after a switch.
  local user_home="${HOME:-/home/${PRIMARY_USER:-}}"
  if [[ "${EUID:-$(id -u)}" -eq 0 && -n "${PRIMARY_USER:-}" ]]; then
    user_home="$(getent passwd "$PRIMARY_USER" | cut -d: -f6)"
  fi
  local gitconfig_path="${user_home}/.gitconfig"
  local git_file_cmd="git --git-dir=/dev/null config --file ${gitconfig_path}"
  if [[ "${EUID:-$(id -u)}" -eq 0 && -n "${PRIMARY_USER:-}" ]]; then
    git_file_cmd="sudo -u ${PRIMARY_USER} git --git-dir=/dev/null config --file ${gitconfig_path}"
  fi
  if [[ -n "$git_name" ]]; then
    $git_file_cmd user.name "$git_name" || true
  fi
  if [[ -n "$git_email" ]]; then
    $git_file_cmd user.email "$git_email" || true
  fi

  if [[ -n "$git_helper" ]]; then
    helper_block=$'    settings = {
      credential.helper = lib.mkDefault "'"${escaped_helper}"'";
    };
'
  fi

  target="${host_dir}/home-deploy-options.nix"

  cat > "$target" <<EOF
{ lib, ... }:
{
  # Git identity (user.name, user.email) is written directly to ~/.gitconfig
  # by nixos-quick-deploy.sh so it remains mutable after every switch.
  # Only enable git and optionally set the credential helper here.
  programs.git = {
    enable = lib.mkDefault true;
${helper_block}  };
}
EOF

  if [[ "${RESTORE_GENERATED_REPO_FILES}" == "true" ]]; then
    log "Projected declarative git identity for this run: ${target} (will be restored on exit)"
  else
    log "Updated declarative git identity: ${target}"
    [[ -n "$git_name" ]] && log "Git identity written to ~/.gitconfig: ${git_name} <${git_email}>"
  fi
}

run_discovery_step() {
  if should_skip_discovery_by_cache; then
    log "Skipping hardware discovery (cache hit, TTL ${DISCOVERY_CACHE_TTL_SECONDS}s)"
    return 0
  fi

  log "Discovering hardware facts for host '${HOST_NAME}' profile '${PROFILE}'"

  # AI stack discovery env — honour caller-supplied overrides or fall through
  # to the defaults in discover-system-facts.sh (auto from profile + RAM).
  local_ai_env=(
    ${AI_STACK_ENABLED_OVERRIDE:+AI_STACK_ENABLED_OVERRIDE="${AI_STACK_ENABLED_OVERRIDE}"}
    ${AI_BACKEND_OVERRIDE:+AI_BACKEND_OVERRIDE="${AI_BACKEND_OVERRIDE}"}
    ${AI_MODELS_OVERRIDE:+AI_MODELS_OVERRIDE="${AI_MODELS_OVERRIDE}"}
    ${AI_UI_ENABLED_OVERRIDE:+AI_UI_ENABLED_OVERRIDE="${AI_UI_ENABLED_OVERRIDE}"}
    ${AI_VECTOR_DB_ENABLED_OVERRIDE:+AI_VECTOR_DB_ENABLED_OVERRIDE="${AI_VECTOR_DB_ENABLED_OVERRIDE}"}
  )

  if [[ "${RECOVERY_MODE}" == true ]]; then
    log "Recovery mode enabled: forcing rootFsckMode=skip, initrdEmergencyAccess=true, earlyKmsPolicy=off"
    HOSTNAME_OVERRIDE="${HOST_NAME}" \
    PRIMARY_USER_OVERRIDE="${PRIMARY_USER}" \
    PROFILE_OVERRIDE="${PROFILE}" \
    ROOT_FSCK_MODE_OVERRIDE="skip" \
    INITRD_EMERGENCY_ACCESS_OVERRIDE="true" \
    EARLY_KMS_POLICY_OVERRIDE="off" \
    "${local_ai_env[@]}" \
    "${REPO_ROOT}/scripts/governance/discover-system-facts.sh"
  else
    HOSTNAME_OVERRIDE="${HOST_NAME}" \
    PRIMARY_USER_OVERRIDE="${PRIMARY_USER}" \
    PROFILE_OVERRIDE="${PROFILE}" \
    "${local_ai_env[@]}" \
    "${REPO_ROOT}/scripts/governance/discover-system-facts.sh"
  fi

  mark_discovery_cache
}

setup_ui

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host)
      HOST_NAME="${2:?missing value for --host}"
      HOST_EXPLICIT=true
      shift 2
      ;;
    --user)
      PRIMARY_USER="${2:?missing value for --user}"
      shift 2
      ;;
    --profile)
      PROFILE="${2:?missing value for --profile}"
      shift 2
      ;;
    --nixos-target)
      NIXOS_TARGET_OVERRIDE="${2:?missing value for --nixos-target}"
      shift 2
      ;;
    --home-target)
      HM_TARGET_OVERRIDE="${2:?missing value for --home-target}"
      shift 2
      ;;
    --flake-ref)
      FLAKE_REF="${2:?missing value for --flake-ref}"
      shift 2
      ;;
    --update-lock)
      UPDATE_FLAKE_LOCK=true
      shift
      ;;
    --boot)
      MODE="boot"
      shift
      ;;
    --recovery-mode)
      RECOVERY_MODE=true
      shift
      ;;
    --allow-prev-fsck-fail)
      ALLOW_PREVIOUS_BOOT_FSCK_FAILURE=true
      shift
      ;;
    --phase0-disko)
      RUN_PHASE0_DISKO=true
      shift
      ;;
    --enroll-secureboot-keys)
      RUN_SECUREBOOT_ENROLL=true
      shift
      ;;
    --build-only)
      MODE="build"
      shift
      ;;
    --allow-gui-switch)
      ALLOW_GUI_SWITCH=true
      shift
      ;;
    --no-gui-fallback)
      AUTO_GUI_SWITCH_FALLBACK=false
      shift
      ;;
    --skip-system-switch)
      SKIP_SYSTEM_SWITCH=true
      shift
      ;;
    --skip-home-switch)
      SKIP_HOME_SWITCH=true
      shift
      ;;
    --skip-health-check)
      RUN_HEALTH_CHECK=false
      shift
      ;;
    --require-home-manager-cli)
      REQUIRE_HOME_MANAGER_CLI=true
      shift
      ;;
    --skip-discovery)
      RUN_DISCOVERY=false
      shift
      ;;
    --skip-flatpak-sync)
      RUN_FLATPAK_SYNC=false
      shift
      ;;
    --skip-readiness-check)
      RUN_READINESS_ANALYSIS=false
      shift
      ;;
    --skip-ai-secrets-bootstrap)
      RUN_AI_SECRETS_BOOTSTRAP=false
      shift
      ;;
    --ai-secrets-bootstrap)
      RUN_AI_SECRETS_BOOTSTRAP=true
      shift
      ;;
    --force-ai-secrets-bootstrap)
      FORCE_AI_SECRETS_BOOTSTRAP=true
      shift
      ;;
    --analyze-only)
      ANALYZE_ONLY=true
      shift
      ;;
    --skip-pre-deploy-dry-run)
      ENFORCE_PRE_DEPLOY_DRY_RUN=false
      shift
      ;;
    --skip-pre-deploy-home-dry-run)
      ENFORCE_PRE_DEPLOY_HOME_DRY_RUN=false
      shift
      ;;
    --preflight-only)
      PRE_DEPLOY_PREFLIGHT_ONLY=true
      shift
      ;;
    --self-check)
      SELF_CHECK_ONLY=true
      shift
      ;;
    --enable-preflight-auto-remediation)
      ENABLE_PREFLIGHT_AUTO_REMEDIATION=true
      shift
      ;;
    --preflight-loop-max-passes)
      PRE_DEPLOY_LOOP_MAX_PASSES="${2:?missing value for --preflight-loop-max-passes}"
      shift 2
      ;;
    --preflight-loop-retry-seconds)
      PRE_DEPLOY_LOOP_RETRY_SECONDS="${2:?missing value for --preflight-loop-retry-seconds}"
      shift 2
      ;;
    --skip-roadmap-verification)
      SKIP_ROADMAP_VERIFICATION=true
      shift
      ;;
    --restore-generated-files)
      RESTORE_GENERATED_REPO_FILES=true
      shift
      ;;
    --persist-generated-files)
      RESTORE_GENERATED_REPO_FILES=false
      shift
      ;;
    --post-flight-mode)
      POST_FLIGHT_MODE="${2:?missing value for --post-flight-mode}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "Unknown argument: $1"
      ;;
  esac
done

case "$PROFILE" in
  ai-dev|gaming|minimal) ;;
  *) die "Unsupported profile '${PROFILE}'. Expected ai-dev|gaming|minimal." ;;
esac

case "${RESTORE_GENERATED_REPO_FILES}" in
  auto)
    if [[ "${ANALYZE_ONLY}" == true ]]; then
      RESTORE_GENERATED_REPO_FILES=true
    else
      RESTORE_GENERATED_REPO_FILES=false
    fi
    ;;
  true|false) ;;
  *)
    die "Invalid RESTORE_GENERATED_REPO_FILES='${RESTORE_GENERATED_REPO_FILES}'. Expected: auto|true|false."
    ;;
esac

case "${POST_FLIGHT_MODE}" in
  declarative|inline|both) ;;
  *) die "Invalid POST_FLIGHT_MODE='${POST_FLIGHT_MODE}'. Expected: declarative|inline|both." ;;
esac

if [[ "${SELF_CHECK_ONLY}" == true ]]; then
  run_script_runtime_contract_check
  log "Self-check complete."
  exit 0
fi

if [[ "${PRE_DEPLOY_PREFLIGHT_ONLY}" == true ]]; then
  RUN_DISCOVERY=false
  RUN_HEALTH_CHECK=false
  RUN_FLATPAK_SYNC=false
  RUN_AI_SECRETS_BOOTSTRAP=false
fi

trap cleanup_on_exit EXIT
trap 'on_unexpected_error "$?" "${LINENO}" "${BASH_COMMAND}"' ERR

assert_non_root_entrypoint
prime_sudo_session

if [[ "${RECOVERY_MODE}" == true ]]; then
  ALLOW_PREVIOUS_BOOT_FSCK_FAILURE=true
  if [[ "$MODE" == "switch" ]]; then
    log "Recovery mode is active with switch mode (no reboot required). If switch hangs on your hardware, rerun with --boot."
  fi
fi

require_command nix
require_command nixos-rebuild
enable_flakes_runtime
load_service_endpoints
ensure_flake_visible_to_nix "${FLAKE_REF}"
resolve_host_from_flake_if_needed
snapshot_generated_repo_files
if [[ "${PRE_DEPLOY_PREFLIGHT_ONLY}" != true ]]; then
  persist_home_git_credentials_declarative
fi
run_timed_step "Roadmap Verification" run_roadmap_completion_verification
run_timed_step "Readiness Analysis" run_readiness_analysis

if [[ "${ANALYZE_ONLY}" == true ]]; then
  log "Readiness analysis complete (--analyze-only)."
  exit 0
fi

if [[ "$UPDATE_FLAKE_LOCK" == true ]]; then
  update_flake_lock "${FLAKE_REF}"
fi

ensure_host_facts_access
section "Preflight Validation"
if [[ "$RUN_DISCOVERY" == true ]]; then
  run_timed_step "Hardware Discovery" run_discovery_step
fi

ensure_host_facts_access
assert_host_storage_config
assert_previous_boot_fsck_clean
assert_runtime_account_unlocked "${PRIMARY_USER}" false
# Snapshot current password hash so we can detect accidental changes post-switch.
snapshot_password_hash "${PRIMARY_USER}"

NIXOS_TARGET="${NIXOS_TARGET_OVERRIDE:-${HOST_NAME}-${PROFILE}}"
HM_TARGET="${HM_TARGET_OVERRIDE:-${PRIMARY_USER}-${HOST_NAME}}"

if [[ -z "${HM_TARGET_OVERRIDE}" ]] && ! has_configuration_name "homeConfigurations" "${HM_TARGET}"; then
  HM_TARGET="${PRIMARY_USER}"
fi

assert_targets_exist "${NIXOS_TARGET}" "${HM_TARGET}"

if [[ "${RUN_AI_SECRETS_BOOTSTRAP}" == true || "${FORCE_AI_SECRETS_BOOTSTRAP}" == true ]]; then
  bootstrap_ai_stack_secrets_if_needed
else
  AI_SECRETS_BOOTSTRAP_STATUS="skipped:cli-disabled"
fi
log "AI secrets bootstrap status: ${AI_SECRETS_BOOTSTRAP_STATUS}"

log "NixOS target: ${NIXOS_TARGET}"
log "Home target: ${HM_TARGET}"

run_timed_step "Preflight Validation Loop" run_pre_deploy_validation_loop
if [[ "${PRE_DEPLOY_PREFLIGHT_ONLY}" == true ]]; then
  log "Preflight-only validation loop complete. No deploy actions were executed."
  exit 0
fi

assert_target_account_guardrails
assert_bootloader_preflight
assert_target_boot_mode
assert_safe_switch_context

if [[ "$RUN_PHASE0_DISKO" == true ]]; then
  if [[ "${DISKO_CONFIRM:-}" != "YES" ]]; then
    die "--phase0-disko is destructive. Re-run with DISKO_CONFIRM=YES to proceed."
  fi

  disk_layout="$(nix_eval_raw_safe "${FLAKE_REF}#nixosConfigurations.\"${NIXOS_TARGET}\".config.mySystem.disk.layout" 2>/dev/null || echo none)"
  if [[ "$disk_layout" == "none" ]]; then
    die "--phase0-disko requested but mySystem.disk.layout is 'none' for ${NIXOS_TARGET}."
  fi

  log "Running Phase 0 disko apply for layout '${disk_layout}' on target '${NIXOS_TARGET}'"
  run_privileged nix run github:nix-community/disko -- --mode disko "${FLAKE_REF}#${NIXOS_TARGET}"
  log "Phase 0 disko apply complete"
fi

if [[ "$RUN_SECUREBOOT_ENROLL" == true ]]; then
  secureboot_enabled="$(nix_eval_raw_safe "${FLAKE_REF}#nixosConfigurations.\"${NIXOS_TARGET}\".config.mySystem.secureboot.enable" 2>/dev/null || echo false)"
  if [[ "$secureboot_enabled" != "true" ]]; then
    die "--enroll-secureboot-keys requested but mySystem.secureboot.enable is not true for ${NIXOS_TARGET}."
  fi

  if [[ "${SECUREBOOT_ENROLL_CONFIRM:-}" != "YES" ]]; then
    die "--enroll-secureboot-keys requires SECUREBOOT_ENROLL_CONFIRM=YES."
  fi

  require_command sbctl
  log "Running sbctl key enrollment"
  run_privileged sbctl enroll-keys -m
  log "sbctl key enrollment complete"
fi

SYSTEM_GENERATION_BEFORE="$(current_system_generation)"
HOME_GENERATION_BEFORE="$(current_home_generation)"

if [[ "$MODE" == "build" ]]; then
  section "Build Mode"
  log "Running dry build"
  if [[ "${SKIP_SYSTEM_SWITCH}" == false ]]; then
    run_privileged nixos-rebuild dry-build --flake "${FLAKE_REF}#${NIXOS_TARGET}"
  else
    log "Skipping system dry-build"
  fi
  if [[ "${SKIP_HOME_SWITCH}" == false ]]; then
    home_build "${HM_TARGET}"
  else
    log "Skipping Home Manager build"
  fi
  log "Dry build complete"
  exit 0
fi

# ---- Pre-rebuild model download + SHA256 recording --------------------------
# Downloads missing GGUF models from HuggingFace BEFORE nixos-rebuild so that
# sha256 values are set declaratively in facts.nix at build time.
#
# facts.nix (generated by discover-system-facts.sh) always writes sha256 = null.
# This function:
#   1. Reads model paths + HuggingFace info from facts.nix
#   2. Downloads each model if the file is absent
#   3. Computes sha256sum of each file
#   4. Patches facts.nix with the actual sha256 values
#   5. Re-validates facts.nix with nix-instantiate
pre_rebuild_model_download() {
  [[ "${SKIP_SYSTEM_SWITCH}" == false ]] || return 0
  local facts_file="${REPO_ROOT}/nix/hosts/${HOST_NAME}/facts.nix"
  [[ -f "$facts_file" ]] || return 0

  # Parse model info from the generated facts.nix lines
  local chat_model_file chat_hf_repo chat_hf_file
  local chat_sha256 embed_sha256
  local embed_model_file embed_hf_repo embed_hf_file
  chat_model_file="$(grep -oP '(?<=llamaCpp\.model\s{0,30}=\s{0,5}")[^"]+' "$facts_file" | head -1 || true)"
  chat_hf_repo="$(grep -oP '(?<=llamaCpp\.huggingFaceRepo\s{0,30}=\s{0,5}")[^"]+' "$facts_file" | head -1 || true)"
  chat_hf_file="$(grep -oP '(?<=llamaCpp\.huggingFaceFile\s{0,30}=\s{0,5}")[^"]+' "$facts_file" | head -1 || true)"
  chat_sha256="$(grep -oP '(?<=llamaCpp\.sha256\s{0,30}=\s{0,5}")[^"]+' "$facts_file" | head -1 || true)"
  embed_model_file="$(grep -oP '(?<=embeddingServer\.model\s{0,30}=\s{0,5}")[^"]+' "$facts_file" | head -1 || true)"
  embed_hf_repo="$(grep -oP '(?<=embeddingServer\.huggingFaceRepo\s{0,30}=\s{0,5}")[^"]+' "$facts_file" | head -1 || true)"
  embed_hf_file="$(grep -oP '(?<=embeddingServer\.huggingFaceFile\s{0,30}=\s{0,5}")[^"]+' "$facts_file" | head -1 || true)"
  embed_sha256="$(grep -oP '(?<=embeddingServer\.sha256\s{0,30}=\s{0,5}")[^"]+' "$facts_file" | head -1 || true)"

  # Ensure model metadata for pre-rebuild.
  # IMPORTANT: pre-rebuild is non-network and non-destructive by design.
  # It must never download or replace model files.
  _ensure_model_matches() {
    local model_path="$1" hf_repo="$2" hf_file="$3" expected_sha="$4"
    [[ -n "$model_path" ]] || return 0
    [[ -n "$hf_repo" && -n "$hf_file" ]] || {
      log "  WARNING: no HuggingFace info — cannot validate model source: ${model_path}"
      return 0
    }
    local meta_path="${model_path}.source-meta"
    local desired_ref="${hf_repo}:${hf_file}:${expected_sha:-null}"
    local needs_download=true

    if run_privileged test -f "$model_path"; then
      local current_ref=""
      if run_privileged test -f "$meta_path"; then
        current_ref="$(run_privileged cat "$meta_path" 2>/dev/null || true)"
      fi

      if [[ "$current_ref" == "$desired_ref" ]]; then
        needs_download=false
      elif [[ -n "$expected_sha" ]]; then
        local existing_sha
        existing_sha="$(run_privileged sha256sum "$model_path" | awk '{print $1}')"
        if [[ "$existing_sha" == "$expected_sha" ]]; then
          run_privileged sh -c "printf '%s\n' '$desired_ref' > '$meta_path'"
          run_privileged chmod 0644 "$meta_path"
          needs_download=false
        fi
      elif [[ "$(basename "$model_path")" == "$hf_file" ]]; then
        # No pinned sha yet: if filename already matches requested source,
        # treat as converged and stamp metadata to avoid redundant downloads.
        run_privileged sh -c "printf '%s\n' '$desired_ref' > '$meta_path'"
        run_privileged chmod 0644 "$meta_path"
        needs_download=false
      fi

      if [[ "$needs_download" == true ]]; then
        log "  Model file exists but metadata/hash differs; skipping pre-rebuild replacement for ${model_path}"
        log "  Runtime fetch unit will reconcile on switch if replacement is required."
      fi
      return 0
    fi

    log "  Model file missing; skipping pre-rebuild download for ${model_path}"
    log "  Runtime fetch unit will download on switch if required."
    return 0
  }

  # Compute sha256 from file and patch the key in facts.nix.
  _record_sha256_in_facts() {
    local model_path="$1" sed_key="$2" hf_repo="$3" hf_file="$4"
    [[ -n "$model_path" ]] || return 0
    run_privileged test -f "$model_path" || return 0
    local current_pinned
    current_pinned="$(grep -oP "(?<=${sed_key}\\.sha256\\s{0,30}=\\s{0,5}\")[^\"]+" "$facts_file" | head -1 || true)"
    if [[ "${current_pinned}" =~ ^[a-fA-F0-9]{64}$ ]]; then
      log "  SHA256 already pinned (${sed_key}); skipping recompute."
      return 0
    fi
    local sha
    log "  Computing SHA256: $(basename "$model_path")"
    sha="$(run_privileged sha256sum "$model_path" | awk '{print $1}')"
    [[ -n "$sha" ]] || return 0
    # Always update this key so model changes cannot leave stale hashes.
    sed -i -E "s#(${sed_key}\\.sha256[[:space:]]*=[[:space:]]*)(null|\"[a-fA-F0-9]{64}\");#\\1\"${sha}\";#" "$facts_file"
    if [[ -n "$hf_repo" && -n "$hf_file" ]]; then
      local meta_path="${model_path}.source-meta"
      run_privileged sh -c "printf '%s\n' '${hf_repo}:${hf_file}:${sha}' > '$meta_path'"
      run_privileged chmod 0644 "$meta_path"
    fi
    log "  SHA256 recorded (${sed_key}): ${sha}"
  }

  log "Pre-rebuild: checking model files..."

  _ensure_model_matches "$chat_model_file"  "$chat_hf_repo"  "$chat_hf_file" "$chat_sha256"
  _ensure_model_matches "$embed_model_file" "$embed_hf_repo" "$embed_hf_file" "$embed_sha256"

  _record_sha256_in_facts "$chat_model_file"  "llamaCpp"        "$chat_hf_repo"  "$chat_hf_file"
  _record_sha256_in_facts "$embed_model_file" "embeddingServer" "$embed_hf_repo" "$embed_hf_file"

  # Re-validate facts.nix after patching
  if command -v nix-instantiate >/dev/null 2>&1; then
    if ! nix-instantiate --parse "$facts_file" >/dev/null 2>&1; then
      log "  WARNING: facts.nix parse error after SHA256 patch — reverting to null"
      sed -i -E 's|(llamaCpp\.sha256[[:space:]]*=[[:space:]]*)\"[a-f0-9]{64}\";|\1null;|' "$facts_file"
      sed -i -E 's|(embeddingServer\.sha256[[:space:]]*=[[:space:]]*)\"[a-f0-9]{64}\";|\1null;|' "$facts_file"
    fi
  fi
  log "Pre-rebuild: model check complete."
}

# Runs for both boot and switch modes; skipped for dry-build (exited above).
# Models are downloaded before nixos-rebuild so sha256 is set declaratively.
pre_rebuild_model_download

if [[ "$MODE" == "boot" ]]; then
  section "Boot Staging"
  log "Staging next boot generation"
  if [[ "${SKIP_SYSTEM_SWITCH}" == false ]]; then
    run_privileged nixos-rebuild boot --flake "${FLAKE_REF}#${NIXOS_TARGET}"
  else
    log "Skipping system boot staging (--skip-system-switch)"
  fi

  if [[ "${SKIP_HOME_SWITCH}" == false ]]; then
    log "Applying Home Manager configuration in boot mode"
    home_switch "${HM_TARGET}"
  else
    log "Skipping Home Manager switch (--skip-home-switch)"
  fi

  if [[ "$RUN_FLATPAK_SYNC" == true && -x "${REPO_ROOT}/scripts/data/sync-flatpak-profile.sh" ]]; then
    log "Syncing Flatpak apps for profile '${PROFILE}' (boot mode, system scope)"
    if "${REPO_ROOT}/scripts/data/sync-flatpak-profile.sh" --flake-ref "${FLAKE_REF}" --target "${NIXOS_TARGET}" --scope system; then
      log "Flatpak profile sync complete"
    else
      die "Flatpak profile sync failed in boot mode; declarative app state is not converged."
    fi
  fi

  log "Skipping deprecated npm global AI tooling sync (declarative-only mode)."

  log "Boot generation staged. Reboot to apply system-level changes (desktop, users, passwords, services)."
  exit 0
fi

if [[ "${SKIP_SYSTEM_SWITCH}" == false ]]; then
  section "System Switch"
  log "Switching system configuration"
  # Free any blocked AI stack ports before rebuild (prevents systemd service failures)
  free_blocked_ai_ports
  run_timed_step "System Switch" run_privileged nixos-rebuild switch --flake "${FLAKE_REF}#${NIXOS_TARGET}"
else
  log "Skipping system switch (--skip-system-switch)"
fi

if [[ "${SKIP_HOME_SWITCH}" == false ]]; then
  section "Home Switch"
  log "Switching Home Manager configuration"
  run_timed_step "Home Switch" home_switch "${HM_TARGET}"
else
  log "Skipping Home Manager switch (--skip-home-switch)"
fi

assert_runtime_account_unlocked "${PRIMARY_USER}" true
# Verify the switch did not unexpectedly reset the login password.
assert_password_unchanged "${PRIMARY_USER}"
assert_post_switch_desktop_outcomes

SYSTEM_GENERATION_AFTER="$(current_system_generation)"
HOME_GENERATION_AFTER="$(current_home_generation)"

if [[ "${SKIP_SYSTEM_SWITCH}" == false && -n "${SYSTEM_GENERATION_BEFORE}" && -n "${SYSTEM_GENERATION_AFTER}" && "${SYSTEM_GENERATION_BEFORE}" == "${SYSTEM_GENERATION_AFTER}" ]]; then
  log "System generation link unchanged after switch (${SYSTEM_GENERATION_AFTER}); this is expected when there are no system-level config changes."
fi

if [[ "${SKIP_HOME_SWITCH}" == false && -n "${HOME_GENERATION_BEFORE}" && -n "${HOME_GENERATION_AFTER}" && "${HOME_GENERATION_BEFORE}" == "${HOME_GENERATION_AFTER}" ]]; then
  log "Home Manager generation link unchanged after switch (${HOME_GENERATION_AFTER}); this is expected when there are no Home Manager config changes."
fi

restart_repo_backed_ai_services_if_needed

if [[ "$RUN_FLATPAK_SYNC" == true && -x "${REPO_ROOT}/scripts/data/sync-flatpak-profile.sh" ]]; then
  log "Syncing Flatpak apps for profile '${PROFILE}' (system scope)"
  if "${REPO_ROOT}/scripts/data/sync-flatpak-profile.sh" --flake-ref "${FLAKE_REF}" --target "${NIXOS_TARGET}" --scope system; then
    log "Flatpak profile sync complete"
  else
    die "Flatpak profile sync failed; declarative app state is not converged."
  fi
fi

log "Skipping deprecated npm global AI tooling sync (declarative-only mode)."

# ---- Runtime orchestration -------------------------------------------------
# Runtime lifecycle is declarative and module-owned. deploy-clean no longer
# evaluates legacy backend values or dispatches legacy phase scripts.
if [[ "${MODE}" != "build" ]]; then
  log "Skipping imperative runtime orchestration in deploy-clean (declarative ownership enabled)."
fi

if [[ "$RUN_HEALTH_CHECK" == true && -x "${REPO_ROOT}/scripts/health/system-health-check.sh" ]]; then
  section "Post-flight Health"
  run_nonfatal_postflight_check \
    "Running post-deploy health check" \
    "Post-deploy health check passed" \
    "Post-deploy health check reported issues (non-critical)" \
    run_timed_step "System Health Check" "${REPO_ROOT}/scripts/health/system-health-check.sh" --detailed
fi

if [[ -x "${REPO_ROOT}/scripts/compare-installed-vs-intended.sh" ]]; then
  run_nonfatal_postflight_check \
    "Running installed-vs-intended package comparison" \
    "Installed-vs-intended comparison passed" \
    "Installed-vs-intended comparison reported gaps (non-critical)" \
    "${REPO_ROOT}/scripts/compare-installed-vs-intended.sh" --host "${HOST_NAME}" --profile "${PROFILE}" --flake-ref "${FLAKE_REF}"
fi

# ---- AI MCP stack post-flight ------------------------------------------------
# Wait for AI services to be fully ready before running health checks
wait_for_ai_services() {
  log "Waiting for AI services to be ready..."
  load_service_endpoints
  local timeout=180
  local interval=5
  local service_name="" health_url=""

  _wait_http_health() {
    local service_name="$1"
    local health_url="$2"
    local elapsed=0

    log "  Waiting for ${service_name}..."
    while ! curl -sf --connect-timeout 2 --max-time 5 "${health_url}" >/dev/null 2>&1; do
      sleep "${interval}"
      elapsed=$((elapsed + interval))
      if (( elapsed >= timeout )); then
        log "  WARNING: ${service_name} not ready after ${timeout}s"
        return 1
      fi
    done
    log "  ${service_name} is ready"
    return 0
  }

  ai_service_health_targets() {
    printf '%s\t%s\n' "llama-cpp-embed.service" "${EMBEDDINGS_URL%/}/health"
    printf '%s\t%s\n' "ai-aidb.service" "${AIDB_URL%/}/health"
    printf '%s\t%s\n' "ai-hybrid-coordinator.service" "${HYBRID_URL%/}/health"
    printf '%s\t%s\n' "llama-cpp.service" "${LLAMA_URL%/}/health"
  }

  while IFS=$'\t' read -r service_name health_url; do
    [[ -n "${service_name}" && -n "${health_url}" ]] || continue
    if systemctl is-enabled --quiet "${service_name}" 2>/dev/null; then
      _wait_http_health "${service_name}" "${health_url}" || true
    fi
  done < <(ai_service_health_targets)

  log "AI services ready check complete"
}

# Wait for services before health checks
wait_for_ai_services
verify_repo_backed_ai_services_are_live_if_needed

# Verify TCP connectivity to Redis/Qdrant/Postgres and HTTP /health endpoints
# for all MCP services. Runs --optional to also report aider-wrapper and
# supplementary services. Non-blocking: issues are logged but do not abort.
if [[ "$RUN_HEALTH_CHECK" == true && -x "${REPO_ROOT}/scripts/testing/check-mcp-health.sh" ]]; then
  run_nonfatal_postflight_check \
    "Running AI stack MCP health check" \
    "AI MCP health check passed" \
    "AI MCP health check reported issues — check 'scripts/testing/check-mcp-health.sh --optional' for details (non-critical)" \
    "${REPO_ROOT}/scripts/testing/check-mcp-health.sh" --optional
fi

# ---- Embedding dimension migration (post-deploy) ----------------------------
# Detects a vector-dimension mismatch between the deployed config and the live
# pgvector table.  Drops document_embeddings, restarts AIDB (which recreates
# the table at the new dimension), then re-indexes agent instructions.
# Idempotent: no-op when dimensions already match or table doesn't exist yet.
run_embedding_migration_if_needed() {
  [[ "$RUN_HEALTH_CHECK" == true ]] || return 0

  # Only run when the embedding server is deployed for this host
  if ! systemctl is-active --quiet llama-cpp-embed.service 2>/dev/null &&
     ! systemctl is-activating --quiet llama-cpp-embed.service 2>/dev/null; then
    return 0
  fi

  # Get target dimension from deployed NixOS config
  local target_dim
  target_dim="$(nix eval --raw --impure \
    "${FLAKE_REF}#nixosConfigurations.\"${NIXOS_TARGET}\".config.mySystem.aiStack.embeddingDimensions" \
    2>/dev/null || echo "")"
  if [[ -z "$target_dim" || ! "$target_dim" =~ ^[0-9]+$ ]]; then
    return 0
  fi

  # Query current vector column typmod from pgvector
  # vector(N) stores typmod = N + 4; typmod -1 means unconstrained
  local current_typmod current_dim
  current_typmod="$(sudo -u postgres psql -d aidb -At \
    -c "SELECT a.atttypmod FROM pg_attribute a
        JOIN pg_class c ON a.attrelid = c.oid
        WHERE c.relname = 'document_embeddings'
          AND a.attname = 'embedding'
          AND c.relkind = 'r';" \
    2>/dev/null | tr -d '[:space:]' || echo "")"

  if [[ -z "$current_typmod" ]]; then
    return 0  # table doesn't exist yet; AIDB will create it at target_dim on first start
  fi

  if [[ "$current_typmod" == "-1" ]]; then
    current_dim="unconstrained"
  else
    current_dim=$(( current_typmod - 4 ))
  fi

  if [[ "$current_dim" == "$target_dim" ]]; then
    log "Embedding dimension OK: ${target_dim}-dim vectors (no migration needed)"
    return 0
  fi

  log "EMBEDDING MIGRATION: dimension mismatch (table=${current_dim}-dim, config=${target_dim}-dim)"
  log "  Vectors cannot be resized in-place — dropping document_embeddings..."
  if ! sudo -u postgres psql -d aidb \
       -c "DROP TABLE IF EXISTS document_embeddings CASCADE;" 2>/dev/null; then
    log "  WARNING: DROP TABLE failed — run manually:"
    log "    sudo -u postgres psql -d aidb -c 'DROP TABLE document_embeddings CASCADE;'"
    return 1
  fi

  log "  Restarting AIDB to recreate table at ${target_dim} dims..."
  run_privileged systemctl restart ai-aidb.service 2>/dev/null || true

  # Wait for AIDB /health to come back
  local aidb_port="8002" waited=0 max_wait=90
  while [[ $waited -lt $max_wait ]]; do
    if curl -fsS --max-time 3 "http://127.0.0.1:${aidb_port}/health" >/dev/null 2>&1; then
      log "  AIDB healthy — document_embeddings recreated at ${target_dim} dims"
      break
    fi
    sleep 3; waited=$(( waited + 3 ))
  done
  if [[ $waited -ge $max_wait ]]; then
    log "  WARNING: AIDB did not respond within ${max_wait}s"
    log "    Check: journalctl -u ai-aidb.service -n 30 --no-pager"
    return 1
  fi

  # Re-index agent instructions into the new embedding space
  if [[ -x "${REPO_ROOT}/scripts/data/import-agent-instructions.sh" ]]; then
    log "  Re-indexing agent instructions (new ${target_dim}-dim embedding space)..."
    if "${REPO_ROOT}/scripts/data/import-agent-instructions.sh" 2>/dev/null; then
      log "  Re-indexing complete"
    else
      log "  WARNING: Re-indexing failed — run manually: bash scripts/data/import-agent-instructions.sh"
    fi
  fi
}

# ---- Embedding SHA256 auto-record (post-deploy — DEPRECATED) -----------------
# Superseded by pre_rebuild_model_download() above which records sha256 BEFORE
# nixos-rebuild so the declarative config is correct from the first switch.
# Kept as a no-op stub to avoid breaking any external callers.
autorecord_embedding_sha256() {
  # Superseded by pre_rebuild_model_download() — sha256 is now recorded before
  # nixos-rebuild so the declarative config is correct from the first switch.
  return 0
}

run_embedding_migration_if_needed
autorecord_embedding_sha256

# ---- Command Center Dashboard post-flight ------------------------------------
# Confirm the dashboard API is reachable and reports a healthy/degraded probe result.
# Non-fatal: a down dashboard never aborts a successful deploy.
check_dashboard_postflight() {
  [[ "${RUN_HEALTH_CHECK}" == true ]] || return 0

  local endpoints_file="${REPO_ROOT}/config/service-endpoints.sh"
  local dashboard_api_url="${DASHBOARD_API_URL:-}"
  if [[ -z "${dashboard_api_url}" && -f "${endpoints_file}" ]]; then
    # shellcheck source=config/service-endpoints.sh
    source "${endpoints_file}"
    dashboard_api_url="${DASHBOARD_API_URL}"
  fi

  local probe_url="${dashboard_api_url%/}/api/health/probe"
  local status
  if status="$(curl -fsS --max-time 15 --connect-timeout 3 "${probe_url}" 2>/dev/null \
      | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("overall_status","unknown"))' 2>/dev/null)"; then
    log "Dashboard OK — ${dashboard_api_url%/} (status: ${status})"
  else
    log "WARNING: Dashboard did not respond at ${probe_url}"
    log "  Check: journalctl -u command-center-dashboard-api.service -n 20 --no-pager"
    log "  Rerun: scripts/testing/check-mcp-health.sh --optional"
  fi
}

restart_prometheus_after_nftables_update_if_needed() {
  # After nixos-rebuild switch the nftables ai_localhost_isolation table is
  # updated but Prometheus may have cached a "no route to host" error from before
  # the prometheus GID was added to the loopback filter. A restart clears that.
  if systemctl is-active prometheus.service &>/dev/null; then
    log "Restarting prometheus (nftables GID allowlist updated)..."
    sudo systemctl restart prometheus.service 2>/dev/null || true
  fi
}

run_dashboard_runtime_postflight() {
  check_dashboard_postflight
  restart_prometheus_after_nftables_update_if_needed
}

run_dashboard_runtime_postflight

run_postflight_convergence

print_completion_test_results
section "Completion Summary"
print_deploy_completion_summary
log "Clean deployment complete"
