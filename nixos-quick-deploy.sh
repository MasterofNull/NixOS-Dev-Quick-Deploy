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
ANALYZE_ONLY=false
SKIP_ROADMAP_VERIFICATION=false
RECOVERY_MODE=false
ALLOW_PREVIOUS_BOOT_FSCK_FAILURE=false
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
  --skip-roadmap-verification
                          Skip flake-first roadmap completion verification preflight
  --restore-generated-files
                          Restore generated host files on exit (temporary run projection)
  --persist-generated-files
                          Persist generated host files after run (declarative update)
  -h, --help              Show this help

Environment overrides:
  ALLOW_GUI_SWITCH=true     Allow live switch from graphical session (default)
  AUTO_GUI_SWITCH_FALLBACK=false
                            Keep switch mode in graphical sessions (default)
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
  ALLOW_ROOT_DEPLOY=true    Allow running this script as root (not recommended)
  BOOT_ESP_MIN_FREE_MB=128  Override minimum required free space on ESP
  RESTORE_GENERATED_REPO_FILES=auto
                            auto: restore only for --analyze-only runs
                            true: always restore generated files on exit
                            false: persist generated files after run
USAGE
}

log() {
  printf '[clean-deploy] %s\n' "$*"
}

die() {
  printf '[clean-deploy] ERROR: %s\n' "$*" >&2
  exit 1
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

  if [[ -x "${REPO_ROOT}/scripts/git-safe.sh" ]]; then
    "${REPO_ROOT}/scripts/git-safe.sh" "$@"
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

  local verifier="${REPO_ROOT}/scripts/verify-flake-first-roadmap-completion.sh"
  if [[ ! -x "$verifier" ]]; then
    log "Roadmap-completion verifier missing/not executable (${verifier}); skipping verification."
    return 0
  fi

  log "Running roadmap-completion verification preflight"
  "$verifier"
}

run_readiness_analysis() {
  local analyzer="${REPO_ROOT}/scripts/analyze-clean-deploy-readiness.sh"
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

generate_secret_value() {
  local kind="${1:-token}"
  local target_len generated
  case "${kind}" in
    password) target_len=32 ;;
    *) target_len=48 ;;
  esac

  # Prefer openssl when available, but fall back to python3 for minimal hosts.
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -base64 48 | tr -d '\n' | tr -d '/+=' | cut -c1-"${target_len}"
    return 0
  fi

  if command -v python3 >/dev/null 2>&1; then
    generated="$(
      python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(64))
PY
    )"
    printf '%s\n' "${generated}" | tr -d '\n' | cut -c1-"${target_len}"
    return 0
  fi

  die "Unable to generate secrets automatically: neither 'openssl' nor 'python3' is available."
}

secret_value_is_safe_yaml_scalar() {
  local value="${1:-}"
  [[ -n "${value}" ]] || return 1
  [[ "${value}" =~ ^[A-Za-z0-9._~+=-]+$ ]]
}

read_secret_value() {
  local label="${1:?missing label}"
  local value confirm
  while true; do
    read -r -s -p "${label}: " value
    printf '\n'
    [[ -n "${value}" ]] || { log "Value cannot be empty."; continue; }
    if ! secret_value_is_safe_yaml_scalar "${value}"; then
      log "Only characters [A-Za-z0-9._~+=-] are supported for interactive secrets."
      continue
    fi
    read -r -s -p "Confirm ${label}: " confirm
    printf '\n'
    [[ "${value}" == "${confirm}" ]] || { log "Values did not match. Try again."; continue; }
    printf '%s\n' "${value}"
    return 0
  done
}

create_or_update_host_deploy_options_local() {
  local host_dir="${1:?missing host dir}"
  local primary_user="${2:?missing primary user}"
  local secrets_file="${3:?missing secrets file}"
  local target="${host_dir}/deploy-options.local.nix"
  local age_key_file="/home/${primary_user}/.config/sops/age/keys.txt"
  local escaped_secrets_file escaped_age_key_file

  escaped_secrets_file="$(nix_escape_string "${secrets_file}")"
  escaped_age_key_file="$(nix_escape_string "${age_key_file}")"

  cat > "${target}" <<EOF
{ lib, ... }:
{
  mySystem.secrets.enable = lib.mkForce true;
  mySystem.secrets.sopsFile = lib.mkForce "${escaped_secrets_file}";
  mySystem.secrets.ageKeyFile = lib.mkForce "${escaped_age_key_file}";
}
EOF
  log "Updated declarative secrets override: ${target}"
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
    secrets_enabled="false"
    log "AI secrets bootstrap fallback: unable to evaluate secrets role; defaulting to disabled."
  fi
  log "AI secrets bootstrap check: aiStack=${ai_enabled}, secrets=${secrets_enabled}"

  if [[ "${ai_enabled}" != "true" && "${FORCE_AI_SECRETS_BOOTSTRAP}" != "true" ]]; then
    AI_SECRETS_BOOTSTRAP_STATUS="skipped:ai-stack-disabled"
    return 0
  fi
  if [[ "${secrets_enabled}" == "true" && "${FORCE_AI_SECRETS_BOOTSTRAP}" != "true" ]]; then
    log "AI stack secrets already enabled; skipping bootstrap prompt."
    AI_SECRETS_BOOTSTRAP_STATUS="skipped:already-enabled"
    return 0
  fi

  if ! is_interactive_tty; then
    die "AI stack is enabled but secrets are disabled and no interactive TTY is available. Rerun interactively to bootstrap secrets or preconfigure mySystem.secrets in deploy-options.local.nix."
  fi

  local choice host_dir secrets_root secrets_file sops_cfg age_key_dir age_key_file public_key
  local legacy_secrets_file legacy_sops_cfg
  local aidb_key_name hybrid_key_name embeddings_key_name postgres_key_name redis_key_name
  local aidb_api_key hybrid_api_key embeddings_api_key postgres_password redis_password
  local plain_tmp summary_tmp

  read -r -p "AI stack secrets are disabled for ${NIXOS_TARGET}. Bootstrap now? [Y/n]: " choice
  choice="${choice:-Y}"
  if [[ ! "${choice}" =~ ^[Yy]$ && "${FORCE_AI_SECRETS_BOOTSTRAP}" != "true" ]]; then
    die "AI stack secrets are required when aiStack is enabled. Bootstrap was declined."
  fi

  require_command sops
  require_command age-keygen

  host_dir="${REPO_ROOT}/nix/hosts/${HOST_NAME}"
  secrets_root="/home/${PRIMARY_USER}/.local/share/nixos-quick-deploy/secrets/${HOST_NAME}"
  secrets_file="${secrets_root}/secrets.sops.yaml"
  sops_cfg="${secrets_root}/.sops.yaml"
  legacy_secrets_file="${host_dir}/secrets.sops.yaml"
  legacy_sops_cfg="${host_dir}/.sops.yaml"
  age_key_dir="/home/${PRIMARY_USER}/.config/sops/age"
  age_key_file="${age_key_dir}/keys.txt"

  aidb_key_name="$(nix_eval_raw_safe "${FLAKE_REF}#nixosConfigurations.\"${NIXOS_TARGET}\".config.mySystem.secrets.names.aidbApiKey" 2>/dev/null || echo "aidb_api_key")"
  hybrid_key_name="$(nix_eval_raw_safe "${FLAKE_REF}#nixosConfigurations.\"${NIXOS_TARGET}\".config.mySystem.secrets.names.hybridApiKey" 2>/dev/null || echo "hybrid_coordinator_api_key")"
  embeddings_key_name="$(nix_eval_raw_safe "${FLAKE_REF}#nixosConfigurations.\"${NIXOS_TARGET}\".config.mySystem.secrets.names.embeddingsApiKey" 2>/dev/null || echo "embeddings_api_key")"
  postgres_key_name="$(nix_eval_raw_safe "${FLAKE_REF}#nixosConfigurations.\"${NIXOS_TARGET}\".config.mySystem.secrets.names.postgresPassword" 2>/dev/null || echo "postgres_password")"
  redis_key_name="$(nix_eval_raw_safe "${FLAKE_REF}#nixosConfigurations.\"${NIXOS_TARGET}\".config.mySystem.secrets.names.redisPassword" 2>/dev/null || echo "redis_password")"

  install -d -m 0700 "${secrets_root}" 2>/dev/null || true
  if [[ ! -d "${secrets_root}" ]]; then
    run_privileged install -d -m 0700 "${secrets_root}"
  fi
  run_privileged chown "${PRIMARY_USER}:$(id -gn "${PRIMARY_USER}" 2>/dev/null || echo "${PRIMARY_USER}")" "${secrets_root}" 2>/dev/null || true

  # Migrate old repo-local secrets to strict external storage (one-time).
  if [[ ! -s "${secrets_file}" && -s "${legacy_secrets_file}" ]]; then
    cp "${legacy_secrets_file}" "${secrets_file}"
    chmod 0600 "${secrets_file}"
    log "Migrated legacy repo-local secrets to ${secrets_file}"
  fi
  if [[ ! -f "${sops_cfg}" && -f "${legacy_sops_cfg}" ]]; then
    cp "${legacy_sops_cfg}" "${sops_cfg}"
    chmod 0600 "${sops_cfg}"
  fi
  # Enforce strict zero-secrets-in-repo behavior.
  rm -f "${legacy_secrets_file}" "${legacy_sops_cfg}" >/dev/null 2>&1 || true

  if [[ -f "${secrets_file}" ]] && SOPS_AGE_KEY_FILE="${age_key_file}" sops -d "${secrets_file}" >/dev/null 2>&1; then
    create_or_update_host_deploy_options_local "${host_dir}" "${PRIMARY_USER}" "${secrets_file}"
    log "Existing encrypted secrets file detected (${secrets_file}); bootstrap skipped."
    AI_SECRETS_BOOTSTRAP_STATUS="skipped:existing-secrets-file"
    return 0
  fi

  local primary_group
  primary_group="$(id -gn "${PRIMARY_USER}" 2>/dev/null || echo "${PRIMARY_USER}")"

  # Prefer a user-owned age key directory so interactive sops usage works.
  install -d -m 0700 "${age_key_dir}" 2>/dev/null || true
  if [[ ! -d "${age_key_dir}" ]]; then
    run_privileged install -d -m 0700 "${age_key_dir}"
  fi
  if [[ ! -w "${age_key_dir}" || ! -x "${age_key_dir}" ]]; then
    run_privileged chown "${PRIMARY_USER}:${primary_group}" "${age_key_dir}" 2>/dev/null || true
    run_privileged chmod 0700 "${age_key_dir}" 2>/dev/null || true
  fi

  if run_privileged test -e "${age_key_file}"; then
    if ! run_privileged test -f "${age_key_file}"; then
      die "AGE key path exists but is not a regular file: ${age_key_file}"
    fi
    run_privileged chown "${PRIMARY_USER}:${primary_group}" "${age_key_file}" 2>/dev/null || true
    run_privileged chmod 0600 "${age_key_file}" 2>/dev/null || true
    log "Using existing age key for sops at ${age_key_file}"
  else
    log "Generating age key for sops at ${age_key_file}"
    age-keygen -o "${age_key_file}" >/dev/null
    run_privileged chown "${PRIMARY_USER}:${primary_group}" "${age_key_file}" 2>/dev/null || true
    chmod 0600 "${age_key_file}" 2>/dev/null || run_privileged chmod 0600 "${age_key_file}"
  fi

  public_key="$(run_privileged awk '/^# public key:/ {print $4; exit}' "${age_key_file}" 2>/dev/null || true)"
  [[ -n "${public_key}" ]] || die "Unable to read AGE public key from ${age_key_file}"

  if [[ ! -f "${sops_cfg}" ]]; then
    cat > "${sops_cfg}" <<EOF
creation_rules:
  - path_regex: .*secrets\\.sops\\.yaml$
    age: >-
      ${public_key}
EOF
    chmod 0600 "${sops_cfg}"
    log "Created SOPS config: ${sops_cfg}"
  fi

  printf 'Select secrets input mode:\n'
  printf '  1) Enter my own values\n'
  printf '  2) Auto-generate secure values\n'
  read -r -p "Choice [1/2, default 1]: " choice
  choice="${choice:-1}"

  case "${choice}" in
    1)
      local shared_choice shared_secret
      read -r -p "Use one shared secret for all AI stack keys/passwords? [y/N]: " shared_choice
      shared_choice="${shared_choice:-N}"
      if [[ "${shared_choice}" =~ ^[Yy]$ ]]; then
        shared_secret="$(read_secret_value "Shared AI stack secret")"
        aidb_api_key="${shared_secret}"
        hybrid_api_key="${shared_secret}"
        embeddings_api_key="${shared_secret}"
        postgres_password="${shared_secret}"
        redis_password="${shared_secret}"
      else
        aidb_api_key="$(read_secret_value "AIDB API key")"
        hybrid_api_key="$(read_secret_value "Hybrid coordinator API key")"
        embeddings_api_key="$(read_secret_value "Embeddings API key")"
        postgres_password="$(read_secret_value "Postgres password")"
        redis_password="$(read_secret_value "Redis password")"
      fi
      ;;
    2)
      aidb_api_key="$(generate_secret_value token)"
      hybrid_api_key="$(generate_secret_value token)"
      embeddings_api_key="$(generate_secret_value token)"
      postgres_password="$(generate_secret_value password)"
      redis_password="$(generate_secret_value password)"
      ;;
    *)
      die "Invalid secrets mode '${choice}'. Expected 1 or 2."
      ;;
  esac

  plain_tmp="$(mktemp)"
  summary_tmp="$(mktemp)"
  chmod 0600 "${plain_tmp}" "${summary_tmp}"

  AIDB_KEY_NAME="${aidb_key_name}" \
  HYBRID_KEY_NAME="${hybrid_key_name}" \
  EMBEDDINGS_KEY_NAME="${embeddings_key_name}" \
  POSTGRES_KEY_NAME="${postgres_key_name}" \
  REDIS_KEY_NAME="${redis_key_name}" \
  AIDB_API_KEY="${aidb_api_key}" \
  HYBRID_API_KEY="${hybrid_api_key}" \
  EMBEDDINGS_API_KEY="${embeddings_api_key}" \
  POSTGRES_PASSWORD="${postgres_password}" \
  REDIS_PASSWORD="${redis_password}" \
  python3 - <<'PY' > "${plain_tmp}"
import json
import os

payload = {
    os.environ["AIDB_KEY_NAME"]: os.environ["AIDB_API_KEY"],
    os.environ["HYBRID_KEY_NAME"]: os.environ["HYBRID_API_KEY"],
    os.environ["EMBEDDINGS_KEY_NAME"]: os.environ["EMBEDDINGS_API_KEY"],
    os.environ["POSTGRES_KEY_NAME"]: os.environ["POSTGRES_PASSWORD"],
    os.environ["REDIS_KEY_NAME"]: os.environ["REDIS_PASSWORD"],
}
print(json.dumps(payload, ensure_ascii=True))
PY

  # Encrypt temp file using the target filename for config/type matching.
  SOPS_AGE_KEY_FILE="${age_key_file}" sops \
    --encrypt \
    --age "${public_key}" \
    --input-type json \
    --output-type yaml \
    --filename-override "secrets.sops.yaml" \
    "${plain_tmp}" > "${secrets_file}"
  chmod 0600 "${secrets_file}"
  rm -f "${plain_tmp}"

  cat > "${summary_tmp}" <<EOF
AI stack initial secrets for ${NIXOS_TARGET} (${HOST_NAME})
Generated on: $(date -Is)

${aidb_key_name}=${aidb_api_key}
${hybrid_key_name}=${hybrid_api_key}
${embeddings_key_name}=${embeddings_api_key}
${postgres_key_name}=${postgres_password}
${redis_key_name}=${redis_password}
EOF
  run_privileged install -m 0600 "${summary_tmp}" "/root/ai-stack-initial-secrets-${HOST_NAME}.txt"
  rm -f "${summary_tmp}"

  create_or_update_host_deploy_options_local "${host_dir}" "${PRIMARY_USER}" "${secrets_file}"
  rm -f "${legacy_secrets_file}" "${legacy_sops_cfg}" >/dev/null 2>&1 || true

  printf '\n[clean-deploy] Initial AI stack secrets have been configured.\n'
  printf '[clean-deploy] Encrypted secrets file: %s\n' "${secrets_file}"
  printf '[clean-deploy] One-time recovery copy (root-only): /root/ai-stack-initial-secrets-%s.txt\n' "${HOST_NAME}"
  printf '[clean-deploy] Record these values now. They will not be printed again.\n'
  if [[ "${choice}" == "2" ]]; then
    printf '[clean-deploy] Auto-generated values:\n'
    printf '  %s=%s\n' "${aidb_key_name}" "${aidb_api_key}"
    printf '  %s=%s\n' "${hybrid_key_name}" "${hybrid_api_key}"
    printf '  %s=%s\n' "${embeddings_key_name}" "${embeddings_api_key}"
    printf '  %s=%s\n' "${postgres_key_name}" "${postgres_password}"
    printf '  %s=%s\n' "${redis_key_name}" "${redis_password}"
  fi
  read -r -p "Press Enter after you have securely recorded these secrets. " _
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
  run_privileged awk -F: -v user="$account" '$1 == user { print $2; found = 1; exit } END { if (!found) exit 1 }' /etc/shadow 2>/dev/null
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
  local git_cmd="git"
  if [[ "${EUID:-$(id -u)}" -eq 0 && -n "${PRIMARY_USER:-}" ]]; then
    git_cmd="sudo -u ${PRIMARY_USER} git"
  fi
  if [[ -n "$git_name" ]]; then
    $git_cmd config --global user.name "$git_name" || true
  fi
  if [[ -n "$git_email" ]]; then
    $git_cmd config --global user.email "$git_email" || true
  fi

  if [[ -n "$git_helper" ]]; then
    helper_block=$'    extraConfig = {
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

trap cleanup_on_exit EXIT
trap 'on_unexpected_error "$?" "${LINENO}" "${BASH_COMMAND}"' ERR

assert_non_root_entrypoint

if [[ "${RECOVERY_MODE}" == true ]]; then
  ALLOW_PREVIOUS_BOOT_FSCK_FAILURE=true
  if [[ "$MODE" == "switch" ]]; then
    log "Recovery mode is active with switch mode (no reboot required). If switch hangs on your hardware, rerun with --boot."
  fi
fi

require_command nix
require_command nixos-rebuild
enable_flakes_runtime
ensure_flake_visible_to_nix "${FLAKE_REF}"
resolve_host_from_flake_if_needed
snapshot_generated_repo_files
persist_home_git_credentials_declarative
run_roadmap_completion_verification
run_readiness_analysis

if [[ "${ANALYZE_ONLY}" == true ]]; then
  log "Readiness analysis complete (--analyze-only)."
  exit 0
fi

if [[ "$UPDATE_FLAKE_LOCK" == true ]]; then
  update_flake_lock "${FLAKE_REF}"
fi

ensure_host_facts_access
if [[ "$RUN_DISCOVERY" == true ]]; then
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
    "${REPO_ROOT}/scripts/discover-system-facts.sh"
  else
    HOSTNAME_OVERRIDE="${HOST_NAME}" \
    PRIMARY_USER_OVERRIDE="${PRIMARY_USER}" \
    PROFILE_OVERRIDE="${PROFILE}" \
    "${local_ai_env[@]}" \
    "${REPO_ROOT}/scripts/discover-system-facts.sh"
  fi
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
  log "Running dry build"
  if [[ "${SKIP_SYSTEM_SWITCH}" == false ]]; then
    run_privileged nixos-rebuild dry-build --flake "${FLAKE_REF}#${NIXOS_TARGET}"
  else
    log "Skipping system dry-build (--skip-system-switch)"
  fi
  if [[ "${SKIP_HOME_SWITCH}" == false ]]; then
    home_build "${HM_TARGET}"
  else
    log "Skipping Home Manager build (--skip-home-switch)"
  fi
  log "Dry build complete"
  exit 0
fi

if [[ "$MODE" == "boot" ]]; then
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

  if [[ "$RUN_FLATPAK_SYNC" == true && -x "${REPO_ROOT}/scripts/sync-flatpak-profile.sh" ]]; then
    log "Syncing Flatpak apps for profile '${PROFILE}' (boot mode, system scope)"
    if "${REPO_ROOT}/scripts/sync-flatpak-profile.sh" --flake-ref "${FLAKE_REF}" --target "${NIXOS_TARGET}" --scope system; then
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
  log "Switching system configuration"
  run_privileged nixos-rebuild switch --flake "${FLAKE_REF}#${NIXOS_TARGET}"
else
  log "Skipping system switch (--skip-system-switch)"
fi

if [[ "${SKIP_HOME_SWITCH}" == false ]]; then
  log "Switching Home Manager configuration"
  home_switch "${HM_TARGET}"
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

if [[ "$RUN_FLATPAK_SYNC" == true && -x "${REPO_ROOT}/scripts/sync-flatpak-profile.sh" ]]; then
  log "Syncing Flatpak apps for profile '${PROFILE}' (system scope)"
  if "${REPO_ROOT}/scripts/sync-flatpak-profile.sh" --flake-ref "${FLAKE_REF}" --target "${NIXOS_TARGET}" --scope system; then
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

if [[ "$RUN_HEALTH_CHECK" == true && -x "${REPO_ROOT}/scripts/system-health-check.sh" ]]; then
  log "Running post-deploy health check"
  if "${REPO_ROOT}/scripts/system-health-check.sh" --detailed; then
    log "Post-deploy health check passed"
  else
    log "Post-deploy health check reported issues (non-critical)"
  fi
fi

if [[ -x "${REPO_ROOT}/scripts/compare-installed-vs-intended.sh" ]]; then
  log "Running installed-vs-intended package comparison"
  if "${REPO_ROOT}/scripts/compare-installed-vs-intended.sh" --host "${HOST_NAME}" --profile "${PROFILE}" --flake-ref "${FLAKE_REF}"; then
    log "Installed-vs-intended comparison passed"
  else
    log "Installed-vs-intended comparison reported gaps (non-critical)"
  fi
fi

# ---- AI MCP stack post-flight ------------------------------------------------
# Verify TCP connectivity to Redis/Qdrant/Postgres and HTTP /health endpoints
# for all MCP services. Runs --optional to also report aider-wrapper and
# supplementary services. Non-blocking: issues are logged but do not abort.
if [[ "$RUN_HEALTH_CHECK" == true && -x "${REPO_ROOT}/scripts/check-mcp-health.sh" ]]; then
  log "Running AI stack MCP health check"
  if "${REPO_ROOT}/scripts/check-mcp-health.sh" --optional; then
    log "AI MCP health check passed"
  else
    log "AI MCP health check reported issues — check 'scripts/check-mcp-health.sh --optional' for details (non-critical)"
  fi
fi

log "Clean deployment complete"
