#!/usr/bin/env bash
#
# NixOS Quick Deploy - Bootstrap Loader
# Version: 6.0.0
# Purpose: Orchestrate modular 8-phase deployment workflow
#
# ============================================================================
# ARCHITECTURE OVERVIEW
# ============================================================================
# This is the main entry point that orchestrates the 8-phase deployment
# workflow using a modular architecture.
#
# Workflow Phases (v6.0.0):
# - Phase 1: System Initialization - Validate requirements, install temp tools
# - Phase 2: System Backup - Comprehensive backup of system and user state
# - Phase 3: Configuration Generation - Generate declarative NixOS configs
# - Phase 4: Pre-deployment Validation - Validate configs, check conflicts
# - Phase 5: Declarative Deployment - Remove nix-env packages, apply configs
# - Phase 6: Additional Tooling - Install non-declarative tools (Claude Code)
# - Phase 7: Post-deployment Validation - Verify packages and services
# - Phase 8: Finalization and Report - Complete setup, generate report
# - Phase 9: K3s + Portainer + K8s Stack - Deploy AI stack into K3s and apply manifests
#
# Directory structure:
# nixos-quick-deploy.sh (this file) - Main entry point
# ├── config/                        - Configuration files
# │   ├── variables.sh               - Global variables
# │   └── defaults.sh                - Default values
# ├── lib/                           - Shared libraries
# │   ├── colors.sh                  - Terminal colors
# │   ├── logging.sh                 - Logging functions
# │   ├── error-handling.sh          - Error management
# │   ├── state-management.sh        - State tracking
# │   └── ... (additional libraries)
# └── phases/                        - Phase implementations
#     ├── phase-01-system-initialization.sh
#     ├── phase-02-system-backup.sh
#     ├── phase-03-configuration-generation.sh
#     ├── phase-04-pre-deployment-validation.sh
#     ├── phase-05-declarative-deployment.sh
#     ├── phase-06-additional-tooling.sh
#     ├── phase-07-post-deployment-validation.sh
#     └── phase-08-finalization-and-report.sh
#
# ============================================================================
# SCRIPT CONFIGURATION
# ============================================================================

# Bash strict mode
# set -e: Exit immediately if a command exits with a non-zero status
# set -u: Treat unset variables as an error and exit immediately
# set -o pipefail: Return value of pipeline is status of last command to exit with non-zero status
# set -E: ERR trap is inherited by shell functions
set -euo pipefail
set -E           # ERR trap inherited by functions

# ============================================================================
# READONLY CONSTANTS
# ============================================================================

readonly SCRIPT_VERSION="6.0.0"
readonly BOOTSTRAP_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly LIB_DIR="$BOOTSTRAP_SCRIPT_DIR/lib"
readonly CONFIG_DIR="$BOOTSTRAP_SCRIPT_DIR/config"
readonly PHASES_DIR="$BOOTSTRAP_SCRIPT_DIR/phases"

# Export SCRIPT_DIR for compatibility with libraries that expect it
readonly SCRIPT_DIR="$BOOTSTRAP_SCRIPT_DIR"
export SCRIPT_DIR

# ============================================================================
# EARLY ENVIRONMENT SETUP
# ============================================================================
# Ensure critical environment variables are set before any library loading
# USER might not be set in some environments (e.g., cron, systemd)
USER="${USER:-$(whoami 2>/dev/null || id -un 2>/dev/null || echo 'unknown')}"
export USER

# EUID is a bash built-in, but export it for consistency
export EUID

# ============================================================================
# EARLY LOGGING CONFIGURATION
# ============================================================================
# These variables must be defined BEFORE loading libraries (especially logging.sh)
# because logging.sh uses them immediately when init_logging() is called

# Create log directory path in user cache
readonly LOG_DIR="${HOME}/.cache/nixos-quick-deploy/logs"
# Create cache directory for preferences and state
readonly CACHE_DIR="${HOME}/.cache/nixos-quick-deploy"
# Create unique log file with timestamp
readonly LOG_FILE="${LOG_DIR}/deploy-$(date +%Y%m%d_%H%M%S).log"
# Set default log level (can be overridden by CLI args)
LOG_LEVEL="${LOG_LEVEL:-INFO}"
# Debug flag (can be overridden by CLI args)
ENABLE_DEBUG=false

# Export critical variables so they're available to all sourced files
export SCRIPT_VERSION
export LOG_DIR
export CACHE_DIR
export LOG_FILE
export LOG_LEVEL

# ============================================================================
# GLOBAL VARIABLES - CLI Flags
# ============================================================================

DRY_RUN=false
FORCE_UPDATE=false
# ENABLE_DEBUG defined above in EARLY LOGGING CONFIGURATION
ROLLBACK=false
RESET_STATE=false
FORCE_RESUME=false
SKIP_HEALTH_CHECK=false
VALIDATE_STATE=false
REPAIR_STATE=false
TEST_ROLLBACK=false
SHOW_HELP=false
SHOW_VERSION=false
QUIET_MODE=false
VERBOSE_MODE=false
LIST_PHASES=false
RESUME=true
RESTART_FAILED=false
RESTART_FROM_SAFE_POINT=false
ZSWAP_CONFIGURATION_OVERRIDE_REQUEST=""
EARLY_KMS_POLICY_OVERRIDE_REQUEST=""
AUTO_APPLY_SYSTEM_CONFIGURATION=true
AUTO_APPLY_HOME_CONFIGURATION=true
PROMPT_BEFORE_SYSTEM_SWITCH=false
PROMPT_BEFORE_HOME_SWITCH=false
AUTO_REGEN_CONFIG_ON_TEMPLATE_CHANGE=true
FLATPAK_REINSTALL_REQUEST=false
AUTO_UPDATE_FLAKE_INPUTS=false
FLAKE_ONLY_MODE=false
FLAKE_FIRST_MODE=true
LEGACY_PHASES_MODE=false
FLAKE_FIRST_PROFILE="ai-dev"
FLAKE_FIRST_PROFILE_EXPLICIT=false
FLAKE_FIRST_TARGET=""
FLAKE_FIRST_DEPLOY_MODE="switch"
RESTORE_KNOWN_GOOD_FLAKE_LOCK=false
SKIP_ROADMAP_VERIFICATION=false
FORCE_HF_DOWNLOAD=false
RUN_AI_PREP=false
RUN_AI_MODEL=true  # Default: Enable AI stack auto-deploy
AI_STACK_DISABLE_MARKER="/var/lib/nixos-quick-deploy/disable-ai-stack"
FLAKE_FIRST_AI_STACK_EXPLICIT=false
FLAKE_FIRST_MODEL_PROFILE="auto"
FLAKE_FIRST_EMBEDDING_MODEL=""
FLAKE_FIRST_LLM_MODEL=""
FLAKE_FIRST_LLM_MODEL_FILE=""
SKIP_AI_MODEL=false
ENABLE_AI_OPTIMIZER_PREP=false
RUN_K8S_STACK=true
RUN_K8S_E2E=false
AI_STACK_POSTGRES_DB="mcp"
AI_STACK_POSTGRES_USER="mcp"
AI_STACK_POSTGRES_PASSWORD=""
AI_STACK_GRAFANA_ADMIN_USER="admin"
AI_STACK_GRAFANA_ADMIN_PASSWORD=""
HOST_SWAP_LIMIT_ENABLED=false
HOST_SWAP_LIMIT_GB=""
HOST_SWAP_LIMIT_VALUE=""

# Declarative migration guardrails:
# - Flake-first is the default execution path.
# - Legacy phase/template rendering is maintenance mode (critical fixes only).
# - New config behavior must land in Nix modules/options first.
readonly TEMPLATE_PATH_FEATURE_POLICY="critical-fixes-only"

# Phase control
declare -a SKIP_PHASES=()
START_FROM_PHASE=""
RESTART_PHASE=""
TEST_PHASE=""
SHOW_PHASE_INFO_NUM=""
CURRENT_PHASE_NUM=""
CURRENT_PHASE_NAME=""

# Safe restart phases (can safely restart from these)
readonly SAFE_RESTART_PHASES=(1 3 8)

# ============================================================================
# PHASE NAME MAPPING
# ============================================================================

# Map numeric phase identifiers to their slug strings. Keep this table in sync
# with the files living under phases/phase-XX-*.sh so orchestration stays
# readable. Phase metadata is referenced throughout phase control helpers.
get_phase_name() {
    case $1 in
        1) echo "system-initialization" ;;
        2) echo "system-backup" ;;
        3) echo "configuration-generation" ;;
        4) echo "pre-deployment-validation" ;;
        5) echo "declarative-deployment" ;;
        6) echo "additional-tooling" ;;
        7) echo "post-deployment-validation" ;;
        8) echo "finalization-and-report" ;;
        9) echo "k3s-portainer" ;;
        *) echo "unknown" ;;
    esac
}

# Human-friendly descriptions for `--show-phase-info` and logging output.
get_phase_description() {
    case $1 in
        1) echo "System initialization - validate requirements and install temporary tools" ;;
        2) echo "System backup - comprehensive backup of all system and user state" ;;
        3) echo "Configuration generation - generate all declarative NixOS configs" ;;
        4) echo "Pre-deployment validation - validate configs and check for conflicts" ;;
        5) echo "Declarative deployment - remove nix-env packages and apply configs" ;;
        6) echo "Additional tooling - install non-declarative tools (Claude Code, etc.)" ;;
        7) echo "Post-deployment validation - verify packages and services running" ;;
        8) echo "Finalization and report - complete setup, validate Hybrid Stack, generate report" ;;
        9) echo "K3s + Portainer + K8s AI stack - deploy AI stack into K3s and apply manifests" ;;
        *) echo "Unknown phase" ;;
    esac
}

# Comma-separated dependency map per phase. These relationships ensure downstream
# steps only run when prerequisite steps have completed and are also referenced
# by `validate_phase_dependencies`.

# ============================================================================
# RUNTIME PATH VALIDATION
# ============================================================================
validate_runtime_paths() {
    if [[ -z "${HOME:-}" || ! -d "${HOME}" ]]; then
        print_error "HOME directory not found or invalid: ${HOME:-<unset>}"
        return 1
    fi

    local required_dirs=(
        "${LOG_DIR}"
        "${CACHE_DIR}"
        "${DOTFILES_ROOT:-}"
        "${AI_STACK_CONFIG_DIR:-}"
    )

    local path
    for path in "${required_dirs[@]}"; do
        [[ -n "$path" ]] || continue
        if ! mkdir -p "$path" 2>/dev/null; then
            print_error "Unable to create required directory: $path"
            return 1
        fi
        if [[ ! -w "$path" ]]; then
            print_error "Required directory is not writable: $path"
            return 1
        fi
    done

    if [[ -n "${TMPDIR:-}" ]]; then
        if [[ ! -d "${TMPDIR}" || ! -w "${TMPDIR}" ]]; then
            print_warning "TMPDIR not usable (${TMPDIR}); falling back to /tmp"
            export TMPDIR="/tmp"
        fi
    fi

    if [[ -n "${XDG_RUNTIME_DIR:-}" ]]; then
        if [[ ! -d "${XDG_RUNTIME_DIR}" || ! -w "${XDG_RUNTIME_DIR}" ]]; then
            print_warning "XDG_RUNTIME_DIR not usable (${XDG_RUNTIME_DIR}); unsetting to allow fallback"
            unset XDG_RUNTIME_DIR
        fi
    fi

    local xdg_var
    for xdg_var in XDG_CACHE_HOME XDG_STATE_HOME XDG_DATA_HOME; do
        local xdg_value="${!xdg_var:-}"
        if [[ -n "$xdg_value" ]]; then
            if ! mkdir -p "$xdg_value" 2>/dev/null || [[ ! -w "$xdg_value" ]]; then
                print_warning "${xdg_var} not usable (${xdg_value}); unsetting to allow fallback"
                unset "$xdg_var"
            fi
        fi
    done

    return 0
}

# ============================================================================
# INTER-PHASE HEALTH CHECKS
# ============================================================================
HEALTH_CHECK_STATUS=""
HEALTH_CHECK_MESSAGE=""

reset_health_check_status() {
    HEALTH_CHECK_STATUS=""
    HEALTH_CHECK_MESSAGE=""
}

health_check_phase_1() {
    reset_health_check_status
    local issues=0
    local warnings=0

    # Swap verification (warn if missing)
    if declare -F calculate_active_swap_total_gb >/dev/null 2>&1; then
        local swap_total
        swap_total=$(calculate_active_swap_total_gb 2>/dev/null || echo 0)
        if [[ "$swap_total" =~ ^[0-9]+$ ]] && (( swap_total > 0 )); then
            print_success "Health check: swap detected (${swap_total}GiB)"
        else
            print_warning "Health check: no active swap detected"
            warnings=$((warnings + 1))
        fi
    fi

    # Prerequisite commands
    local cmd
    for cmd in jq git systemctl; do
        if ! command -v "$cmd" >/dev/null 2>&1; then
            print_error "Health check: missing required command $cmd"
            issues=$((issues + 1))
        fi
    done

    if (( issues > 0 )); then
        HEALTH_CHECK_STATUS="fail"
        HEALTH_CHECK_MESSAGE="Missing critical prerequisites"
        return 1
    fi

    if (( warnings > 0 )); then
        HEALTH_CHECK_STATUS="warn"
        HEALTH_CHECK_MESSAGE="Swap not detected"
    else
        HEALTH_CHECK_STATUS="pass"
        HEALTH_CHECK_MESSAGE="Swap + prerequisites ok"
    fi

    return 0
}

health_check_phase_3() {
    reset_health_check_status
    local issues=0

    local required_files=(
        "${SYSTEM_CONFIG_FILE:-}"
        "${HOME_MANAGER_FILE:-}"
        "${FLAKE_FILE:-}"
        "${HARDWARE_CONFIG_FILE:-}"
    )

    local path
    for path in "${required_files[@]}"; do
        if [[ -z "$path" || ! -s "$path" ]]; then
            print_error "Health check: missing generated config file: $path"
            issues=$((issues + 1))
        fi
    done

    if (( issues > 0 )); then
        HEALTH_CHECK_STATUS="fail"
        HEALTH_CHECK_MESSAGE="Generated configs missing"
        return 1
    fi

    HEALTH_CHECK_STATUS="pass"
    HEALTH_CHECK_MESSAGE="Generated configs present"
    return 0
}

health_check_phase_5() {
    reset_health_check_status
    local issues=0
    local warnings=0

    if [[ "$AUTO_APPLY_SYSTEM_CONFIGURATION" == true ]]; then
        if [[ ! -e /run/current-system ]]; then
            print_error "Health check: /run/current-system missing after switch"
            issues=$((issues + 1))
        fi
    fi

    if [[ "$AUTO_APPLY_HOME_CONFIGURATION" == true ]]; then
        local hm_profile="/nix/var/nix/profiles/per-user/${USER}/home-manager"
        local hm_profile_user="$HOME/.local/state/nix/profiles/home-manager"
        if [[ ! -e "$hm_profile" && ! -e "$hm_profile_user" ]]; then
            print_warning "Health check: home-manager profile not found at $hm_profile or $hm_profile_user"
            warnings=$((warnings + 1))
        fi
    fi

    if (( issues > 0 )); then
        HEALTH_CHECK_STATUS="fail"
        HEALTH_CHECK_MESSAGE="System switch validation failed"
        return 1
    fi

    if (( warnings > 0 )); then
        HEALTH_CHECK_STATUS="warn"
        HEALTH_CHECK_MESSAGE="Home-manager profile missing"
    else
        HEALTH_CHECK_STATUS="pass"
        HEALTH_CHECK_MESSAGE="System + home-manager OK"
    fi

    return 0
}

health_check_phase_9() {
    reset_health_check_status
    local issues=0
    local warnings=0
    local kubectl_timeout="${KUBECTL_TIMEOUT:-20}"
    local namespace="${AI_STACK_NAMESPACE:-ai-stack}"

    if [[ -z "${KUBECONFIG:-}" && -f /etc/rancher/k3s/k3s.yaml ]]; then
        export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
    fi

    if ! command -v kubectl >/dev/null 2>&1; then
        print_error "Health check: kubectl not found"
        issues=$((issues + 1))
    else
        if ! kubectl --request-timeout="${kubectl_timeout}s" get nodes >/dev/null 2>&1; then
            print_error "Health check: kubectl cannot reach cluster"
            issues=$((issues + 1))
        fi

        local pods
        pods=$(kubectl --request-timeout="${kubectl_timeout}s" get pods -n "$namespace" --no-headers 2>/dev/null || true)
        if [[ -z "$pods" ]]; then
            print_warning "Health check: no ${namespace} pods reported"
            warnings=$((warnings + 1))
        else
            local running_count
            running_count=$(echo "$pods" | awk '$3 == "Running" || $3 == "Completed" {count++} END {print count+0}')
            if (( running_count == 0 )); then
                print_warning "Health check: ${namespace} pods not running yet"
                warnings=$((warnings + 1))
            fi
        fi

        if [[ "${AUTO_REPAIR_IMAGE_PULLS:-true}" == "true" ]]; then
            if auto_repair_k8s_image_pulls "$namespace"; then
                print_success "Health check: image pull failures auto-remediated"
            else
                print_warning "Health check: image pull auto-remediation not applied or failed"
            fi
        fi
    fi

    if (( issues > 0 )); then
        HEALTH_CHECK_STATUS="fail"
        HEALTH_CHECK_MESSAGE="Kubernetes cluster unavailable"
        return 1
    fi

    if (( warnings > 0 )); then
        HEALTH_CHECK_STATUS="warn"
        HEALTH_CHECK_MESSAGE="AI stack pods not fully running"
    else
        HEALTH_CHECK_STATUS="pass"
        HEALTH_CHECK_MESSAGE="Kubernetes cluster + AI stack OK"
    fi

    return 0
}

detect_k8s_image_pull_failures() {
    local namespace="$1"
    local kubectl_timeout="${KUBECTL_TIMEOUT:-20}"
    local failures=""
    local data
    data=$(kubectl --request-timeout="${kubectl_timeout}s" get pods -n "$namespace" -o jsonpath='{range .items[*]}{range .status.containerStatuses[*]}{.state.waiting.reason}{"|"}{.image}{"\n"}{end}{range .status.initContainerStatuses[*]}{.state.waiting.reason}{"|"}{.image}{"\n"}{end}{end}' 2>/dev/null || true)
    if [[ -z "$data" ]]; then
        echo ""
        return 0
    fi
    while IFS='|' read -r reason image; do
        [[ -z "$reason" || -z "$image" ]] && continue
        if [[ "$reason" == "ImagePullBackOff" || "$reason" == "ErrImagePull" ]]; then
            failures+="${image} "
        fi
    done <<< "$data"
    echo "${failures%% }"
}

map_image_to_build_dir() {
    case "$1" in
        ai-stack-aidb) echo "aidb" ;;
        ai-stack-embeddings) echo "embeddings-service" ;;
        ai-stack-hybrid-coordinator) echo "hybrid-coordinator" ;;
        ai-stack-ralph-wiggum) echo "ralph-wiggum" ;;
        ai-stack-container-engine) echo "container-engine" ;;
        ai-stack-aider-wrapper) echo "aider-wrapper" ;;
        ai-stack-nixos-docs) echo "nixos-docs" ;;
        ai-stack-dashboard-api) echo "dashboard-api" ;;
        ai-stack-health-monitor) echo "health-monitor" ;;
        *) echo "" ;;
    esac
}

map_image_to_deployment() {
    case "$1" in
        ai-stack-embeddings) echo "embeddings" ;;
        ai-stack-dashboard-api) echo "dashboard-api" ;;
        ai-stack-health-monitor) echo "health-monitor" ;;
        ai-stack-container-engine) echo "container-engine" ;;
        ai-stack-aider-wrapper) echo "aider-wrapper" ;;
        ai-stack-nixos-docs) echo "nixos-docs" ;;
        ai-stack-hybrid-coordinator) echo "hybrid-coordinator" ;;
        ai-stack-ralph-wiggum) echo "ralph-wiggum" ;;
        ai-stack-aidb) echo "aidb" ;;
        *) echo "" ;;
    esac
}

auto_repair_k8s_image_pulls() {
    local namespace="$1"
    local failures
    local kubectl_timeout="${KUBECTL_TIMEOUT:-20}"
    local rollout_timeout="${AI_STACK_ROLLOUT_TIMEOUT:-180}"
    local build_script="${SCRIPT_DIR}/scripts/build-k3s-images.sh"
    local publish_script="${SCRIPT_DIR}/scripts/publish-local-registry.sh"

    failures=$(detect_k8s_image_pull_failures "$namespace")
    if [[ -z "$failures" ]]; then
        return 0
    fi

    if [[ ! -x "$build_script" || ! -x "$publish_script" ]]; then
        print_warning "Auto-repair: build/publish scripts not available"
        return 1
    fi

    if ! command -v buildah >/dev/null 2>&1; then
        print_warning "Auto-repair: buildah not available"
        return 1
    fi

    if ! command -v skopeo >/dev/null 2>&1; then
        print_warning "Auto-repair: skopeo not available"
        return 1
    fi

    declare -A build_dirs=()
    declare -A restart_deploys=()
    declare -A publish_by_tag=()

    for image in $failures; do
        local image_ref="${image##*/}"
        local base="${image_ref%%:*}"
        local tag="${image_ref#*:}"
        if [[ "$tag" == "$base" ]]; then
            tag="latest"
        fi
        local build_dir
        build_dir=$(map_image_to_build_dir "$base")
        if [[ -n "$build_dir" ]]; then
            build_dirs["$build_dir"]=1
            if [[ -z "${publish_by_tag[$tag]:-}" ]]; then
                publish_by_tag["$tag"]="$base"
            elif [[ " ${publish_by_tag[$tag]} " != *" ${base} "* ]]; then
                publish_by_tag["$tag"]+=",${base}"
            fi
            local deploy
            deploy=$(map_image_to_deployment "$base")
            [[ -n "$deploy" ]] && restart_deploys["$deploy"]=1
        else
            print_warning "Auto-repair: unrecognized image ${base}, skipping"
        fi
    done

    if (( ${#build_dirs[@]} == 0 )); then
        print_warning "Auto-repair: no buildable images detected"
        return 1
    fi

    local build_list
    build_list=$(IFS=,; echo "${!build_dirs[*]}")

    print_info "Auto-repair: building images (${build_list})"
    if ! BUILD_TOOL=buildah SKIP_K3S_IMPORT=true ONLY_IMAGES="$build_list" "$build_script"; then
        print_warning "Auto-repair: build failed"
        return 1
    fi

    for tag in "${!publish_by_tag[@]}"; do
        local publish_list="${publish_by_tag[$tag]}"
        print_info "Auto-repair: publishing images (${publish_list}) with tag ${tag}"
        if ! CONTAINER_CLI=skopeo ONLY_IMAGES="$publish_list" TAG="$tag" "$publish_script"; then
            print_warning "Auto-repair: publish failed"
            return 1
        fi
    done

    if (( ${#restart_deploys[@]} > 0 )); then
        local restart_list
        local -a restart_args=()
        local -a failed_deploys=()
        local retry_on_failure="${AUTO_REPAIR_IMAGE_PULLS_RETRY:-true}"
        restart_list=$(IFS=' '; echo "${!restart_deploys[*]}")
        for deploy in "${!restart_deploys[@]}"; do
            restart_args+=("deployment/${deploy}")
        done
        print_info "Auto-repair: restarting deployments (${restart_list})"
        kubectl --request-timeout="${kubectl_timeout}s" rollout restart -n "$namespace" "${restart_args[@]}" >/dev/null 2>&1 || true

        local rollout_failed=0
        for deploy in "${!restart_deploys[@]}"; do
            if ! kubectl --request-timeout="${kubectl_timeout}s" rollout status -n "$namespace" "deployment/${deploy}" --timeout="${rollout_timeout}s" >/dev/null 2>&1; then
                rollout_failed=1
                failed_deploys+=("$deploy")
                print_warning "Auto-repair: rollout failed for ${deploy}"
            fi
        done
        if (( rollout_failed > 0 )) && [[ "$retry_on_failure" == "true" ]]; then
            print_warning "Auto-repair: retrying rollout once for failed deployments."
            sleep 5
            rollout_failed=0
            for deploy in "${failed_deploys[@]}"; do
                kubectl --request-timeout="${kubectl_timeout}s" rollout restart -n "$namespace" "deployment/${deploy}" >/dev/null 2>&1 || true
                if ! kubectl --request-timeout="${kubectl_timeout}s" rollout status -n "$namespace" "deployment/${deploy}" --timeout="${rollout_timeout}s" >/dev/null 2>&1; then
                    rollout_failed=1
                    print_warning "Auto-repair: rollout retry failed for ${deploy}"
                fi
            done
        fi
        if (( rollout_failed > 0 )); then
            return 1
        fi
    fi

    return 0
}

run_inter_phase_health_check() {
    local phase_num="$1"

    if [[ "$SKIP_HEALTH_CHECK" == true ]]; then
        print_info "Skipping inter-phase health checks (--skip-health-check)"
        if declare -F record_health_check >/dev/null 2>&1; then
            record_health_check "$phase_num" "skipped" "Skipped via --skip-health-check"
        fi
        return 0
    fi

    case "$phase_num" in
        1) health_check_phase_1 ;;
        3) health_check_phase_3 ;;
        5) health_check_phase_5 ;;
        9) health_check_phase_9 ;;
        *) return 0 ;;
    esac

    local exit_code=$?
    local status="${HEALTH_CHECK_STATUS:-unknown}"
    local message="${HEALTH_CHECK_MESSAGE:-}"

    if declare -F record_health_check >/dev/null 2>&1; then
        record_health_check "$phase_num" "$status" "$message"
    fi

    if [[ "$exit_code" -ne 0 ]]; then
        print_error "Phase ${phase_num} health check failed: ${message}"
        return "$exit_code"
    fi

    if [[ "$status" == "warn" ]]; then
        print_warning "Phase ${phase_num} health check warning: ${message}"
    else
        print_success "Phase ${phase_num} health check passed"
    fi

    return 0
}

print_inter_phase_health_summary() {
    if [[ ! -f "${STATE_FILE:-}" ]]; then
        return 0
    fi

    print_section "Inter-Phase Health Summary"

    if command -v jq >/dev/null 2>&1; then
        local summary
        summary=$(jq -r '.health_checks // [] | if length == 0 then "" else .[] | "\(.phase)\t\(.status)\t\(.checked_at)\t\(.message)" end' "$STATE_FILE" 2>/dev/null || true)
        if [[ -z "$summary" ]]; then
            print_info "No inter-phase health checks recorded."
            return 0
        fi
        while IFS=$'\t' read -r phase status checked_at message; do
            printf "  • Phase %s: %s (%s) %s\n" "$phase" "$status" "$checked_at" "$message"
        done <<< "$summary"
    elif command -v python3 >/dev/null 2>&1; then
        python3 - "$STATE_FILE" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as handle:
    data = json.load(handle)

checks = data.get("health_checks", [])
if not checks:
    print("  • No inter-phase health checks recorded.")
    sys.exit(0)

for entry in checks:
    phase = entry.get("phase", "?")
    status = entry.get("status", "?")
    checked_at = entry.get("checked_at", "unknown")
    message = entry.get("message", "")
    print(f"  • Phase {phase}: {status} ({checked_at}) {message}")
PY
    else
        print_info "No JSON parser available to render health summary."
    fi
}
get_phase_dependencies() {
    case $1 in
        1) echo "" ;;
        2) echo "1" ;;
        3) echo "1,2" ;;
        4) echo "1,2,3" ;;
        5) echo "1,2,3,4" ;;
        6) echo "1,2,3,4,5" ;;
        7) echo "1,2,3,4,5,6" ;;
        8) echo "1,2,3,4,5,6,7" ;;
        9) echo "1,2,3,4,5,6,7,8" ;;
        *) echo "" ;;
    esac
}

# Treat a phase dependency as satisfied if either the phase marker or its
# phase-specific completion marker exists. This also backfills missing
# phase markers when the phase outputs are already present (e.g., phases
# run directly without the main orchestrator).
phase_dependency_satisfied() {
    local phase_num="$1"
    local phase_step
    phase_step="phase-$(printf '%02d' "$phase_num")"

    if is_step_complete "$phase_step"; then
        return 0
    fi

    local fallback_step=""
    case "$phase_num" in
        1) fallback_step="system_initialization" ;;
        2) fallback_step="comprehensive_backup" ;;
        3) fallback_step="generate_validate_configs" ;;
        4) fallback_step="pre_deployment_validation" ;;
        5) fallback_step="deploy_configurations" ;;
        6) fallback_step="install_tools_services" ;;
        7) fallback_step="post_install_validation" ;;
        8) fallback_step="finalization_and_report" ;;
    esac

    if [[ -n "$fallback_step" ]] && is_step_complete "$fallback_step"; then
        print_warning "State backfill: marking ${phase_step} complete based on ${fallback_step}."
        mark_step_complete "$phase_step"
        return 0
    fi

    if [[ "$phase_num" == "3" ]]; then
        local hm_dir="${HM_CONFIG_DIR:-$HOME/.dotfiles/home-manager}"
        if [[ -f "$hm_dir/flake.nix" && -f "$hm_dir/home.nix" && -f "$hm_dir/configuration.nix" ]]; then
            print_warning "State backfill: marking ${phase_step} complete based on generated configs."
            mark_step_complete "$phase_step"
            return 0
        fi
    fi

    if [[ "$phase_num" == "1" ]]; then
        local pref_dir="${DEPLOYMENT_PREFERENCES_DIR:-$HOME/.cache/nixos-quick-deploy/preferences}"
        if [[ -d "$pref_dir" ]] && find "$pref_dir" -maxdepth 1 -type f -print -quit 2>/dev/null | grep -q .; then
            print_warning "State backfill: marking ${phase_step} complete based on cached preferences."
            mark_step_complete "$phase_step"
            return 0
        fi
    fi

    if [[ "$phase_num" == "2" ]]; then
        local backups_dir="${STATE_DIR:-$HOME/.cache/nixos-quick-deploy}/backups"
        if [[ -d "$backups_dir" ]] && find "$backups_dir" -type f -name "manifest.txt" -print -quit 2>/dev/null | grep -q .; then
            print_warning "State backfill: marking ${phase_step} complete based on backup manifest."
            mark_step_complete "$phase_step"
            return 0
        fi
    fi

    if [[ "$phase_num" == "4" ]]; then
        local hm_dir="${HM_CONFIG_DIR:-$HOME/.dotfiles/home-manager}"
        local sys_config="${SYSTEM_CONFIG_FILE:-$hm_dir/configuration.nix}"
        if [[ -f "$hm_dir/flake.nix" && -f "$hm_dir/home.nix" && -f "$sys_config" ]]; then
            print_warning "State backfill: marking ${phase_step} complete based on generated configs."
            mark_step_complete "$phase_step"
            return 0
        fi
    fi

    if [[ "$phase_num" == "5" ]]; then
        local hm_link_dir="$HOME/.config/home-manager"
        if [[ -f "$hm_link_dir/flake.nix" && -f "$hm_link_dir/home.nix" ]]; then
            print_warning "State backfill: marking ${phase_step} complete based on home-manager links."
            mark_step_complete "$phase_step"
            return 0
        fi
    fi

    # Phase 8 depends on phases 6+7. If finalization completed, treat missing
    # phase-06/07 markers as stale state and backfill them.
    if [[ "$phase_num" == "6" || "$phase_num" == "7" ]]; then
        if is_step_complete "phase-08" || is_step_complete "finalization_and_report"; then
            print_warning "State backfill: marking ${phase_step} complete based on phase-08 completion."
            mark_step_complete "$phase_step"
            return 0
        fi
    fi

    return 1
}

# ============================================================================
# LIBRARY LOADING
# ============================================================================

# Load every helper under $LIB_DIR (set near the top of this file). These
# libraries expose functions like `log`, `print_*`, and configuration helpers
# consumed later in the bootstrap.
load_libraries() {
    local libs=(
        "error-codes.sh"
        "colors.sh"
        "logging-structured.sh"
        "logging.sh"
        "error-handling.sh"
        "state-management.sh"
        "user-interaction.sh"
        "validation.sh"
        "retry.sh"
        "backup.sh"
        "secrets.sh"
        "gpu-detection.sh"
        "hardware-detect.sh"
        "ai-optimizer.sh"
        "python.sh"
        "nixos.sh"
        "packages.sh"
        "home-manager.sh"
        "user.sh"
        "config.sh"
        "flatpak.sh"
        "timeout.sh"
        "retry-backoff.sh"
        "validation-input.sh"
        "tools.sh"
        "service-conflict-resolution.sh"
        "finalization.sh"
        "reporting.sh"
        "progress.sh"
        "dry-run.sh"
        "common.sh"
        "dashboard.sh"
    )

    echo "Loading libraries..."

    for lib in "${libs[@]}"; do
        local lib_path="$LIB_DIR/$lib"

        if [[ ! -f "$lib_path" ]]; then
            echo "FATAL: Library not found: $lib_path" >&2
            exit 1
        fi

        source "$lib_path" || {
            echo "FATAL: Failed to load library: $lib" >&2
            exit 1
        }

        echo "  ✓ Loaded: $lib"
    done
    echo ""
}

# ============================================================================
# CONFIGURATION LOADING
# ============================================================================

# Source configuration shells from $CONFIG_DIR (variables.sh/defaults.sh). At
# this stage strict mode is still relaxed so missing vars won't explode.
load_configuration() {
    local configs=(
        "settings.sh"
        "variables.sh"
        "defaults.sh"
    )

    echo "Loading configuration..."

    for config in "${configs[@]}"; do
        local config_path="$CONFIG_DIR/$config"
        if [[ ! -f "$config_path" ]]; then
            echo "FATAL: Configuration not found: $config_path" >&2
            exit 1
        fi

        # Source config files
        # Note: set -u is not yet enabled at this point, so undefined variables
        # won't cause errors. Critical variables like LOG_DIR, LOG_FILE, and
        # SCRIPT_VERSION are already defined in main script before this runs.
        if source "$config_path" 2>/dev/null; then
            echo "  ✓ Loaded: $config"
        else
            echo "FATAL: Failed to load configuration: $config" >&2
            exit 1
        fi
    done

    echo ""
}

# ============================================================================
# HELP AND USAGE
# ============================================================================

# CLI helper: display version/build info for `--version`.
print_version() {
    cat << EOF
NixOS Quick Deploy - Modular Bootstrap Loader
Version: $SCRIPT_VERSION
Architecture: 8-phase modular deployment system

Components:
  - 10 library files (colors, logging, error-handling, state, etc.)
  - 2 config files (variables, defaults)
  - 8 phase modules (system-initialization through finalization-and-report)
  - 1 bootstrap orchestrator (this script)

Copyright (c) 2025
License: MIT
Repository: https://github.com/MasterofNull/NixOS-Dev-Quick-Deploy

For help: $(basename "$0") --help
EOF
}

# Long-form usage text for `--help`. Keep option descriptions in sync with
# `parse_arguments`.
print_usage() {
    cat << 'EOF'
NixOS Quick Deploy - Bootstrap Loader v6.0.0

USAGE:
    ./nixos-quick-deploy.sh [OPTIONS]

BASIC OPTIONS:
    -h, --help                  Show this help message
    -v, --version               Show version information
    -q, --quiet                 Quiet mode (only warnings and errors)
        --verbose               Verbose mode (detailed output)
    -d, --debug                 Enable debug mode (trace execution)
    -f, --force-update          Force recreation of configurations
        --dry-run               Preview changes without applying
        --rollback              Rollback to previous state
        --reset-state           Clear state for fresh start
        --skip-health-check     Skip health check validation
        --validate-state        Fail if resume state does not match expected outputs
        --force-resume          Skip state version validation on resume
        --repair-state          Clear mismatched phase entries from state before resume
        --test-rollback         Perform a rollback + restore validation after deployment
        --enable-zswap          Force-enable zswap-backed hibernation setup (persists)
        --disable-zswap         Force-disable zswap-backed hibernation setup (persists)
        --zswap-auto            Return to automatic zswap detection (clears override)
        --disable-early-kms     Disable initrd early-KMS module preloading (safety fallback)
        --early-kms-auto        Enable guarded automatic early-KMS module preloading policy
        --force-early-kms       Force initrd early-KMS module preloading (advanced/debug)
        --skip-switch           Skip automatic nixos/home-manager switch steps
        --skip-system-switch    Skip automatic nixos-rebuild switch
        --skip-home-switch      Skip automatic home-manager switch
        --prefix PATH           Override dotfiles root (default: ~/.dotfiles)
        --flatpak-reinstall     Force reinstall of managed Flatpaks (resets Flatpak state pre-switch)
        --force-hf-download     Force re-download of Hugging Face TGI models before the switch
        --update-flake-inputs   Run 'nix flake update' before activation (opt-in)
        --flake-only            Skip nix-channel updates (flake handles package resolution)
        --flake-first           Use direct flake-first deployment path (default)
        --legacy-phases         Use legacy 9-phase pipeline (maintenance mode, critical fixes only)
        --flake-first-profile P Select profile for flake-first mode (ai-dev|gaming|minimal)
        --flake-first-target T  Override nixosConfigurations target in flake-first mode
        --flake-first-deploy-mode M
                                Deploy mode for flake-first path (switch|boot|build)
        --restore-flake-lock    Re-seed flake.lock from the bundled baseline
        --skip-roadmap-verification
                                Skip flake-first roadmap-completion verifier preflight
        --with-ai-prep          Run the optional AI-Optimizer preparation phase after Phase 8
        --with-ai-model         Force enable Hybrid Learning Stack deployment (default: disabled)
        --without-ai-model      Skip AI model deployment phase (disable default prompt)
        --flake-first-ai-stack [on|off]
                                Override declarative AI stack role for flake-first runs
        --flake-first-model-profile P
                                Model profile for flake-first (auto|small|medium|large)
        --with-k8s-stack        (deprecated) K3s + Portainer + K8s AI stack is now always enabled
        --with-k8s-e2e          Run hospital K3s E2E tests after K8s deployment
        --without-k8s-e2e       Skip hospital K3s E2E tests
        --prompt-switch         Prompt before running system/home switches
        --prompt-system-switch  Prompt before running nixos-rebuild switch
        --prompt-home-switch    Prompt before running home-manager switch

PHASE CONTROL OPTIONS:
        --skip-phase N          Skip specific phase number (1-8)
                                Can be used multiple times
        --start-from-phase N    Start execution from phase N onwards
        --restart-phase N       Restart from specific phase number
        --test-phase N          Test specific phase in isolation
        --resume                Resume from last failed phase (default)
        --restart-failed        Restart the failed phase from beginning
        --restart-from-safe-point   Restart from last safe entry point

INFORMATION OPTIONS:
        --list-phases           List all phases with status
        --show-phase-info N     Show detailed info about phase N

PHASE OVERVIEW:
    Phase 1:  System Initialization       - Validate requirements, install temp tools
    Phase 2:  System Backup               - Comprehensive system and user backup
    Phase 3:  Configuration Generation    - Generate declarative NixOS configs
    Phase 4:  Pre-deployment Validation   - Validate configs, check conflicts
    Phase 5:  Declarative Deployment      - Remove nix-env packages, apply configs
    Phase 6:  Additional Tooling          - Install non-declarative tools
    Phase 7:  Post-deployment Validation  - Verify packages and services
    Phase 8:  Finalization and Report     - Complete setup, validate Hybrid Stack, generate report
    Phase 9:  K3s + Portainer + K8s Stack - Deploy AI stack into K3s and apply manifests

EXAMPLES:
    # Normal deployment (resumes from last failure if any)
    ./nixos-quick-deploy.sh

    # Start fresh deployment
    ./nixos-quick-deploy.sh --reset-state

    # Skip health check and start from phase 3
    ./nixos-quick-deploy.sh --skip-health-check --start-from-phase 3

    # Skip specific phases
    ./nixos-quick-deploy.sh --skip-phase 5 --skip-phase 7

    # Test a specific phase
    ./nixos-quick-deploy.sh --test-phase 4

    # List all phases with current status
    ./nixos-quick-deploy.sh --list-phases

    # Show detailed info about a phase
    ./nixos-quick-deploy.sh --show-phase-info 6

    # Rollback to previous state
    ./nixos-quick-deploy.sh --rollback

    # Dry run to preview changes
    ./nixos-quick-deploy.sh --dry-run

    # Flake-first with explicit deploy mode (no reboot unless mode=boot)
    ./nixos-quick-deploy.sh --flake-first --flake-first-profile ai-dev --flake-first-deploy-mode switch

SAFE RESTART POINTS:
    Phases 1, 3, and 8 are safe restart points. Other phases may require
    dependency validation before restarting.

FOR MORE INFORMATION:
    Visit: https://github.com/MasterofNull/NixOS-Dev-Quick-Deploy
    Logs: ~/.cache/nixos-quick-deploy/logs/

ENVIRONMENT OVERRIDES:
    ALLOW_ROOT_DEPLOY=true     Allow running as root/sudo (not recommended)
    AUTO_PROMPT_PROFILE_SELECTION=false
                              Disable interactive profile prompt when profile flag is omitted

EOF
}

# ============================================================================
# ARGUMENT PARSING
# ============================================================================

# Central CLI parser. Flags toggle the globals declared in the "GLOBAL
# VARIABLES - CLI Flags" section (lines ~120-210) so downstream logic can react
# without reparsing argv.
parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                SHOW_HELP=true
                shift
                ;;
            -v|--version)
                SHOW_VERSION=true
                shift
                ;;
            -q|--quiet)
                QUIET_MODE=true
                shift
                ;;
            --verbose)
                VERBOSE_MODE=true
                shift
                ;;
            -d|--debug)
                ENABLE_DEBUG=true
                shift
                ;;
            -f|--force-update)
                FORCE_UPDATE=true
                shift
                ;;
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --rollback)
                ROLLBACK=true
                shift
                ;;
            --reset-state)
                RESET_STATE=true
                shift
                ;;
            --skip-health-check)
                SKIP_HEALTH_CHECK=true
                shift
                ;;
            --validate-state)
                VALIDATE_STATE=true
                shift
                ;;
            --force-resume)
                FORCE_RESUME=true
                shift
                ;;
            --repair-state)
                REPAIR_STATE=true
                shift
                ;;
            --test-rollback)
                TEST_ROLLBACK=true
                shift
                ;;
            --skip-switch)
                AUTO_APPLY_SYSTEM_CONFIGURATION=false
                AUTO_APPLY_HOME_CONFIGURATION=false
                shift
                ;;
            --skip-system-switch)
                AUTO_APPLY_SYSTEM_CONFIGURATION=false
                shift
                ;;
            --skip-home-switch)
                AUTO_APPLY_HOME_CONFIGURATION=false
                shift
                ;;
            --prefix)
                if [[ -z "${2:-}" ]] || [[ "$2" =~ ^- ]]; then
                    echo "ERROR: --prefix requires a path" >&2
                    exit 1
                fi
                DOTFILES_ROOT_OVERRIDE="$2"
                export DOTFILES_ROOT_OVERRIDE
                shift 2
                ;;
            --prompt-switch)
                PROMPT_BEFORE_SYSTEM_SWITCH=true
                PROMPT_BEFORE_HOME_SWITCH=true
                shift
                ;;
            --prompt-system-switch)
                PROMPT_BEFORE_SYSTEM_SWITCH=true
                shift
                ;;
            --prompt-home-switch)
                PROMPT_BEFORE_HOME_SWITCH=true
                shift
                ;;
            --enable-zswap)
                ZSWAP_CONFIGURATION_OVERRIDE_REQUEST="enable"
                shift
                ;;
            --disable-zswap)
                ZSWAP_CONFIGURATION_OVERRIDE_REQUEST="disable"
                shift
                ;;
            --zswap-auto)
                ZSWAP_CONFIGURATION_OVERRIDE_REQUEST="auto"
                shift
                ;;
            --disable-early-kms)
                EARLY_KMS_POLICY_OVERRIDE_REQUEST="off"
                shift
                ;;
            --early-kms-auto)
                EARLY_KMS_POLICY_OVERRIDE_REQUEST="auto"
                shift
                ;;
            --force-early-kms)
                EARLY_KMS_POLICY_OVERRIDE_REQUEST="force"
                shift
                ;;
            --skip-phase)
                if [[ -z "${2:-}" ]] || [[ "$2" =~ ^- ]]; then
                    echo "ERROR: --skip-phase requires a phase number" >&2
                    exit 1
                fi
                SKIP_PHASES+=("$2")
                shift 2
                ;;
            --start-from-phase)
                if [[ -z "${2:-}" ]] || [[ "$2" =~ ^- ]]; then
                    echo "ERROR: --start-from-phase requires a phase number" >&2
                    exit 1
                fi
                START_FROM_PHASE="$2"
                shift 2
                ;;
            --restart-phase)
                if [[ -z "${2:-}" ]] || [[ "$2" =~ ^- ]]; then
                    echo "ERROR: --restart-phase requires a phase number" >&2
                    exit 1
                fi
                RESTART_PHASE="$2"
                START_FROM_PHASE="$2"
                shift 2
                ;;
            --test-phase)
                if [[ -z "${2:-}" ]] || [[ "$2" =~ ^- ]]; then
                    echo "ERROR: --test-phase requires a phase number" >&2
                    exit 1
                fi
                TEST_PHASE="$2"
                shift 2
                ;;
            --list-phases)
                LIST_PHASES=true
                shift
                ;;
            --show-phase-info)
                if [[ -z "${2:-}" ]] || [[ "$2" =~ ^- ]]; then
                    echo "ERROR: --show-phase-info requires a phase number" >&2
                    exit 1
                fi
                SHOW_PHASE_INFO_NUM="$2"
                shift 2
                ;;
            --resume)
                RESUME=true
                shift
                ;;
            --restart-failed)
                RESTART_FAILED=true
                shift
                ;;
            --restart-from-safe-point)
                RESTART_FROM_SAFE_POINT=true
                shift
                ;;
            --flatpak-reinstall)
                FLATPAK_REINSTALL_REQUEST=true
                shift
                ;;
            --force-hf-download)
                FORCE_HF_DOWNLOAD=true
                shift
                ;;
            --update-flake-inputs)
                AUTO_UPDATE_FLAKE_INPUTS=true
                shift
                ;;
            --flake-only)
                FLAKE_ONLY_MODE=true
                shift
                ;;
            --flake-first)
                FLAKE_FIRST_MODE=true
                LEGACY_PHASES_MODE=false
                shift
                ;;
            --legacy-phases)
                FLAKE_FIRST_MODE=false
                LEGACY_PHASES_MODE=true
                shift
                ;;
            --flake-first-profile)
                if [[ -z "${2:-}" ]] || [[ "$2" =~ ^- ]]; then
                    echo "ERROR: --flake-first-profile requires ai-dev|gaming|minimal" >&2
                    exit 1
                fi
                FLAKE_FIRST_PROFILE="$2"
                FLAKE_FIRST_PROFILE_EXPLICIT=true
                shift 2
                ;;
            --flake-first-target)
                if [[ -z "${2:-}" ]] || [[ "$2" =~ ^- ]]; then
                    echo "ERROR: --flake-first-target requires a target name" >&2
                    exit 1
                fi
                FLAKE_FIRST_TARGET="$2"
                shift 2
                ;;
            --flake-first-deploy-mode)
                if [[ -z "${2:-}" ]] || [[ "$2" =~ ^- ]]; then
                    echo "ERROR: --flake-first-deploy-mode requires switch|boot|build" >&2
                    exit 1
                fi
                case "${2,,}" in
                    switch|boot|build)
                        FLAKE_FIRST_DEPLOY_MODE="${2,,}"
                        ;;
                    *)
                        echo "ERROR: Invalid --flake-first-deploy-mode '$2' (expected switch|boot|build)" >&2
                        exit 1
                        ;;
                esac
                shift 2
                ;;
            --restore-flake-lock)
                RESTORE_KNOWN_GOOD_FLAKE_LOCK=true
                shift
                ;;
            --skip-roadmap-verification)
                SKIP_ROADMAP_VERIFICATION=true
                shift
                ;;
            --with-ai-prep)
                RUN_AI_PREP=true
                shift
                ;;
            --with-ai-model)
                RUN_AI_MODEL=true
                shift
                ;;
            --without-ai-model)
                RUN_AI_MODEL=false
                FLAKE_FIRST_AI_STACK_EXPLICIT=true
                shift
                ;;
            --flake-first-ai-stack)
                if [[ -z "${2:-}" ]] || [[ "$2" =~ ^- ]]; then
                    echo "ERROR: --flake-first-ai-stack requires on|off" >&2
                    exit 1
                fi
                case "${2,,}" in
                    on|true|yes|y|1)
                        RUN_AI_MODEL=true
                        FLAKE_FIRST_AI_STACK_EXPLICIT=true
                        ;;
                    off|false|no|n|0)
                        RUN_AI_MODEL=false
                        FLAKE_FIRST_AI_STACK_EXPLICIT=true
                        ;;
                    *)
                        echo "ERROR: Invalid --flake-first-ai-stack '$2' (expected on|off)" >&2
                        exit 1
                        ;;
                esac
                shift 2
                ;;
            --flake-first-model-profile)
                if [[ -z "${2:-}" ]] || [[ "$2" =~ ^- ]]; then
                    echo "ERROR: --flake-first-model-profile requires auto|small|medium|large" >&2
                    exit 1
                fi
                case "${2,,}" in
                    auto|small|medium|large)
                        FLAKE_FIRST_MODEL_PROFILE="${2,,}"
                        ;;
                    *)
                        echo "ERROR: Invalid --flake-first-model-profile '$2' (expected auto|small|medium|large)" >&2
                        exit 1
                        ;;
                esac
                shift 2
                ;;
            --with-ai-stack)
                print_warning "Flag --with-ai-stack is deprecated; K3s + Portainer + K8s AI stack is always enabled."
                RUN_K8S_STACK=true
                shift
                ;;
            --with-k8s-stack)
                print_warning "Flag --with-k8s-stack is deprecated; K3s + Portainer + K8s AI stack is always enabled."
                shift
                ;;
            --with-k8s-e2e)
                RUN_K8S_E2E=true
                shift
                ;;
            --without-k8s-e2e)
                RUN_K8S_E2E=false
                shift
                ;;
            *)
                echo "ERROR: Unknown option: $1" >&2
                echo "Run with --help for usage information" >&2
                exit 1
                ;;
        esac
    done
}

# Entry-point guardrail: require running as a normal user so generated files
# stay user-owned and only privileged sub-steps use sudo.
assert_non_root_entrypoint() {
    if [[ "${EUID:-$(id -u)}" -eq 0 && "${ALLOW_ROOT_DEPLOY:-false}" != "true" ]]; then
        echo "ERROR: Do not run nixos-quick-deploy.sh as root/sudo." >&2
        echo "Run as your normal user; the script escalates only privileged steps." >&2
        echo "Override only if required: ALLOW_ROOT_DEPLOY=true ./nixos-quick-deploy.sh ..." >&2
        exit 1
    fi
}

# ============================================================================
# PHASE INFORMATION
# ============================================================================

# Render a table describing the eight phases. This is used by `--list-phases`
# and piggybacks on get_phase_name/get_phase_description helpers above.
list_phases() {
    echo ""
    echo "============================================"
    echo "  NixOS Quick Deploy - Phase Overview"
    echo "============================================"
    echo ""

    # Load libraries minimally to get state
    source "$LIB_DIR/colors.sh" 2>/dev/null || true
    source "$CONFIG_DIR/variables.sh" 2>/dev/null || true

    for phase_num in {1..9}; do
        local phase_name=$(get_phase_name "$phase_num")
        local phase_desc=$(get_phase_description "$phase_num")
        local status="PENDING"

        # Check if state file exists and get status
        if [[ -f "${STATE_FILE:-}" ]]; then
            if jq -e --arg step "phase-$(printf '%02d' $phase_num)" '.completed_steps[] | select(.step == $step)' "$STATE_FILE" &>/dev/null; then
                status="COMPLETED"
            fi
        fi

        printf "Phase %2d: %-30s [%s]\n" "$phase_num" "$phase_name" "$status"
        printf "          %s\n\n" "$phase_desc"
    done

    echo "============================================"
    echo "Optional extensions:"
    echo "  • AI-Optimizer preparation (enable with --with-ai-prep)"
    echo "  • AI model deployment (enabled by default, disable with --without-ai-model)"
    echo ""
}

# Detailed view for `--show-phase-info`. Surfaces descriptions and dependency
# chains to make troubleshooting simpler when only a subset of phases run.
show_phase_info() {
    local phase_num="$1"

    if [[ ! "$phase_num" =~ ^[0-9]+$ ]] || [[ "$phase_num" -lt 1 ]] || [[ "$phase_num" -gt 9 ]]; then
        echo "ERROR: Invalid phase number. Must be 1-9" >&2
        exit 1
    fi

    local phase_name=$(get_phase_name "$phase_num")
    local phase_desc=$(get_phase_description "$phase_num")
    local phase_deps=$(get_phase_dependencies "$phase_num")
    local phase_script="$PHASES_DIR/phase-$(printf '%02d' $phase_num)-$phase_name.sh"

    echo ""
    echo "============================================"
    echo "  Phase $phase_num: $phase_name"
    echo "============================================"
    echo ""
    echo "Description:"
    echo "  $phase_desc"
    echo ""
    echo "Script Location:"
    echo "  $phase_script"
    echo ""

    if [[ -n "$phase_deps" ]]; then
        echo "Dependencies:"
        echo "  Requires phases: $phase_deps"
    else
        echo "Dependencies:"
        echo "  None (entry point phase)"
    fi
    echo ""

    # Check if phase is safe restart point
    if [[ " ${SAFE_RESTART_PHASES[@]} " =~ " ${phase_num} " ]]; then
        echo "Safe Restart Point: YES"
    else
        echo "Safe Restart Point: NO (requires dependency validation)"
    fi
    echo ""

    # Check current status
    source "$CONFIG_DIR/variables.sh" 2>/dev/null || true
    if [[ -f "${STATE_FILE:-}" ]]; then
        if jq -e --arg step "phase-$(printf '%02d' $phase_num)" '.completed_steps[] | select(.step == $step)' "$STATE_FILE" &>/dev/null; then
            echo "Current Status: COMPLETED"
        else
            echo "Current Status: PENDING"
        fi
    else
        echo "Current Status: PENDING (no state file)"
    fi
    echo ""
    echo "============================================"
    echo ""
}

# ============================================================================
# PHASE CONTROL
# ============================================================================

# Utility: determine whether the operator asked to skip a phase (via repeated
# `--skip-phase` flags). `SKIP_PHASES` is populated inside parse_arguments.
should_skip_phase() {
    local phase_num="$1"
    for skip_phase in "${SKIP_PHASES[@]}"; do
        if [[ "$skip_phase" == "$phase_num" ]]; then
            return 0
        fi
    done
    return 1
}

# When resuming after an interruption, walk the completion log at $STATE_FILE
# (defined in config/variables.sh:101) to find the next incomplete phase.
get_resume_phase() {
    # If restart-from-safe-point is set, find last safe point
    if [[ "$RESTART_FROM_SAFE_POINT" == true ]]; then
        local last_safe_phase=1
        if [[ -f "$STATE_FILE" ]]; then
            for safe_phase in "${SAFE_RESTART_PHASES[@]}"; do
                if jq -e --arg step "phase-$(printf '%02d' $safe_phase)" '.completed_steps[] | select(.step == $step)' "$STATE_FILE" &>/dev/null; then
                    last_safe_phase=$safe_phase
                fi
            done
        fi
        echo "$last_safe_phase"
        return
    fi

    # Otherwise, find the next incomplete phase
    if [[ ! -f "$STATE_FILE" ]]; then
        echo "1"
        return
    fi

    for phase_num in {1..8}; do
        if ! jq -e --arg step "phase-$(printf '%02d' $phase_num)" '.completed_steps[] | select(.step == $step)' "$STATE_FILE" &>/dev/null; then
            echo "$phase_num"
            return
        fi
    done

    # All phases complete
    echo "1"
}

# ============================================================================
# CONFIG TEMPLATE DIGEST (AUTO REGEN)
# ============================================================================
compute_config_templates_digest() {
    if ! command -v python3 >/dev/null 2>&1; then
        return 1
    fi
    python3 - "$SCRIPT_DIR" <<'PY'
import hashlib
import os
import sys

root = sys.argv[1]
targets = [
    os.path.join(root, "templates"),
    os.path.join(root, "config"),
    os.path.join(root, "lib", "config.sh"),
]
files = []
for target in targets:
    if os.path.isdir(target):
        for dirpath, _, filenames in os.walk(target):
            for name in filenames:
                files.append(os.path.join(dirpath, name))
    elif os.path.isfile(target):
        files.append(target)

files = sorted(set(files))
digest = hashlib.sha256()
for path in files:
    digest.update(path.encode("utf-8"))
    with open(path, "rb") as handle:
        digest.update(handle.read())
print(digest.hexdigest())
PY
}

maybe_reset_config_phases_on_template_change() {
    if [[ "$AUTO_REGEN_CONFIG_ON_TEMPLATE_CHANGE" != "true" ]]; then
        return 0
    fi

    local current_digest
    current_digest=$(compute_config_templates_digest 2>/dev/null || true)
    if [[ -z "$current_digest" ]]; then
        log WARNING "Unable to compute template digest; skipping auto-regeneration."
        return 0
    fi

    local stored_digest=""
    if declare -F state_get_metadata >/dev/null 2>&1; then
        stored_digest=$(state_get_metadata "config_templates_digest" 2>/dev/null || true)
    fi

    if [[ -n "$stored_digest" && "$stored_digest" == "$current_digest" ]]; then
        return 0
    fi

    if [[ -n "$stored_digest" ]]; then
        print_warning "Template changes detected; re-running phases 3+."
    else
        print_info "No template digest recorded; ensuring phases 3+ run."
    fi

    if declare -F state_remove_phase_steps_from >/dev/null 2>&1; then
        state_remove_phase_steps_from 3 || true
    fi
    if declare -F state_remove_steps >/dev/null 2>&1; then
        state_remove_steps \
            generate_validate_configs \
            pre_deployment_validation \
            deploy_configurations \
            install_tools_services \
            post_install_validation \
            finalization_and_report || true
    fi
}

# Cross-check the prerequisite list for a phase. Ensures the JSON state file
# (managed via lib/state-management.sh) records completion entries for each
# dependency before execution proceeds.
validate_phase_dependencies() {
    local phase_num="$1"
    local deps=$(get_phase_dependencies "$phase_num")

    if [[ -n "${TEST_PHASE:-}" && "$phase_num" == "$TEST_PHASE" ]]; then
        return 0
    fi

    if [[ -z "$deps" ]]; then
        return 0
    fi

    if [[ ! -f "$STATE_FILE" ]]; then
        log ERROR "Cannot validate dependencies: state file not found"
        return 1
    fi

    local missing_deps=()
    IFS=',' read -ra DEP_ARRAY <<< "$deps"
    for dep in "${DEP_ARRAY[@]}"; do
        if declare -F phase_dependency_satisfied >/dev/null 2>&1; then
            if ! phase_dependency_satisfied "$dep"; then
                missing_deps+=("$dep")
            fi
        else
            local step_id="phase-$(printf '%02d' "$dep")"
            if declare -F is_step_complete >/dev/null 2>&1; then
                if ! is_step_complete "$step_id"; then
                    missing_deps+=("$dep")
                fi
            else
                if ! jq -e --arg step "$step_id" '.completed_steps[] | select(.step == $step)' "$STATE_FILE" &>/dev/null; then
                    missing_deps+=("$dep")
                fi
            fi
        fi
    done

    if [[ ${#missing_deps[@]} -gt 0 ]]; then
        log ERROR "Phase $phase_num has missing dependencies: ${missing_deps[*]}"
        print_error "Cannot execute phase $phase_num: missing dependencies ${missing_deps[*]}"
        if [[ "${DRY_RUN:-false}" == true ]]; then
            print_warning "DRY RUN: Ignoring missing dependencies for phase $phase_num"
            return 0
        fi
        return 1
    fi

    return 0
}

state_completed_steps_count() {
    if [[ ! -f "$STATE_FILE" ]]; then
        echo "0"
        return 0
    fi
    if command -v jq >/dev/null 2>&1; then
        jq -r '.completed_steps | length' "$STATE_FILE" 2>/dev/null || echo "0"
        return 0
    fi
    if command -v python3 >/dev/null 2>&1; then
        python3 - "$STATE_FILE" <<'PY' 2>/dev/null || echo "0"
import json
import sys
path = sys.argv[1]
with open(path, "r", encoding="utf-8") as handle:
    data = json.load(handle)
print(len(data.get("completed_steps", [])))
PY
        return 0
    fi
    echo "0"
}

state_last_completed_at() {
    if [[ ! -f "$STATE_FILE" ]]; then
        return 1
    fi
    if command -v jq >/dev/null 2>&1; then
        jq -r '.completed_steps | sort_by(.completed_at) | last(.[]?) | .completed_at // empty' "$STATE_FILE" 2>/dev/null
        return 0
    fi
    if command -v python3 >/dev/null 2>&1; then
        python3 - "$STATE_FILE" <<'PY' 2>/dev/null || true
import json
import sys
path = sys.argv[1]
with open(path, "r", encoding="utf-8") as handle:
    data = json.load(handle)
steps = data.get("completed_steps", [])
steps = [s for s in steps if isinstance(s, dict) and s.get("completed_at")]
if not steps:
    sys.exit(0)
steps.sort(key=lambda s: s.get("completed_at"))
print(steps[-1].get("completed_at", ""))
PY
        return 0
    fi
    return 1
}

state_remove_phase_steps_from() {
    local min_phase="$1"
    if [[ -z "$min_phase" ]]; then
        return 1
    fi
    if [[ ! -f "$STATE_FILE" ]]; then
        return 1
    fi
    if command -v jq >/dev/null 2>&1; then
        if jq --argjson min "$min_phase" '
            .completed_steps |= map(
                if (.step | type == "string") and (.step | test("^phase-[0-9]{2}$")) then
                    ( (.step | split("-")[1] | tonumber) < $min )
                else
                    true
                end
            )
        ' "$STATE_FILE" > "${STATE_FILE}.tmp" 2>/dev/null && mv "${STATE_FILE}.tmp" "$STATE_FILE" 2>/dev/null; then
            return 0
        fi
        rm -f "${STATE_FILE}.tmp" 2>/dev/null || true
        return 1
    fi
    if command -v python3 >/dev/null 2>&1; then
        if python3 - "$STATE_FILE" "$min_phase" <<'PY' 2>/dev/null; then
import json
import re
import sys

path = sys.argv[1]
min_phase = int(sys.argv[2])
with open(path, "r", encoding="utf-8") as handle:
    data = json.load(handle)
steps = data.get("completed_steps", [])
filtered = []
for item in steps:
    step = item.get("step") if isinstance(item, dict) else None
    if isinstance(step, str) and re.match(r"^phase-[0-9]{2}$", step):
        phase_num = int(step.split("-")[1])
        if phase_num >= min_phase:
            continue
    filtered.append(item)
data["completed_steps"] = filtered
with open(path, "w", encoding="utf-8") as handle:
    json.dump(data, handle, indent=2)
PY
            return 0
        fi
        return 1
    fi
    return 1
}

bootstrap_resume_validation_tools() {
    # Resume validation can use jq/python3; install them early when available.
    local strict="${1:-false}"
    local missing=0
    local previous_imperative_flag="${IMPERATIVE_INSTALLS_ALLOWED:-false}"

    # setup_environment runs before phase-01, so imperative installs are not yet
    # enabled by default. Temporarily allow preflight bootstrap installs here.
    export IMPERATIVE_INSTALLS_ALLOWED=true

    if ! command -v jq >/dev/null 2>&1; then
        missing=1
        if declare -F ensure_prerequisite_installed >/dev/null 2>&1; then
            ensure_prerequisite_installed "jq" "nixpkgs#jq" "jq (JSON parser)" || true
        fi
    fi

    if ! command -v python3 >/dev/null 2>&1; then
        missing=1
        if declare -F ensure_prerequisite_installed >/dev/null 2>&1; then
            ensure_prerequisite_installed "python3" "nixpkgs#python3" "python3 (Python interpreter)" || true
        fi
    fi

    export IMPERATIVE_INSTALLS_ALLOWED="$previous_imperative_flag"

    if [[ "$strict" == "true" ]] && ! command -v jq >/dev/null 2>&1 && ! command -v python3 >/dev/null 2>&1; then
        print_error "State validation requires jq or python3. Install one of them and retry."
        return 1
    fi

    if [[ "$missing" == "1" ]] && ! command -v jq >/dev/null 2>&1 && ! command -v python3 >/dev/null 2>&1; then
        print_warning "Proceeding without jq/python3; resume state validation will be limited."
    fi

    return 0
}

validate_resume_state() {
    local strict="${1:-false}"
    local errors=0
    local min_reset_phase=0

    if [[ ! -f "$STATE_FILE" ]]; then
        print_info "State file not found; resume will start from phase 1."
        return 0
    fi

    if [[ "$FORCE_RESUME" == "true" ]]; then
        print_warning "FORCE_RESUME enabled; skipping state version validation."
    elif declare -F validate_state_version >/dev/null 2>&1; then
        if [[ "$strict" == "true" ]]; then
            if ! validate_state_version enforce; then
                print_error "State version mismatch; use --reset-state or rerun without --validate-state."
                return 1
            fi
        else
            validate_state_version check || true
        fi
    fi

    if ! command -v jq >/dev/null 2>&1 && ! command -v python3 >/dev/null 2>&1; then
        print_warning "State validation limited: jq/python3 unavailable."
        return 0
    fi

    local completed_count
    completed_count=$(state_completed_steps_count)
    if [[ "$completed_count" == "0" ]]; then
        print_info "State file has no completed steps; resume will start from phase 1."
        return 0
    fi

    local last_completed
    last_completed=$(state_last_completed_at || true)
    if [[ -n "$last_completed" ]]; then
        local last_epoch now_epoch
        last_epoch=$(date -d "$last_completed" +%s 2>/dev/null || echo "")
        now_epoch=$(date +%s 2>/dev/null || echo "")
        if [[ -n "$last_epoch" && -n "$now_epoch" ]]; then
            local age_sec=$((now_epoch - last_epoch))
            if (( age_sec > 86400 )); then
                print_warning "State file last updated more than 24h ago (${last_completed}); validate before resume."
            fi
        fi
    fi

    if is_step_complete "phase-03"; then
        local missing=()
        local hm_dir="${HM_CONFIG_DIR:-}"
        if [[ -z "$hm_dir" || ! -d "$hm_dir" ]]; then
            missing+=("HM_CONFIG_DIR")
        else
            [[ -f "$hm_dir/flake.nix" ]] || missing+=("flake.nix")
            [[ -f "$hm_dir/home.nix" ]] || missing+=("home.nix")
            [[ -f "$hm_dir/configuration.nix" ]] || missing+=("configuration.nix")
            [[ -f "$hm_dir/hardware-configuration.nix" ]] || missing+=("hardware-configuration.nix")
        fi
        if (( ${#missing[@]} > 0 )); then
            print_warning "State mismatch: phase 03 completed but config outputs missing (${missing[*]})."
            errors=$((errors + 1))
            min_reset_phase=3
        fi
    fi

    if is_step_complete "phase-05"; then
        local hm_link_dir="$HOME/.config/home-manager"
        if [[ ! -f "$hm_link_dir/flake.nix" || ! -f "$hm_link_dir/home.nix" ]]; then
            print_warning "State mismatch: phase 05 completed but home-manager links are missing under $hm_link_dir."
            errors=$((errors + 1))
            if (( min_reset_phase == 0 || min_reset_phase > 5 )); then
                min_reset_phase=5
            fi
        fi
    fi

    if (( errors > 0 )) && [[ "$REPAIR_STATE" == "true" && "$min_reset_phase" -gt 0 ]]; then
        print_warning "Repairing state: clearing completed phase entries from phase ${min_reset_phase} onward."
        if state_remove_phase_steps_from "$min_reset_phase"; then
            print_info "State repair complete. Resume will restart from phase ${min_reset_phase}."
        else
            print_error "State repair failed; unable to update ${STATE_FILE}."
            if [[ "$strict" == "true" ]]; then
                return 1
            fi
        fi
    fi

    if (( errors > 0 )) && [[ "$strict" == "true" ]]; then
        print_error "State validation failed (${errors} issue(s)). Run with --reset-state or repair state before resuming."
        return 1
    fi

    return 0
}

# Invoke a specific phase script from $PHASES_DIR. Handles dry-run logging,
# dependency validation, and completion tracking in one place.
execute_phase() {
    local phase_num="$1"
    local phase_name=$(get_phase_name "$phase_num")
    local phase_script="$PHASES_DIR/phase-$(printf '%02d' $phase_num)-$phase_name.sh"
    local phase_step="phase-$(printf '%02d' $phase_num)"
    local previous_log_component="${LOG_COMPONENT:-}"

    CURRENT_PHASE_NUM="$phase_num"
    CURRENT_PHASE_NAME="$phase_name"
    export CURRENT_PHASE_NUM CURRENT_PHASE_NAME
    LOG_COMPONENT="phase-${phase_num}-${phase_name}"
    export LOG_COMPONENT

    # Check if phase script exists
    if [[ ! -f "$phase_script" ]]; then
        log ERROR "Phase script not found: $phase_script"
        print_error "Phase $phase_num script not found"
        LOG_COMPONENT="$previous_log_component"
        export LOG_COMPONENT
        return 1
    fi

    # Check if already completed (skip if not restart)
    if [[ -z "$RESTART_PHASE" ]] && is_step_complete "$phase_step"; then
        log INFO "Phase $phase_num already completed (skipping)"
        print_info "Phase $phase_num: $phase_name [ALREADY COMPLETED]"
        LOG_COMPONENT="$previous_log_component"
        export LOG_COMPONENT
        return 0
    fi

    # Validate dependencies
    if ! validate_phase_dependencies "$phase_num"; then
        LOG_COMPONENT="$previous_log_component"
        export LOG_COMPONENT
        return 1
    fi

    # Execute phase with progress tracking
    local total_phases=8  # Total number of phases in deployment
    
    # Track phase start for duration calculation
    if declare -F track_phase_start >/dev/null 2>&1; then
        track_phase_start "$phase_num"
    fi
    
    # Calculate and display progress
    local progress_pct=$(( (phase_num * 100) / total_phases ))
    
    print_section "Phase $phase_num/$total_phases: $phase_name"
    print_info "Progress: $progress_pct% ($phase_num of $total_phases phases)"
    
    # Show overall progress with ETA if available
    if declare -F show_progress >/dev/null 2>&1; then
        show_progress "$phase_num"
    fi
    
    log INFO "Executing phase $phase_num/$total_phases: $phase_name"

    if [[ "$DRY_RUN" == true ]]; then
        print_info "[DRY RUN] Would execute: $phase_script"
        log INFO "[DRY RUN] Phase $phase_num skipped"
        
        # Enhanced dry-run: Show what would be done
        if declare -F dry_run_phase_validation >/dev/null 2>&1; then
            dry_run_phase_validation "$phase_num" "$phase_name" "$phase_script" || true
        fi
        LOG_COMPONENT="$previous_log_component"
        export LOG_COMPONENT
        return 0
    fi

    # Source and execute the phase script
    local phase_start_time
    phase_start_time=$(date +%s)
    
    if source "$phase_script"; then
        local phase_end_time
        phase_end_time=$(date +%s)
        local phase_duration=$((phase_end_time - phase_start_time))

        if ! run_inter_phase_health_check "$phase_num"; then
            log ERROR "Phase $phase_num failed health check"
            print_error "Phase $phase_num health check failed"
            LOG_COMPONENT="$previous_log_component"
            export LOG_COMPONENT
            return 1
        fi

        # Track phase completion
        if declare -F track_phase_complete >/dev/null 2>&1; then
            track_phase_complete "$phase_num"
        fi
        
        mark_step_complete "$phase_step"
        log INFO "Phase $phase_num completed successfully in ${phase_duration}s"
        print_success "Phase $phase_num completed (${phase_duration}s)"
        
        # Show cumulative progress
        local completed_pct=$(( ((phase_num) * 100) / total_phases ))
        log INFO "Overall progress: $completed_pct% complete"
        
        LOG_COMPONENT="$previous_log_component"
        export LOG_COMPONENT
        return 0
    else
        local exit_code=$?
        local phase_end_time
        phase_end_time=$(date +%s)
        local phase_duration=$((phase_end_time - phase_start_time))
        
        log ERROR "Phase $phase_num failed with exit code $exit_code after ${phase_duration}s"
        print_error "Phase $phase_num failed (exit code: $exit_code)"
        LOG_COMPONENT="$previous_log_component"
        export LOG_COMPONENT
        return $exit_code
    fi
}

run_optional_phase_script() {
    local script_path="$1"
    local function_name="$2"
    local label="$3"

    if [[ ! -f "$script_path" ]]; then
        print_warning "$label script not found at $script_path"
        return 1
    fi

    # shellcheck source=/dev/null
    if ! source "$script_path"; then
        print_error "Failed to load $label script ($script_path)"
        return 1
    fi

    if "$function_name"; then
        print_success "$label completed"
        echo ""
        return 0
    fi

    print_error "$label failed"
    return 1
}

# Interactive failure handler invoked whenever execute_phase returns non-zero.
# Provides retry/skip/rollback/exit prompts so operators can steer recovery.
handle_phase_failure() {
    local phase_num="$1"
    local phase_name=$(get_phase_name "$phase_num")

    echo ""
    print_error "Phase $phase_num ($phase_name) failed!"
    echo ""

    if [[ "$DRY_RUN" == true ]]; then
        log INFO "Dry run mode: continuing despite failure"
        return 0
    fi

    # Interactive failure handling (repeat until user resolves or exits)
    while true; do
        echo "What would you like to do?"
        echo "  1) Retry this phase (regenerate configs)"
        echo "  2) Skip and continue"
        echo "  3) Rollback"
        echo "  4) Exit"
        echo ""
        read -p "Choice [1-4]: " choice

        case "$choice" in
            1)
                log INFO "User chose to retry phase $phase_num"
                if [[ "$phase_num" -ge 3 ]]; then
                    print_section "Regenerating configurations before retry"
                    if declare -F ensure_user_settings_ready >/dev/null 2>&1; then
                        if ! ensure_user_settings_ready --noninteractive; then
                            print_error "Failed to confirm user settings for regeneration"
                            continue
                        fi
                    fi
                    if declare -F generate_nixos_system_config >/dev/null 2>&1; then
                        if ! generate_nixos_system_config; then
                            print_error "Failed to regenerate NixOS system configuration"
                            continue
                        fi
                    fi
                    if declare -F create_home_manager_config >/dev/null 2>&1; then
                        if ! create_home_manager_config; then
                            print_error "Failed to regenerate home-manager configuration"
                            continue
                        fi
                    fi
                    print_success "Configuration regeneration complete"
                fi
                if execute_phase "$phase_num"; then
                    return 0
                fi
                print_warning "Phase $phase_num still failing; choose next action"
                ;;
            2)
                log WARNING "User chose to skip phase $phase_num"
                print_warning "Skipping phase $phase_num"
                return 0
                ;;
            3)
                log INFO "User chose to rollback"
                ROLLBACK_IN_PROGRESS=true
                export ROLLBACK_IN_PROGRESS
                perform_rollback
                exit $?
                ;;
            4|*)
                log INFO "User chose to exit"
                AUTO_ROLLBACK_SUPPRESSED=true
                export AUTO_ROLLBACK_SUPPRESSED
                exit 1
                ;;
        esac
    done
}

# ============================================================================
# ROLLBACK
# ============================================================================

# Trigger a system rollback using the generation recorded in
# $ROLLBACK_INFO_FILE (defined in config/variables.sh:108 and populated during
# backup stages). Mirrors the manual `sudo nixos-rebuild switch --rollback`
# flow, but keeps messaging consistent.
perform_rollback() {
    log INFO "Performing rollback"
    print_section "Rolling back to previous state"

    if [[ ! -f "$ROLLBACK_INFO_FILE" ]]; then
        print_error "No rollback information found"
        log ERROR "Rollback info file not found: $ROLLBACK_INFO_FILE"
        return 1
    fi

    # Read rollback generation
    local rollback_gen=$(cat "$ROLLBACK_INFO_FILE" 2>/dev/null || echo "")
    if [[ -z "$rollback_gen" ]]; then
        print_error "Invalid rollback information"
        return 1
    fi

    print_info "Rolling back to generation: $rollback_gen"
    log INFO "Rolling back to generation: $rollback_gen"

    if [[ "$DRY_RUN" == true ]]; then
        print_info "[DRY RUN] Would execute: sudo nixos-rebuild switch --rollback"
        return 0
    fi

    if sudo nixos-rebuild switch --rollback; then
        print_success "Rollback completed successfully"
        log INFO "Rollback completed successfully"
        return 0
    else
        print_error "Rollback failed"
        log ERROR "Rollback failed"
        return 1
    fi
}

get_current_generation() {
    local gen_link
    gen_link=$(readlink /nix/var/nix/profiles/system 2>/dev/null || true)
    if [[ -n "$gen_link" ]]; then
        local gen
        gen=$(echo "$gen_link" | sed -n 's/.*system-\([0-9]\+\)-link/\1/p')
        if [[ -n "$gen" ]]; then
            echo "$gen"
            return 0
        fi
    fi

    if command -v nixos-rebuild >/dev/null 2>&1; then
        local gen
        gen=$(nixos-rebuild list-generations 2>/dev/null | awk '/current/ {print $1; exit}')
        if [[ -n "$gen" ]]; then
            echo "$gen"
            return 0
        fi
    fi

    return 1
}

run_rollback_health_check() {
    local label="$1"
    if [[ "${ROLLBACK_TEST_HEALTH_CHECK:-true}" != true ]]; then
        print_info "Skipping rollback health check ($label) (ROLLBACK_TEST_HEALTH_CHECK=false)"
        return 0
    fi

    local health_script="$SCRIPT_DIR/scripts/system-health-check.sh"
    if [[ -x "$health_script" ]]; then
        print_info "Running rollback health check ($label) via $health_script"
        if "$health_script" --detailed; then
            print_success "Rollback health check passed ($label)"
            return 0
        fi
        print_warning "Rollback health check reported issues ($label)"
        return 1
    fi

    if declare -F run_system_health_check_stage >/dev/null 2>&1; then
        print_info "Running rollback health check ($label) via run_system_health_check_stage"
        if run_system_health_check_stage; then
            print_success "Rollback health check passed ($label)"
            return 0
        fi
        print_warning "Rollback health check reported issues ($label)"
        return 1
    fi

    print_warning "Rollback health check skipped ($label) - no health checker found"
    return 0
}

test_rollback_flow() {
    print_section "Rollback Validation"

    if [[ "$DRY_RUN" == true ]]; then
        print_info "[DRY RUN] Would execute rollback validation"
        return 0
    fi

    if [[ ! -f "$ROLLBACK_INFO_FILE" ]]; then
        print_error "Rollback validation failed: rollback info file not found"
        return 1
    fi

    local current_gen
    current_gen=$(get_current_generation || true)
    if [[ -z "$current_gen" ]]; then
        print_error "Rollback validation failed: unable to determine current generation"
        return 1
    fi

    if [[ "${AUTO_CONFIRM_ROLLBACK_TEST:-false}" != true ]]; then
        echo ""
        echo "Rollback validation will switch system generations twice."
        read -p "Continue? [y/N]: " confirm
        if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
            print_warning "Rollback validation cancelled"
            return 1
        fi
    fi

    print_info "Current generation: $current_gen"
    print_info "Rolling back to previous generation..."
    if ! sudo nixos-rebuild switch --rollback; then
        print_error "Rollback validation failed: rollback switch failed"
        return 1
    fi

    local rollback_gen
    rollback_gen=$(get_current_generation || true)
    if [[ -z "$rollback_gen" || "$rollback_gen" == "$current_gen" ]]; then
        print_error "Rollback validation failed: generation did not change after rollback"
        return 1
    fi

    run_rollback_health_check "after rollback" || true

    print_info "Restoring original generation..."
    if ! sudo nixos-rebuild switch --rollback; then
        print_error "Rollback validation failed: restore switch failed"
        return 1
    fi

    local restored_gen
    restored_gen=$(get_current_generation || true)
    if [[ -z "$restored_gen" || "$restored_gen" != "$current_gen" ]]; then
        print_error "Rollback validation failed: did not return to original generation"
        return 1
    fi

    run_rollback_health_check "after restore" || true

    print_success "Rollback validation completed (returned to generation $current_gen)"
    return 0
}

# ============================================================================
# MAIN INITIALIZATION
# ============================================================================

# Cosmetic banner shown before deployment details. Highlights DRY RUN and DEBUG
# modes when relevant so logs are unambiguous.
print_header() {
    echo ""
    echo "============================================"
    echo "  NixOS Quick Deploy v$SCRIPT_VERSION"
    echo "  9-Phase Modular Deployment"
    echo "============================================"
    echo ""

    if [[ "$DRY_RUN" == true ]]; then
        echo "  MODE: DRY RUN (no changes will be made)"
        echo ""
    fi

    if [[ "$ENABLE_DEBUG" == true ]]; then
        echo "  DEBUG: Enabled"
        echo ""
    fi
}

# Guarantee that flakes + nix-command experimental features are enabled for the
# duration of the run, while preserving any additional user-provided NIX_CONFIG
# content.
ensure_nix_experimental_features_env() {
    # Ensure flakes and nix-command are enabled without clobbering user settings.
    local required_features="nix-command flakes"
    local addition="experimental-features = ${required_features}"
    local newline=$'\n'
    local current_config="${NIX_CONFIG:-}"

    if [[ -z "$current_config" ]]; then
        export NIX_CONFIG="$addition"
        log INFO "NIX_CONFIG initialized with experimental features: $required_features"
        return
    fi

    if printf '%s\n' "$current_config" | grep -q '^[[:space:]]*experimental-features[[:space:]]*='; then
        local existing_line
        existing_line=$(printf '%s\n' "$current_config" | grep '^[[:space:]]*experimental-features[[:space:]]*=' | head -n1)
        local features
        features=$(printf '%s' "${existing_line#*=}" | xargs)

        local feature
        local updated_features="$features"
        for feature in nix-command flakes; do
            if [[ " $updated_features " != *" $feature "* ]]; then
                updated_features+=" $feature"
            fi
        done
        updated_features=$(printf '%s' "$updated_features" | xargs)

        if [[ "$features" != "$updated_features" ]]; then
            local new_line="experimental-features = $updated_features"
            local updated_config
            updated_config=$(printf '%s\n' "$current_config" | sed "0,/^[[:space:]]*experimental-features[[:space:]]*=.*/s//${new_line}/")
            export NIX_CONFIG="$updated_config"
            log INFO "Updated NIX_CONFIG experimental features: $updated_features"
        else
            export NIX_CONFIG="$current_config"
            log DEBUG "NIX_CONFIG already contains required experimental features"
        fi
    else
        export NIX_CONFIG="${current_config}${newline}${addition}"
        log INFO "Appended experimental features to NIX_CONFIG: $required_features"
    fi
}

# ============================================================================
# Sudo Keepalive
# ============================================================================

# Deployment-specific exit cleanup (wraps cleanup_on_exit from lib/error-handling.sh)
# This function is set as the EXIT trap once and handles all deployment resources,
# avoiding the previous bug where successive trap registrations overwrote each other.
_deploy_exit_cleanup() {
    # Kill sudo keepalive background process
    if [[ -n "${SUDO_KEEPALIVE_PID:-}" ]]; then
        kill "$SUDO_KEEPALIVE_PID" 2>/dev/null || true
    fi
    # Release deploy lock (flock-based)
    if [[ -n "${_DEPLOY_LOCK_FD:-}" ]]; then
        flock -u "$_DEPLOY_LOCK_FD" 2>/dev/null || true
    fi
    # Remove lock file
    if [[ -n "${_DEPLOY_LOCK_FILE:-}" ]]; then
        rm -f "$_DEPLOY_LOCK_FILE" 2>/dev/null || true
    fi
    # Chain to original cleanup (state save, temp files, etc.)
    if declare -F cleanup_on_exit >/dev/null 2>&1; then
        cleanup_on_exit
    fi
}

start_sudo_keepalive() {
    if [[ ${EUID:-0} -eq 0 ]]; then
        return 0
    fi

    if ! command -v sudo >/dev/null 2>&1; then
        return 0
    fi

    if sudo -v; then
        (
            while true; do
                sudo -n -v >/dev/null 2>&1 || exit 0
                sleep 60
            done
        ) &
        SUDO_KEEPALIVE_PID=$!
        # Note: SUDO_KEEPALIVE_PID is cleaned up by _deploy_exit_cleanup (no separate trap needed)
    else
        print_warning "sudo authentication failed; you may be prompted again later."
    fi
}

# ============================================================================
# AI Stack Credentials + Host Swap Limits
# ============================================================================

# suggest_ai_stack_llama_defaults: pick legacy-parity llama.cpp defaults from
# detected GPU VRAM / host RAM for first-run AI stack configuration.
suggest_ai_stack_llama_defaults() {
    local gpu_vram=0
    local ram_gb=0

    if command -v nvidia-smi >/dev/null 2>&1; then
        gpu_vram=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | head -1 | awk '{print int($1/1024)}' || echo 0)
    elif command -v rocm-smi >/dev/null 2>&1; then
        gpu_vram=$(rocm-smi --showmeminfo vram --csv 2>/dev/null | tail -1 | awk -F',' '{print int($2/1024)}' || echo 0)
    fi

    if [[ -r /proc/meminfo ]]; then
        ram_gb=$(awk '/MemTotal:/ {printf "%d", $2/1024/1024}' /proc/meminfo 2>/dev/null || echo 0)
    fi

    local model_id="unsloth/Qwen3-4B-Instruct-2507-GGUF"
    local model_file="Qwen3-4B-Instruct-2507-Q4_K_M.gguf"

    if [[ "$gpu_vram" =~ ^[0-9]+$ ]] && (( gpu_vram >= 24 )); then
        model_id="Qwen/Qwen2.5-Coder-14B-Instruct"
        model_file="qwen2.5-coder-14b-instruct-q4_k_m.gguf"
    elif [[ "$gpu_vram" =~ ^[0-9]+$ ]] && (( gpu_vram >= 16 )); then
        model_id="Qwen/Qwen2.5-Coder-7B-Instruct"
        model_file="qwen2.5-coder-7b-instruct-q4_k_m.gguf"
    elif [[ "$ram_gb" =~ ^[0-9]+$ ]] && (( ram_gb >= 32 )); then
        model_id="Qwen/Qwen2.5-Coder-7B-Instruct"
        model_file="qwen2.5-coder-7b-instruct-q4_k_m.gguf"
    fi

    printf '%s|%s\n' "$model_id" "$model_file"
}

# prewarm_ai_stack_embeddings_cache: mirror legacy phase behavior by attempting
# an embeddings model cache warm-up before first runtime requests.
prewarm_ai_stack_embeddings_cache() {
    local embeddings_script="$SCRIPT_DIR/scripts/download-embeddings-model.sh"
    if [[ ! -x "$embeddings_script" ]]; then
        return 0
    fi

    local env_file="${AI_STACK_ENV_FILE:-${AI_STACK_CONFIG_DIR:-${PRIMARY_HOME:-$HOME}/.config/nixos-ai-stack}/.env}"
    local embedding_model="sentence-transformers/all-MiniLM-L6-v2"
    local ai_stack_data="${AI_STACK_DATA:-$HOME/.local/share/nixos-ai-stack}"

    if [[ -f "$env_file" ]]; then
        local val
        val=$(awk -F= '/^EMBEDDING_MODEL=/{sub("^[^=]*=", "", $0); print $0; exit}' "$env_file" 2>/dev/null || true)
        [[ -n "$val" ]] && embedding_model="$val"
        val=$(awk -F= '/^AI_STACK_DATA=/{sub("^[^=]*=", "", $0); print $0; exit}' "$env_file" 2>/dev/null || true)
        [[ -n "$val" ]] && ai_stack_data="$val"
    fi

    local embeddings_cache_dir="${ai_stack_data}/embeddings/cache"
    mkdir -p "$embeddings_cache_dir"

    print_info "Pre-warming embeddings cache (${embedding_model})"
    EMBEDDING_MODEL="$embedding_model" \
    EMBEDDINGS_CACHE_DIR="$embeddings_cache_dir" \
    "$embeddings_script" >/dev/null 2>&1 || print_warning "Embeddings cache prewarm failed; runtime download fallback remains available."
}

# wait_for_ai_stack_readiness: best-effort post-switch readiness check so
# flake-first keeps legacy parity observability without imperative apply steps.
wait_for_ai_stack_readiness() {
    if [[ "$RUN_AI_MODEL" != true ]]; then
        return 0
    fi

    if ! command -v kubectl >/dev/null 2>&1; then
        return 0
    fi

    if ! kubectl --request-timeout=15s cluster-info >/dev/null 2>&1; then
        print_warning "Kubernetes API not reachable yet; skipping AI stack readiness wait."
        return 0
    fi

    local namespace="${AI_STACK_NAMESPACE:-ai-stack}"
    print_info "Checking AI stack readiness in namespace '${namespace}'"

    kubectl --request-timeout=30s -n "$namespace" get deploy >/dev/null 2>&1 || return 0
    kubectl --request-timeout=120s -n "$namespace" rollout status deploy/aidb >/dev/null 2>&1 || \
        print_warning "AIDB deployment is not ready yet (non-fatal; reconciliation will continue)."
    kubectl --request-timeout=120s -n "$namespace" rollout status deploy/qdrant >/dev/null 2>&1 || \
        print_warning "Qdrant deployment is not ready yet (non-fatal; reconciliation will continue)."
}

ensure_ai_stack_env() {
    if [[ "$RUN_AI_MODEL" != true && "${LOCAL_AI_STACK_ENABLED:-false}" != "true" ]]; then
        return 0
    fi
    local interactive=true
    if [[ ! -t 0 ]]; then
        interactive=false
    fi

    read_env_value() {
        local key="$1"
        local file="$2"
        awk -F= -v target="$key" '
            $0 ~ "^[[:space:]]*"target"=" {
                sub("^[^=]*=", "", $0);
                print $0;
                exit;
            }
        ' "$file"
    }

    set_env_value() {
        local key="$1"
        local value="$2"
        local file="$3"
        local tmp_file
        tmp_file=$(mktemp)

        awk -v target="$key" -v replacement="$value" '
            BEGIN { updated = 0 }
            $0 ~ "^[[:space:]]*" target "=" {
                print target "=" replacement
                updated = 1
                next
            }
            { print }
            END {
                if (updated == 0) {
                    print target "=" replacement
                }
            }
        ' "$file" > "$tmp_file"

        mv "$tmp_file" "$file"
    }

    local config_dir="${AI_STACK_CONFIG_DIR:-${PRIMARY_HOME:-$HOME}/.config/nixos-ai-stack}"
    local env_file="${AI_STACK_ENV_FILE:-${config_dir}/.env}"
    export AI_STACK_ENV_FILE="$env_file"

    if [[ -f "$env_file" ]]; then
        if confirm "Reuse existing AI stack credentials at ${env_file}?" "y"; then
            local existing_db
            local existing_user
            local existing_password
            local existing_grafana_user
            local existing_grafana_password
            local existing_embedding_model
            local existing_llama_model
            local existing_llama_model_file
            local existing_ai_stack_data
            existing_db=$(read_env_value "POSTGRES_DB" "$env_file")
            existing_user=$(read_env_value "POSTGRES_USER" "$env_file")
            existing_password=$(read_env_value "POSTGRES_PASSWORD" "$env_file")
            existing_grafana_user=$(read_env_value "GRAFANA_ADMIN_USER" "$env_file")
            existing_grafana_password=$(read_env_value "GRAFANA_ADMIN_PASSWORD" "$env_file")
            existing_embedding_model=$(read_env_value "EMBEDDING_MODEL" "$env_file")
            existing_llama_model=$(read_env_value "LLAMA_CPP_DEFAULT_MODEL" "$env_file")
            existing_llama_model_file=$(read_env_value "LLAMA_CPP_MODEL_FILE" "$env_file")
            existing_ai_stack_data=$(read_env_value "AI_STACK_DATA" "$env_file")

            if [[ -z "$existing_db" ]]; then
                existing_db=$(prompt_user "Postgres database name" "${AI_STACK_POSTGRES_DB:-mcp}")
                set_env_value "POSTGRES_DB" "$existing_db" "$env_file"
            fi

            if [[ -z "$existing_user" ]]; then
                existing_user=$(prompt_user "Postgres username" "${AI_STACK_POSTGRES_USER:-mcp}")
                set_env_value "POSTGRES_USER" "$existing_user" "$env_file"
            fi

            if [[ -z "$existing_password" ]]; then
                if [[ "$interactive" != true ]]; then
                    print_error "Non-interactive session: POSTGRES_PASSWORD missing in $env_file. Set it and rerun."
                    return 1
                fi
                while true; do
                    existing_password=$(prompt_secret "Postgres password")
                    if [[ -n "$existing_password" ]]; then
                        break
                    fi
                    print_warning "Postgres password cannot be empty."
                done
                set_env_value "POSTGRES_PASSWORD" "$existing_password" "$env_file"
            fi

            if [[ -z "$existing_grafana_user" ]]; then
                existing_grafana_user=$(prompt_user "Grafana admin username" "${AI_STACK_GRAFANA_ADMIN_USER:-admin}")
                set_env_value "GRAFANA_ADMIN_USER" "$existing_grafana_user" "$env_file"
            fi

            if [[ -z "$existing_grafana_password" ]]; then
                if [[ "$interactive" != true ]]; then
                    print_error "Non-interactive session: GRAFANA_ADMIN_PASSWORD missing in $env_file. Set it and rerun."
                    return 1
                fi
                while true; do
                    existing_grafana_password=$(prompt_secret "Grafana admin password")
                    if [[ -n "$existing_grafana_password" ]]; then
                        break
                    fi
                    print_warning "Grafana admin password cannot be empty."
                done
                set_env_value "GRAFANA_ADMIN_PASSWORD" "$existing_grafana_password" "$env_file"
            fi

            if [[ -z "$existing_embedding_model" ]]; then
                existing_embedding_model="${EMBEDDING_MODEL:-BAAI/bge-small-en-v1.5}"
                set_env_value "EMBEDDING_MODEL" "$existing_embedding_model" "$env_file"
            fi

            if [[ -z "$existing_llama_model" ]]; then
                local llama_defaults
                llama_defaults=$(suggest_ai_stack_llama_defaults)
                existing_llama_model="${LLAMA_CPP_DEFAULT_MODEL:-${llama_defaults%%|*}}"
                set_env_value "LLAMA_CPP_DEFAULT_MODEL" "$existing_llama_model" "$env_file"
            fi

            if [[ -z "$existing_llama_model_file" ]]; then
                local llama_defaults
                llama_defaults=$(suggest_ai_stack_llama_defaults)
                existing_llama_model_file="${LLAMA_CPP_MODEL_FILE:-${llama_defaults##*|}}"
                set_env_value "LLAMA_CPP_MODEL_FILE" "$existing_llama_model_file" "$env_file"
            fi

            if [[ -z "$existing_ai_stack_data" ]]; then
                existing_ai_stack_data="${AI_STACK_DATA:-$HOME/.local/share/nixos-ai-stack}"
                set_env_value "AI_STACK_DATA" "$existing_ai_stack_data" "$env_file"
            fi

            chmod 600 "$env_file" 2>/dev/null || true
            return 0
        fi
    fi

    print_section "AI Stack Credentials"

    while true; do
        AI_STACK_POSTGRES_DB=$(prompt_user "Postgres database name" "${AI_STACK_POSTGRES_DB:-mcp}")
        if validate_username "$AI_STACK_POSTGRES_DB" 2>/dev/null; then break; fi
        print_warning "Database name must be lowercase alphanumeric (letters, digits, underscores, hyphens)."
    done

    while true; do
        AI_STACK_POSTGRES_USER=$(prompt_user "Postgres username" "${AI_STACK_POSTGRES_USER:-mcp}")
        if validate_username "$AI_STACK_POSTGRES_USER" 2>/dev/null; then break; fi
        print_warning "Username must start with a letter/underscore, then lowercase alphanumeric."
    done

    while true; do
        if [[ "$interactive" != true ]]; then
            print_error "Non-interactive session: POSTGRES_PASSWORD is required. Set it in $env_file and rerun."
            return 1
        fi
        AI_STACK_POSTGRES_PASSWORD=$(prompt_secret "Postgres password")
        if validate_password_strength "$AI_STACK_POSTGRES_PASSWORD" 2>/dev/null; then break; fi
        print_warning "Password must be 12+ characters with at least 3 of: uppercase, lowercase, digit, special char."
    done

    while true; do
        AI_STACK_GRAFANA_ADMIN_USER=$(prompt_user "Grafana admin username" "${AI_STACK_GRAFANA_ADMIN_USER:-admin}")
        if validate_username "$AI_STACK_GRAFANA_ADMIN_USER" 2>/dev/null; then break; fi
        print_warning "Username must start with a letter/underscore, then lowercase alphanumeric."
    done

    while true; do
        if [[ "$interactive" != true ]]; then
            print_error "Non-interactive session: GRAFANA_ADMIN_PASSWORD is required. Set it in $env_file and rerun."
            return 1
        fi
        AI_STACK_GRAFANA_ADMIN_PASSWORD=$(prompt_secret "Grafana admin password")
        if validate_password_strength "$AI_STACK_GRAFANA_ADMIN_PASSWORD" 2>/dev/null; then break; fi
        print_warning "Password must be 12+ characters with at least 3 of: uppercase, lowercase, digit, special char."
    done

    local llama_defaults
    llama_defaults=$(suggest_ai_stack_llama_defaults)

    mkdir -p "$config_dir"
    cat > "$env_file" <<EOF
AI_STACK_DATA=${AI_STACK_DATA:-$HOME/.local/share/nixos-ai-stack}
POSTGRES_DB=${AI_STACK_POSTGRES_DB}
POSTGRES_USER=${AI_STACK_POSTGRES_USER}
POSTGRES_PASSWORD=${AI_STACK_POSTGRES_PASSWORD}
GRAFANA_ADMIN_USER=${AI_STACK_GRAFANA_ADMIN_USER}
GRAFANA_ADMIN_PASSWORD=${AI_STACK_GRAFANA_ADMIN_PASSWORD}
EMBEDDING_MODEL=${EMBEDDING_MODEL:-BAAI/bge-small-en-v1.5}
LLAMA_CPP_DEFAULT_MODEL=${LLAMA_CPP_DEFAULT_MODEL:-${llama_defaults%%|*}}
LLAMA_CPP_MODEL_FILE=${LLAMA_CPP_MODEL_FILE:-${llama_defaults##*|}}
EOF

    chmod 600 "$env_file" 2>/dev/null || true
    print_success "Saved AI stack credentials to ${env_file}"
}

suggest_host_swap_limit_gb() {
    local ram_gb="${TOTAL_RAM_GB:-}"
    if ! [[ "$ram_gb" =~ ^[0-9]+$ ]] || (( ram_gb <= 0 )); then
        if declare -F resolve_total_ram_gb >/dev/null 2>&1; then
            ram_gb=$(resolve_total_ram_gb 2>/dev/null || echo 0)
        else
            ram_gb=0
        fi
    fi

    local swap_gb=0
    if declare -F calculate_active_swap_total_gb >/dev/null 2>&1; then
        swap_gb=$(calculate_active_swap_total_gb 2>/dev/null || echo 0)
    fi

    if ! [[ "$swap_gb" =~ ^[0-9]+$ ]]; then
        swap_gb=0
    fi

    if (( ram_gb <= 0 )); then
        echo 0
        return
    fi

    local recommended=$(( (ram_gb * 60 + 99) / 100 )) # ~60% of RAM, rounded up
    if (( recommended < 2 )); then
        recommended=2
    elif (( recommended > 32 )); then
        recommended=32
    fi

    if (( swap_gb > 0 && recommended > swap_gb )); then
        recommended="$swap_gb"
    fi

    echo "$recommended"
}

configure_host_swap_limits() {
    local suggested_swap_gb
    suggested_swap_gb=$(suggest_host_swap_limit_gb)
    local default_swap_gb="${HOST_SWAP_LIMIT_GB:-}"
    local swap_total_gb=0
    if declare -F calculate_active_swap_total_gb >/dev/null 2>&1; then
        swap_total_gb=$(calculate_active_swap_total_gb 2>/dev/null || echo 0)
    fi

    local ram_gb="${TOTAL_RAM_GB:-}"
    if ! [[ "$ram_gb" =~ ^[0-9]+$ ]] || (( ram_gb <= 0 )); then
        if declare -F resolve_total_ram_gb >/dev/null 2>&1; then
            ram_gb=$(resolve_total_ram_gb 2>/dev/null || echo 0)
        else
            ram_gb=0
        fi
    fi

    if [[ -z "$default_swap_gb" ]]; then
        if [[ "$suggested_swap_gb" =~ ^[0-9]+$ && "$suggested_swap_gb" -gt 0 ]]; then
            default_swap_gb="auto"
        else
            default_swap_gb="0"
        fi
    fi

    local min_rec=0
    local max_rec=0
    if (( ram_gb > 0 )); then
        min_rec=$(( (ram_gb * 25 + 99) / 100 ))
        if (( min_rec < 2 )); then
            min_rec=2
        fi
        max_rec=$(( (ram_gb * 75 + 99) / 100 ))
        if (( max_rec < min_rec )); then
            max_rec=$min_rec
        fi
        if (( swap_total_gb > 0 )); then
            if (( min_rec > swap_total_gb )); then
                min_rec=$swap_total_gb
            fi
            if (( max_rec > swap_total_gb )); then
                max_rec=$swap_total_gb
            fi
        fi
    fi

    if [[ "${HOST_SWAP_LIMIT_ENABLED:-}" == "true" ]]; then
        print_info "Host swap limits already enabled (${HOST_SWAP_LIMIT_VALUE:-${HOST_SWAP_LIMIT_GB}G}). Skipping prompt."
        return 0
    fi
    if [[ "${HOST_SWAP_LIMIT_ENABLED:-}" == "false" && -n "${HOST_SWAP_LIMIT_VALUE:-}" ]]; then
        print_info "Host swap limits explicitly disabled; skipping prompt."
        return 0
    fi

    if confirm "Configure host-level swap limits for systemd services (includes containers)?" "y"; then
        if [[ "$suggested_swap_gb" =~ ^[0-9]+$ && "$suggested_swap_gb" -gt 0 ]]; then
            if [[ "$swap_total_gb" =~ ^[0-9]+$ && "$swap_total_gb" -gt 0 ]]; then
                print_info "Suggested swap cap: ${suggested_swap_gb}GB (≈60% RAM, capped by total swap ${swap_total_gb}GB)."
            else
                print_info "Suggested swap cap: ${suggested_swap_gb}GB (≈60% RAM)."
            fi
        else
            print_info "No active swap detected; consider 'skip' to disable host swap limits."
        fi

        if (( min_rec > 0 && max_rec > 0 )); then
            print_info "Recommended per-service range: ${min_rec}-${max_rec}GB (adjust for workload spikes)."
        fi
        print_info "Examples: auto, 0 (no cap), ${suggested_swap_gb}, ${min_rec}, skip"

        local swap_input
        local attempts=0
        while true; do
            swap_input=$(prompt_user "Default swap max per service in GB (0=unlimited, 'auto'=suggested, 'skip'=disable)" "$default_swap_gb")
            case "${swap_input,,}" in
                ""|"auto"|"default"|"suggested"|"rec"|"recommended")
                    if [[ "$suggested_swap_gb" =~ ^[0-9]+$ && "$suggested_swap_gb" -gt 0 ]]; then
                        swap_input="$suggested_swap_gb"
                    else
                        swap_input="0"
                    fi
                    ;;
                "skip"|"none"|"no")
                    HOST_SWAP_LIMIT_ENABLED=false
                    HOST_SWAP_LIMIT_VALUE=""
                    print_info "Skipping host swap limits per user choice."
                    return 0
                    ;;
            esac

            if [[ "$swap_input" =~ ^[0-9]+$ ]]; then
                if [[ "$swap_total_gb" =~ ^[0-9]+$ && "$swap_total_gb" -gt 0 && "$swap_input" -gt "$swap_total_gb" ]]; then
                    print_warning "Requested swap cap (${swap_input}GB) exceeds total swap (${swap_total_gb}GB). Capping to ${swap_total_gb}GB."
                    swap_input="$swap_total_gb"
                fi
                HOST_SWAP_LIMIT_GB="$swap_input"
                HOST_SWAP_LIMIT_ENABLED=true
                if (( swap_input <= 0 )); then
                    HOST_SWAP_LIMIT_VALUE="infinity"
                else
                    HOST_SWAP_LIMIT_VALUE="${swap_input}G"
                fi
                export HOST_SWAP_LIMIT_ENABLED HOST_SWAP_LIMIT_GB HOST_SWAP_LIMIT_VALUE
                print_success "Host swap limit set to ${HOST_SWAP_LIMIT_VALUE}"
                break
            fi

            attempts=$((attempts + 1))
            if (( attempts >= 3 )); then
                print_warning "Swap limit must be a number of GB (or 'auto'/'skip'). Skipping host swap limits after ${attempts} invalid entries."
                HOST_SWAP_LIMIT_ENABLED=false
                break
            fi
            print_warning "Swap limit must be a number of GB (or 'auto'/'skip'). Try again."
        done
    fi
}

# ============================================================================
# MAIN FUNCTION
# ============================================================================

# setup_environment: Load libraries, configuration, acquire deployment lock,
# and run preflight checks. Returns non-zero on failure.
setup_environment() {
    # Load core components
    load_libraries
    load_configuration
    synchronize_primary_user_path
    if ! validate_config; then
        exit "${ERR_CONFIG_INVALID:-30}"
    fi

    if [[ -n "$ZSWAP_CONFIGURATION_OVERRIDE_REQUEST" ]]; then
        case "$ZSWAP_CONFIGURATION_OVERRIDE_REQUEST" in
            enable|disable|auto)
                ZSWAP_CONFIGURATION_OVERRIDE="$ZSWAP_CONFIGURATION_OVERRIDE_REQUEST"
                export ZSWAP_CONFIGURATION_OVERRIDE
                if declare -F persist_zswap_configuration_override >/dev/null 2>&1; then
                    persist_zswap_configuration_override "$ZSWAP_CONFIGURATION_OVERRIDE" || true
                fi
                case "$ZSWAP_CONFIGURATION_OVERRIDE" in
                    enable)
                        print_info "Zswap override set to ENABLE; prompts will appear even if detection fails."
                        ;;
                    disable)
                        print_info "Zswap override set to DISABLE; swap-backed hibernation will be skipped."
                        ;;
                    auto)
                        print_info "Zswap override cleared; automatic detection restored."
                        ;;
                esac
                ;;
        esac
    fi

    if [[ -n "$EARLY_KMS_POLICY_OVERRIDE_REQUEST" ]]; then
        case "$EARLY_KMS_POLICY_OVERRIDE_REQUEST" in
            off|auto|force)
                EARLY_KMS_POLICY="$EARLY_KMS_POLICY_OVERRIDE_REQUEST"
                export EARLY_KMS_POLICY
                case "$EARLY_KMS_POLICY" in
                    off)
                        print_warning "Early KMS module preloading disabled for this run (EARLY_KMS_POLICY=off)."
                        ;;
                    auto)
                        print_info "Early KMS module preloading set to automatic mode."
                        ;;
                    force)
                        print_warning "Early KMS module preloading forced for this run (EARLY_KMS_POLICY=force)."
                        ;;
                esac
                ;;
        esac
    fi

    # Enable strict undefined variable checking
    set -u

    # Handle rollback mode
    if [[ "$ROLLBACK" == true ]]; then
        ROLLBACK_IN_PROGRESS=true
        export ROLLBACK_IN_PROGRESS
        perform_rollback
        exit $?
    fi

    # Handle state reset
    if [[ "$RESET_STATE" == true ]]; then
        reset_state
        print_success "State reset successfully"
        exit 0
    fi

    # Initialize core systems
    init_logging
    if ! validate_runtime_paths; then
        exit 1
    fi
    ensure_nix_experimental_features_env
    init_state
    maybe_reset_config_phases_on_template_change
    if [[ "$RESUME" == true ]]; then
        print_info "Validating resume state..."
        if ! bootstrap_resume_validation_tools "$VALIDATE_STATE"; then
            exit "${ERR_STATE_INVALID:-31}"
        fi
        if ! validate_resume_state "$VALIDATE_STATE"; then
            exit "${ERR_STATE_INVALID:-31}"
        fi
    fi
    configure_host_swap_limits

    # Prevent concurrent deployments (avoids overlapping Phase 9 runs)
    local lock_file="${CACHE_DIR}/deploy.lock"
    local lock_fd=200
    mkdir -p "$CACHE_DIR" >/dev/null 2>&1 || true
    if command -v flock >/dev/null 2>&1; then
        local lock_acquired=false
        local lock_start_time
        local lock_warned=false
        local lock_timeout_sec="${DEPLOY_LOCK_TIMEOUT_SEC:-60}"
        lock_start_time=$(date +%s)
        while true; do
            exec 200>"${lock_file}"
            if flock -n "$lock_fd"; then
                printf '%s\n' "$$" > "$lock_file"
                lock_acquired=true
                break
            fi
            local lock_pid
            lock_pid=$(cat "$lock_file" 2>/dev/null || true)
            if [[ -n "$lock_pid" ]] && ! kill -0 "$lock_pid" 2>/dev/null; then
                print_warning "Stale deploy lock detected (PID $lock_pid not running); clearing lock."
                rm -f "$lock_file" 2>/dev/null || true
                continue
            fi
            local now elapsed
            now=$(date +%s)
            elapsed=$((now - lock_start_time))
            if (( lock_timeout_sec > 0 && elapsed >= lock_timeout_sec )); then
                print_error "Another nixos-quick-deploy instance is running (lock: $lock_file, waited ${elapsed}s)"
                exit 1
            fi
            if [[ "$lock_warned" != true ]]; then
                print_warning "Another nixos-quick-deploy instance is running; waiting for lock release..."
                lock_warned=true
            fi
            sleep 2
        done
        if [[ "$lock_acquired" != true ]]; then
            print_error "Unable to acquire deploy lock (lock: $lock_file)"
            exit 1
        fi
        _DEPLOY_LOCK_FD="$lock_fd"
        _DEPLOY_LOCK_FILE="$lock_file"
        DEPLOY_LOCK_FILE="$lock_file"
        export DEPLOY_LOCK_FILE
        trap _deploy_exit_cleanup EXIT
    else
        if [[ -f "$lock_file" ]]; then
            local lock_pid
            lock_pid=$(cat "$lock_file" 2>/dev/null || true)
            if [[ -n "$lock_pid" ]] && kill -0 "$lock_pid" 2>/dev/null; then
                print_error "Another nixos-quick-deploy instance is running (PID: $lock_pid)"
                exit 1
            fi
            if [[ -n "$lock_pid" ]]; then
                print_warning "Stale deploy lock detected (PID $lock_pid not running); clearing lock."
            fi
            rm -f "$lock_file" 2>/dev/null || true
        fi
        echo "$$" > "$lock_file"
        _DEPLOY_LOCK_FILE="$lock_file"
        DEPLOY_LOCK_FILE="$lock_file"
        export DEPLOY_LOCK_FILE
        trap _deploy_exit_cleanup EXIT
    fi

    # Preflight: avoid overlapping AI stack setup/stack runs
    local allow_running_stack_setup="${ALLOW_RUNNING_STACK_SETUP:-false}"
    local auto_stop_stack="${AUTO_STOP_STACK_ON_CONFLICT:-false}"
    if [[ "$allow_running_stack_setup" != "true" ]]; then
        local stack_conflict=false
        if pgrep -f "setup-hybrid-learning-auto\\.sh" >/dev/null 2>&1; then
            print_warning "Hybrid learning setup is already running (setup-hybrid-learning-auto.sh)."
            stack_conflict=true
        fi
        if [[ "$stack_conflict" == "true" ]]; then
            if [[ "$auto_stop_stack" == "true" && -x "${SCRIPT_DIR}/scripts/stop-ai-stack.sh" ]]; then
                print_warning "AUTO_STOP_STACK_ON_CONFLICT=true; stopping AI stack to continue."
                "${SCRIPT_DIR}/scripts/stop-ai-stack.sh" || print_warning "AI stack stop reported issues."
            else
                print_error "AI stack setup is already running. Aborting to avoid conflicts."
                print_info "Wait for it to finish or re-run with ALLOW_RUNNING_STACK_SETUP=true"
                print_info "To auto-stop conflicting processes, set AUTO_STOP_STACK_ON_CONFLICT=true"
                exit 1
            fi
        fi
    fi
}

# maybe_prompt_flake_first_ai_stack: collect declarative AI stack and model choices
# early in flake-first flow so selections become host-scoped Nix options.
maybe_prompt_flake_first_ai_stack() {
    if [[ "$FLAKE_FIRST_AI_STACK_EXPLICIT" == true || ! -t 0 || ! -t 1 ]]; then
        return 0
    fi

    local default_answer="n"
    if [[ "$profile" == "ai-dev" ]]; then
        default_answer="y"
    fi
    if confirm "Enable declarative AI stack services for this host/profile?" "$default_answer"; then
        RUN_AI_MODEL=true
    else
        RUN_AI_MODEL=false
    fi

    if [[ "$RUN_AI_MODEL" != true ]]; then
        return 0
    fi

    if [[ "${FLAKE_FIRST_MODEL_PROFILE}" == "auto" ]]; then
        local prompt_profile
        prompt_profile=$(prompt_user "Model profile [auto|small|medium|large]" "auto")
        case "${prompt_profile,,}" in
            auto|small|medium|large) FLAKE_FIRST_MODEL_PROFILE="${prompt_profile,,}" ;;
            *) print_warning "Unknown model profile '${prompt_profile}', keeping auto." ;;
        esac
    fi
}

# resolve_flake_first_model_selection: map model profile selection to concrete
# embedding + llama defaults that are persisted declaratively per host.
resolve_flake_first_model_selection() {
    local llama_defaults
    llama_defaults=$(suggest_ai_stack_llama_defaults)
    local default_model="${llama_defaults%%|*}"
    local default_file="${llama_defaults##*|}"
    local embed_default="${EMBEDDING_MODEL:-BAAI/bge-small-en-v1.5}"

    case "${FLAKE_FIRST_MODEL_PROFILE:-auto}" in
        small)
            FLAKE_FIRST_EMBEDDING_MODEL="BAAI/bge-small-en-v1.5"
            FLAKE_FIRST_LLM_MODEL="Qwen/Qwen2.5-Coder-3B-Instruct-GGUF"
            FLAKE_FIRST_LLM_MODEL_FILE="qwen2.5-coder-3b-instruct-q4_k_m.gguf"
            ;;
        medium)
            FLAKE_FIRST_EMBEDDING_MODEL="BAAI/bge-small-en-v1.5"
            FLAKE_FIRST_LLM_MODEL="Qwen/Qwen2.5-Coder-7B-Instruct-GGUF"
            FLAKE_FIRST_LLM_MODEL_FILE="qwen2.5-coder-7b-instruct-q4_k_m.gguf"
            ;;
        large)
            FLAKE_FIRST_EMBEDDING_MODEL="BAAI/bge-base-en-v1.5"
            FLAKE_FIRST_LLM_MODEL="Qwen/Qwen2.5-Coder-14B-Instruct-GGUF"
            FLAKE_FIRST_LLM_MODEL_FILE="qwen2.5-coder-14b-instruct-q4_k_m.gguf"
            ;;
        *)
            FLAKE_FIRST_EMBEDDING_MODEL="$embed_default"
            FLAKE_FIRST_LLM_MODEL="${LLAMA_CPP_DEFAULT_MODEL:-$default_model}"
            FLAKE_FIRST_LLM_MODEL_FILE="${LLAMA_CPP_MODEL_FILE:-$default_file}"
            ;;
    esac
}

# persist_flake_first_host_options: write host-scoped declarative deploy options
# consumed by flake.nix for AI-stack enablement and model selection.
persist_flake_first_host_options() {
    local host_name="$1"
    local host_dir="${SCRIPT_DIR}/nix/hosts/${host_name}"
    local deploy_file="${host_dir}/deploy-options.nix"

    if [[ ! -d "$host_dir" ]]; then
        print_error "Host directory not found for declarative options: $host_dir"
        return 1
    fi

    resolve_flake_first_model_selection

    cat > "$deploy_file" <<EOF
{ lib, ... }:
{
  mySystem.roles.aiStack.enable = lib.mkForce ${RUN_AI_MODEL};
  mySystem.aiStack = {
    enable = lib.mkForce ${RUN_AI_MODEL};
    modelProfile = lib.mkForce "${FLAKE_FIRST_MODEL_PROFILE}";
    embeddingModel = lib.mkForce "${FLAKE_FIRST_EMBEDDING_MODEL}";
    llamaDefaultModel = lib.mkForce "${FLAKE_FIRST_LLM_MODEL}";
    llamaModelFile = lib.mkForce "${FLAKE_FIRST_LLM_MODEL_FILE}";
  };
}
EOF

    print_info "Updated declarative deploy options: ${deploy_file}"
    return 0
}

# apply_flake_first_ai_stack_toggle: persist the --without-ai-model choice for
# declarative reconciliation by writing/removing the AI stack disable marker.
apply_flake_first_ai_stack_toggle() {
    local marker_path="${AI_STACK_DISABLE_MARKER:-/var/lib/nixos-quick-deploy/disable-ai-stack}"
    local marker_dir
    marker_dir="$(dirname "$marker_path")"

    if [[ "$DRY_RUN" == true ]]; then
        if [[ "$RUN_AI_MODEL" == true ]]; then
            print_info "[DRY RUN] Would remove AI stack disable marker: ${marker_path}"
        else
            print_info "[DRY RUN] Would create AI stack disable marker: ${marker_path}"
        fi
        return 0
    fi

    if [[ "$RUN_AI_MODEL" == true ]]; then
        if sudo rm -f "$marker_path"; then
            print_info "AI stack disable marker removed (${marker_path}); declarative reconciliation enabled."
        else
            print_error "Failed to remove AI stack disable marker: ${marker_path}"
            return 1
        fi
        return 0
    fi

    if ! sudo mkdir -p "$marker_dir"; then
        print_error "Failed to create marker directory: ${marker_dir}"
        return 1
    fi

    if sudo touch "$marker_path"; then
        print_info "AI stack disable marker created (${marker_path}); declarative reconciliation disabled."
    else
        print_error "Failed to create AI stack disable marker: ${marker_path}"
        return 1
    fi
}

# run_flake_first_roadmap_verification: enforce roadmap-complete flake-first
# implementation markers before running declarative deployment.
run_flake_first_roadmap_verification() {
    if [[ "${SKIP_ROADMAP_VERIFICATION:-false}" == "true" ]]; then
        print_info "Skipping roadmap-completion verification (--skip-roadmap-verification)"
        return 0
    fi

    local verifier="${SCRIPT_DIR}/scripts/verify-flake-first-roadmap-completion.sh"
    if [[ ! -x "$verifier" ]]; then
        print_warning "Roadmap-completion verifier not executable (${verifier}); skipping verification."
        return 0
    fi

    print_info "Verifying roadmap-complete flake-first requirements"
    if ! "$verifier"; then
        print_error "Roadmap-completion verification failed. Resolve missing items or rerun with --skip-roadmap-verification."
        return 1
    fi

    return 0
}

# run_flake_first_deployment: Execute a direct declarative deployment path.
# This bypasses the 9-phase generator pipeline and applies the root flake.
run_flake_first_deployment() {
    print_section "Flake-First Deployment Mode"

    local profile="${FLAKE_FIRST_PROFILE:-ai-dev}"
    if [[ "${AUTO_PROMPT_PROFILE_SELECTION:-true}" == "true" && "${FLAKE_FIRST_PROFILE_EXPLICIT:-false}" != "true" && -t 0 && -t 1 ]]; then
        print_info "Select flake-first profile:"
        echo "  1) ai-dev   (AI/dev workstation stack)"
        echo "  2) gaming   (gaming-focused desktop stack)"
        echo "  3) minimal  (minimal base system)"
        local profile_choice=""
        if declare -F prompt_user >/dev/null 2>&1; then
            profile_choice="$(prompt_user "Choose profile [1-3 or name]" "$profile")"
        else
            read -r -p "Choose profile [1-3 or name] (default: ${profile}): " profile_choice
            profile_choice="${profile_choice:-$profile}"
        fi
        case "${profile_choice,,}" in
            1|ai|ai-dev|aidev) profile="ai-dev" ;;
            2|gaming|game) profile="gaming" ;;
            3|min|minimal) profile="minimal" ;;
            "") ;;
            *)
                print_warning "Unknown profile selection '${profile_choice}', keeping '${profile}'."
                ;;
        esac
    fi
    case "$profile" in
        ai-dev|gaming|minimal) ;;
        *)
            print_error "Invalid --flake-first-profile '$profile' (expected ai-dev|gaming|minimal)"
            return 1
            ;;
    esac

    maybe_prompt_flake_first_ai_stack

    local deploy_mode="${FLAKE_FIRST_DEPLOY_MODE:-switch}"
    case "$deploy_mode" in
        switch|boot|build) ;;
        *)
            print_error "Invalid flake deploy mode '${deploy_mode}' (expected switch|boot|build)"
            return 1
            ;;
    esac

    local detected_host
    detected_host=$(hostname -s 2>/dev/null || hostname)
    detected_host=$(printf '%s' "$detected_host" | tr '[:upper:]' '[:lower:]' | tr -cd 'a-z0-9-')
    if [[ -z "$detected_host" ]]; then
        detected_host="nixos"
    fi

    local hosts_root="${SCRIPT_DIR}/nix/hosts"
    if [[ ! -f "${hosts_root}/${detected_host}/default.nix" && -d "$hosts_root" ]]; then
        local -a detected_hosts=()
        mapfile -t detected_hosts < <(find "$hosts_root" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | while IFS= read -r host; do [[ -f "$hosts_root/$host/default.nix" ]] && printf '%s\n' "$host"; done | sort -u)
        if [[ ${#detected_hosts[@]} -eq 1 ]]; then
            print_warning "Detected hostname '${detected_host}' has no flake host directory; using '${detected_hosts[0]}'"
            detected_host="${detected_hosts[0]}"
        fi
    fi

    local flake_ref="path:${SCRIPT_DIR}"
    local deploy_clean_script="${SCRIPT_DIR}/scripts/deploy-clean.sh"
    local nixos_target="${FLAKE_FIRST_TARGET:-${detected_host}-${profile}}"

    if [[ ! -x "$deploy_clean_script" ]]; then
        print_error "Clean deploy script missing or not executable: $deploy_clean_script"
        return 1
    fi

    if ! command -v nix >/dev/null 2>&1; then
        print_error "nix command is required for --flake-first mode"
        return 1
    fi

    local nix_cache_root="${XDG_CACHE_HOME:-$HOME/.cache}"
    local -a nix_env=(env XDG_CACHE_HOME="$nix_cache_root" NIX_CONFIG="experimental-features = nix-command flakes")

    if [[ "${PROMPT_BEFORE_SYSTEM_SWITCH,,}" == "true" ]]; then
        print_info "Select flake-first deploy mode:"
        echo "  1) switch (apply now, no reboot)"
        echo "  2) boot   (stage next generation, reboot required)"
        echo "  3) build  (dry-build only)"
        read -r -p "Choose mode [1/2/3] (default: ${deploy_mode}): " mode_choice
        case "${mode_choice,,}" in
            2|b|boot) deploy_mode="boot" ;;
            3|d|dry|build) deploy_mode="build" ;;
            ""|1|s|switch) deploy_mode="switch" ;;
            *)
                print_warning "Unknown selection '${mode_choice}', keeping mode '${deploy_mode}'."
                ;;
        esac
    fi

    if [[ "${PROMPT_BEFORE_SYSTEM_SWITCH,,}" == "true" && "${deploy_mode}" == "switch" ]]; then
        if ! confirm "Apply system configuration now via flake-first switch?" "y"; then
            AUTO_APPLY_SYSTEM_CONFIGURATION=false
        fi
    fi

    if [[ "${PROMPT_BEFORE_HOME_SWITCH,,}" == "true" ]]; then
        if ! confirm "Apply Home Manager configuration now via flake-first switch/build?" "y"; then
            AUTO_APPLY_HOME_CONFIGURATION=false
        fi
    fi

    local -a deploy_args=(
        --host "$detected_host"
        --profile "$profile"
        --flake-ref "$flake_ref"
    )

    if [[ -n "${FLAKE_FIRST_TARGET:-}" ]]; then
        deploy_args+=(--nixos-target "$FLAKE_FIRST_TARGET")
    fi

    if [[ "${AUTO_UPDATE_FLAKE_INPUTS:-false}" == "true" ]]; then
        deploy_args+=(--update-lock)
    fi

    if [[ "${SKIP_HEALTH_CHECK:-false}" == "true" ]]; then
        deploy_args+=(--skip-health-check)
    fi

    if [[ "${AUTO_APPLY_SYSTEM_CONFIGURATION,,}" != "true" ]]; then
        deploy_args+=(--skip-system-switch)
    fi

    if [[ "${AUTO_APPLY_HOME_CONFIGURATION,,}" != "true" ]]; then
        deploy_args+=(--skip-home-switch)
    fi

    case "$deploy_mode" in
        boot) deploy_args+=(--boot) ;;
        build) deploy_args+=(--build-only) ;;
    esac

    if [[ "$DRY_RUN" == true ]]; then
        print_info "[DRY RUN] Running flake check (no build): nix flake check --no-build ${flake_ref}"
        if ! "${nix_env[@]}" nix flake check --no-build "$flake_ref"; then
            print_error "Dry-run flake check failed for ${flake_ref}"
            return 1
        fi
        print_success "Dry-run flake check passed"
        print_info "[DRY RUN] Would run: ${deploy_clean_script} ${deploy_args[*]}"
        return 0
    fi

    print_info "Using flake target: ${nixos_target} (mode=${deploy_mode})"

    # Password preservation guarantee:
    # The flake-first path sets users.mutableUsers = true in
    # nix/modules/core/users.nix.  With mutableUsers = true NixOS preserves
    # the login password from /etc/shadow across every nixos-rebuild — the
    # deploy script NEVER prompts for or modifies the login password.
    # To change your password run: passwd
    print_info "Password policy: login password is PRESERVED (mutableUsers = true)"

    if ! run_flake_first_roadmap_verification; then
        return 1
    fi

    if ! persist_flake_first_host_options "$detected_host"; then
        print_error "Failed to persist host-scoped declarative deploy options"
        return 1
    fi

    if ! ensure_ai_stack_env; then
        print_error "Failed to prepare AI stack environment configuration"
        return 1
    fi

    prewarm_ai_stack_embeddings_cache

    if ! apply_flake_first_ai_stack_toggle; then
        print_error "Failed to persist AI stack declarative toggle state"
        return 1
    fi

    if ! run_optional_phase_script "$PHASES_DIR/phase-02-system-backup.sh" phase_02_backup "Comprehensive backup"; then
        print_error "Flake-first backup parity task failed"
        return 1
    fi

    print_info "Executing declarative deploy via scripts/deploy-clean.sh"
    if ! "$deploy_clean_script" "${deploy_args[@]}"; then
        print_error "Flake-first deploy-clean execution failed"
        return 1
    fi

    if ! run_flake_first_legacy_outcome_tasks "$deploy_mode"; then
        print_error "Flake-first legacy completion tasks failed"
        return 1
    fi

    if declare -F mark_step_complete >/dev/null 2>&1; then
        mark_step_complete "flake-first-switch" || true
    fi

    print_success "Flake-first deployment path completed"
    return 0
}

# run_flake_first_legacy_outcome_tasks: execute legacy parity tasks that remain
# relevant for flake-first mode (tooling, validation, reporting, and optional
# runtime AI stack gates) while keeping declarative system/profile deployment.
run_flake_first_legacy_outcome_tasks() {
    local deploy_mode="$1"

    # In boot mode, system-level changes are staged and may require reboot before
    # downstream runtime expectations (desktop/session, user auth) are visible.
    if [[ "$deploy_mode" == "boot" ]]; then
        print_warning "System changes are staged for next boot. Reboot required for desktop/user/service changes."
    fi

    print_section "Flake-First Completion: Legacy-Parity Tasks"

    if ! run_optional_phase_script "$PHASES_DIR/phase-06-additional-tooling.sh" phase_06_additional_tooling "Additional tooling"; then
        return 1
    fi

    if ! run_optional_phase_script "$PHASES_DIR/phase-07-post-deployment-validation.sh" phase_07_post_deployment_validation "Post-deployment validation"; then
        return 1
    fi

    if ! run_optional_phase_script "$PHASES_DIR/phase-08-finalization-and-report.sh" phase_08_finalization_and_report "Finalization and report"; then
        return 1
    fi

    if [[ "$RUN_AI_PREP" == true ]]; then
        if ! run_optional_phase_script "$PHASES_DIR/phase-09-ai-optimizer-prep.sh" phase_09_ai_optimizer_prep "AI-Optimizer preparation"; then
            return 1
        fi
    fi

    if [[ "$RUN_AI_MODEL" == true ]]; then
        print_info "Phase 9 imperative stack/model scripts skipped in flake-first; declarative AI stack module owns deployment."
    fi

    return 0
}

# run_deployment_phases: Execute the 9-phase deployment workflow plus optional
# AI-Optimizer and AI Model phases.
run_deployment_phases() {
    if [[ "${LEGACY_PHASES_MODE:-false}" == "true" ]]; then
        print_warning "Legacy phase pipeline enabled (--legacy-phases). This path is maintenance mode; critical fixes only."
    fi

    # Print deployment header
    print_header

    if [[ "$DRY_RUN" == false ]]; then
        start_sudo_keepalive
    fi

    # Handle test phase mode
    if [[ -n "$TEST_PHASE" ]]; then
        log INFO "Testing phase $TEST_PHASE in isolation"
        print_section "Testing Phase $TEST_PHASE"
        execute_phase "$TEST_PHASE"
        exit $?
    fi

    # Determine starting phase
    local start_phase=1

    if [[ -n "$START_FROM_PHASE" ]]; then
        start_phase=$START_FROM_PHASE
        log INFO "Starting from phase $start_phase (user specified)"
    elif [[ "$RESUME" == true ]] || [[ -z "$START_FROM_PHASE" ]]; then
        start_phase=$(get_resume_phase)
        if [[ $start_phase -gt 1 ]]; then
            log INFO "Resuming from phase $start_phase"
            print_info "Resuming from phase $start_phase"
        fi
    fi

    # Validate starting phase number
    if [[ ! "$start_phase" =~ ^[0-9]+$ ]] || [[ "$start_phase" -lt 1 ]] || [[ "$start_phase" -gt 9 ]]; then
        print_error "Invalid starting phase: $start_phase"
        exit 1
    fi

    # Create rollback point
    if [[ "$DRY_RUN" == false && $start_phase -eq 1 ]]; then
        log INFO "Creating rollback point"
        create_rollback_point "Before deployment $(date +%Y-%m-%d_%H:%M:%S)"
    fi

    # Execute phases sequentially
    echo ""
    print_section "Starting 9-Phase Deployment Workflow"
    log INFO "Starting deployment from phase $start_phase"
    echo ""

    for phase_num in $(seq $start_phase 9); do
        # Check if phase should be skipped
        if should_skip_phase "$phase_num"; then
            log INFO "Skipping phase $phase_num (user requested)"
            print_info "Skipping Phase $phase_num (--skip-phase)"
            continue
        fi

        # Execute phase
        if ! execute_phase "$phase_num"; then
            handle_phase_failure "$phase_num" || exit 1
        fi

        echo ""
    done

    print_inter_phase_health_summary
    echo ""

    if [[ "$RUN_AI_PREP" == true ]]; then
        print_section "Optional Phase: AI-Optimizer Preparation"
        if ! run_optional_phase_script "$PHASES_DIR/phase-09-ai-optimizer-prep.sh" phase_09_ai_optimizer_prep "AI-Optimizer preparation"; then
            exit 1
        fi
    fi

    if [[ "$RUN_AI_MODEL" == true ]]; then
        print_section "Optional Phase: AI Model Deployment"
        if ! run_optional_phase_script "$PHASES_DIR/phase-09-ai-model-deployment.sh" phase_09_ai_model_deployment "AI model deployment"; then
            exit 1
        fi
    fi
}

# run_post_deployment: Execute post-deployment tasks including rollback tests,
# AI stack startup, and final health checks. Returns the aggregate exit code.
run_post_deployment() {
    local rollback_test_exit=0
    if [[ "$TEST_ROLLBACK" == true ]]; then
        if ! test_rollback_flow; then
            rollback_test_exit=$?
            print_warning "Rollback validation reported issues."
        fi
    fi

    local stack_exit=0
    if [[ "$RUN_AI_MODEL" == true ]]; then
        local startup_script="$SCRIPT_DIR/scripts/start-ai-stack-and-dashboard.sh"
        if [[ -x "$startup_script" ]]; then
            print_section "Post-Deploy: Start AI Stack + Dashboard"
            log INFO "Starting AI stack + dashboard via $startup_script"
            if "$startup_script"; then
                print_success "AI stack + dashboard startup completed"
                wait_for_ai_stack_readiness || true
                echo ""
            else
                stack_exit=$?
                print_warning "AI stack + dashboard startup reported issues. Review the output above."
                echo ""
            fi
        else
            log WARNING "Startup script missing at $startup_script"
            print_warning "AI stack startup script not found at $startup_script"
            print_info "Ensure scripts are up to date (git pull) and rerun."
            echo ""
            stack_exit=1
        fi
    else
        log INFO "Skipping AI stack startup (AI model deployment disabled)"
        print_info "Skipping AI stack startup (--without-ai-model)"
        echo ""
    fi

    # Deployment success
    log INFO "All phases completed successfully"
    echo ""

    local health_exit=0
    local health_script="$SCRIPT_DIR/scripts/system-health-check.sh"
    if [[ "$SKIP_HEALTH_CHECK" != true ]]; then
        if [[ "${FINAL_PHASE_HEALTH_CHECK_COMPLETED:-false}" == true ]]; then
            log INFO "Skipping redundant final health check (already run in Phase 8)"
            print_info "Final health check already completed during Phase 8"
        else
            if [[ -x "$health_script" ]]; then
                print_section "Final System Health Check"
                log INFO "Running final system health check via $health_script"
                echo ""
                if "$health_script" --detailed; then
                    print_success "System health check passed"
                    echo ""
                else
                    health_exit=$?
                    print_warning "System health check reported issues. Review the output above and rerun with --fix if needed."
                    echo ""
                fi
            else
                log WARNING "Health check script missing at $health_script"
                print_warning "Health check script not found at $health_script"
                print_info "Run git pull to restore scripts or download manually."
                echo ""
            fi
        fi
    else
        log INFO "Skipping final health check (flag)"
        print_info "Skipping final health check (--skip-health-check)"
    fi

    echo "============================================"
    local final_exit=0
    if [[ $health_exit -ne 0 || $stack_exit -ne 0 || $rollback_test_exit -ne 0 ]]; then
        final_exit=1
    fi

    if [[ $final_exit -eq 0 ]]; then
        print_success "Deployment completed successfully!"

        # Show AI Stack health check info (if available)
        local health_monitor="$SCRIPT_DIR/scripts/ai-stack-health.sh"
        if [[ -x "$health_monitor" && "${SKIP_AI_MODEL:-false}" != true ]]; then
            echo ""
            print_info "AI Stack health check available at: $health_monitor"
            print_info "To check stack status, run: kubectl get pods -n ai-stack"
            echo ""
        fi
    else
        print_warning "Deployment completed with follow-up actions required."
        if [[ $health_exit -ne 0 ]]; then
            print_info "Review the health check summary above. You can rerun fixes with: $health_script --fix"
        fi
        if [[ $rollback_test_exit -ne 0 ]]; then
            print_info "Rollback validation failed. You can rerun with: $SCRIPT_DIR/nixos-quick-deploy.sh --test-rollback"
            print_info "Set AUTO_CONFIRM_ROLLBACK_TEST=true to skip the confirmation prompt."
        fi
        if [[ $stack_exit -ne 0 ]]; then
            print_info "AI stack + dashboard startup failed. Run: $SCRIPT_DIR/scripts/start-ai-stack-and-dashboard.sh"
        fi
    fi
    echo "============================================"
    echo ""
    echo "Log file: $LOG_FILE"
    echo ""

    return $final_exit
}

# End-to-end orchestrator: parses arguments, sets up environment, runs the
# phase machine, and executes post-deployment tasks.
main() {
    # Parse arguments
    parse_arguments "$@"

    if [[ "$FLATPAK_REINSTALL_REQUEST" == true ]]; then
        export RESET_FLATPAK_STATE_BEFORE_SWITCH="true"
    fi

    # Enable debug mode if requested
    if [[ "$ENABLE_DEBUG" == true ]]; then
        set -x
    fi

    # Configure logging level
    if [[ "$QUIET_MODE" == true ]]; then
        export LOG_LEVEL="WARNING"
    elif [[ "$VERBOSE_MODE" == true ]]; then
        export LOG_LEVEL="DEBUG"
    else
        export LOG_LEVEL="INFO"
    fi

    # Handle early-exit commands
    if [[ "$SHOW_HELP" == true ]]; then
        print_usage
        exit 0
    fi

    if [[ "$SHOW_VERSION" == true ]]; then
        print_version
        exit 0
    fi

    if [[ "$LIST_PHASES" == true ]]; then
        source "$LIB_DIR/colors.sh" 2>/dev/null || true
        source "$CONFIG_DIR/variables.sh" 2>&1 | grep -v "readonly variable" >&2 || true
        list_phases
        exit 0
    fi

    if [[ -n "$SHOW_PHASE_INFO_NUM" ]]; then
        source "$LIB_DIR/colors.sh" 2>/dev/null || true
        source "$CONFIG_DIR/variables.sh" 2>&1 | grep -v "readonly variable" >&2 || true
        show_phase_info "$SHOW_PHASE_INFO_NUM"
        exit 0
    fi

    assert_non_root_entrypoint

    # Phase 1: Setup environment, acquire lock, preflight checks
    setup_environment

    if [[ "$FLAKE_FIRST_MODE" == true ]]; then
        if run_flake_first_deployment; then
            # Keep post-deploy behavior consistent with legacy mode so AI stack
            # startup, rollback checks, and health checks still run.
            run_post_deployment
            exit $?
        fi
        exit 1
    fi

    # Phase 2: Execute deployment phases (1-9 + optional AI phases)
    run_deployment_phases

    # Phase 3: Post-deployment tasks (rollback test, AI stack, health check)
    run_post_deployment
}

# ============================================================================
# SCRIPT EXECUTION
# ============================================================================

# Run main function
main "$@"
