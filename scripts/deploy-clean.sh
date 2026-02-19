#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

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
HOME_MANAGER_BACKUP_EXTENSION="${HOME_MANAGER_BACKUP_EXTENSION:-backup}"
REQUIRE_HOME_MANAGER_CLI="${REQUIRE_HOME_MANAGER_CLI:-false}"
PREFER_NIX_RUN_HOME_MANAGER="${PREFER_NIX_RUN_HOME_MANAGER:-true}"
HOME_MANAGER_NIX_RUN_REF="${HOME_MANAGER_NIX_RUN_REF:-github:nix-community/home-manager/release-25.11#home-manager}"

AUTO_STAGED_FLAKE_PATH=""
# Tracks untracked files we temporarily add so Nix can evaluate local git flakes.
# We unstage them on exit to avoid leaving a dirty index that blocks `git pull --rebase`.
declare -a AUTO_STAGED_FLAKE_FILES=()

RESTORE_GENERATED_REPO_FILES="${RESTORE_GENERATED_REPO_FILES:-true}"
GENERATED_FILE_SNAPSHOT_DIR=""
declare -a GENERATED_FILE_SNAPSHOT_TARGETS=()

usage() {
  cat <<'USAGE'
Usage: ./scripts/deploy-clean.sh [options]

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
  --analyze-only          Run readiness analysis and exit (no build/switch)
  --skip-roadmap-verification
                          Skip flake-first roadmap completion verification preflight
  -h, --help              Show this help

Environment overrides:
  ALLOW_GUI_SWITCH=true     Allow live switch from graphical session (default)
  AUTO_GUI_SWITCH_FALLBACK=false
                            Keep switch mode in graphical sessions (default)
  HOME_MANAGER_BACKUP_EXTENSION=backup
                            Backup suffix used for Home Manager file collisions
  REQUIRE_HOME_MANAGER_CLI=false
                            Require home-manager command in PATH (disable fallback paths)
  PREFER_NIX_RUN_HOME_MANAGER=true
                            Try `nix run` home-manager before activation fallback when CLI missing
  HOME_MANAGER_NIX_RUN_REF=github:nix-community/home-manager/release-25.11#home-manager
                            Flake ref used for nix-run Home Manager fallback
  ALLOW_ROOT_DEPLOY=true    Allow running this script as root (not recommended)
  BOOT_ESP_MIN_FREE_MB=128  Override minimum required free space on ESP
  RESTORE_GENERATED_REPO_FILES=true
                            Restore generated host files (facts/home-deploy-options) on exit
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
    die "Do not run deploy-clean.sh as root/sudo. Run as your normal user; the script escalates only privileged steps. Override only if required: ALLOW_ROOT_DEPLOY=true."
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
      install -m 0644 "${GENERATED_FILE_SNAPSHOT_DIR}/${key}.snapshot" "${target}"
    else
      rm -f "${target}" >/dev/null 2>&1 || true
    fi
  done

  rm -rf "${GENERATED_FILE_SNAPSHOT_DIR}" >/dev/null 2>&1 || true
  GENERATED_FILE_SNAPSHOT_DIR=""
}

cleanup_on_exit() {
  cleanup_auto_staged_flake_files
  restore_generated_repo_files
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
        runtime_root_uuid="$(blkid -s UUID -o value "${runtime_root_real}" 2>/dev/null || true)"
        [[ -n "${runtime_root_uuid}" ]] && runtime_root_uuid_path="/dev/disk/by-uuid/${runtime_root_uuid}"
      fi
    fi
    runtime_root_fstype="$(findmnt -no FSTYPE / 2>/dev/null || true)"

    if [[ -n "${runtime_root_source}" && "${host_root_device}" != "${runtime_root_source}" && "${host_root_device}" != "${runtime_root_uuid_path}" ]]; then
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
  elif ! "${bootctl_cmd}" status >/dev/null 2>&1; then
    log "Bootloader preflight: bootctl status failed in current runtime; skipping strict bootloader checks."
    strict_bootloader_checks=false
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

  nix build "${FLAKE_REF}#homeConfigurations."${hm_target}".activationPackage"
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
  nix build --out-link "$out_link" "${FLAKE_REF}#homeConfigurations."${hm_target}".activationPackage"
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

  local escaped_name escaped_email escaped_helper target helper_block=""
  escaped_name="$(nix_escape_string "$git_name")"
  escaped_email="$(nix_escape_string "$git_email")"
  escaped_helper="$(nix_escape_string "$git_helper")"

  if [[ -n "$git_helper" ]]; then
    helper_block=$'    extraConfig = {
      credential.helper = lib.mkForce "'"${escaped_helper}"'";
    };
'
  fi

  target="${host_dir}/home-deploy-options.nix"

  cat > "$target" <<EOF
{ lib, ... }:
{
  programs.git = {
    enable = lib.mkDefault true;
    settings = {
      user.name = lib.mkForce "${escaped_name}";
      user.email = lib.mkForce "${escaped_email}";
    };
${helper_block}  };
}
EOF

  log "Updated declarative git identity: ${target}"
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
    --analyze-only)
      ANALYZE_ONLY=true
      shift
      ;;
    --skip-roadmap-verification)
      SKIP_ROADMAP_VERIFICATION=true
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

trap cleanup_on_exit EXIT

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

if [[ -z "${HM_TARGET_OVERRIDE}" ]] && ! nix_eval_raw_safe "${FLAKE_REF}#homeConfigurations.\"${HM_TARGET}\".config.home.username" >/dev/null 2>&1; then
  HM_TARGET="${PRIMARY_USER}"
fi

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
    log "Syncing Flatpak apps for profile '${PROFILE}' (boot mode)"
    if "${REPO_ROOT}/scripts/sync-flatpak-profile.sh" --flake-ref "${FLAKE_REF}" --target "${NIXOS_TARGET}"; then
      log "Flatpak profile sync complete"
    else
      die "Flatpak profile sync failed in boot mode; declarative app state is not converged."
    fi
  fi

  # npm AI CLI tools (boot mode)
  if [[ -x "${REPO_ROOT}/scripts/sync-npm-ai-tools.sh" ]]; then
    log "Syncing npm AI CLI tools (boot mode)"
    if "${REPO_ROOT}/scripts/sync-npm-ai-tools.sh"; then
      log "npm AI CLI tools sync complete"
    else
      log "npm AI CLI tools sync reported issues (non-critical)"
    fi
  fi

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
  log "Syncing Flatpak apps for profile '${PROFILE}'"
  if "${REPO_ROOT}/scripts/sync-flatpak-profile.sh" --flake-ref "${FLAKE_REF}" --target "${NIXOS_TARGET}"; then
    log "Flatpak profile sync complete"
  else
    die "Flatpak profile sync failed; declarative app state is not converged."
  fi
fi

# ---- npm AI CLI tools (flake-first replaces Phase 6) -----------------------
# In flake-first mode the legacy Phase 6 is skipped.  This sync step ensures
# npm-based AI wrappers, OpenSkills, and the Claude Code native binary are
# installed after the NixOS + Home Manager switch.
if [[ -x "${REPO_ROOT}/scripts/sync-npm-ai-tools.sh" ]]; then
  log "Syncing npm AI CLI tools"
  if "${REPO_ROOT}/scripts/sync-npm-ai-tools.sh"; then
    log "npm AI CLI tools sync complete"
  else
    log "npm AI CLI tools sync reported issues (non-critical)"
  fi
fi

# ---- K3s AI stack backend --------------------------------------------------
# When mySystem.aiStack.backend = "k3s" the declarative Nix config only installs
# the K3s binary; actual cluster bootstrap and workload deployment is handled by
# the phase-09 bash orchestration (too stateful/imperative for pure Nix).
# We check the evaluated config and delegate to the legacy phase scripts.
if [[ "${MODE}" != "build" ]]; then
  ai_backend_val=""
  if ai_backend_val="$(nix_eval_raw_safe \
      "${FLAKE_REF}#nixosConfigurations.${NIXOS_TARGET}.config.mySystem.aiStack.backend" \
      2>/dev/null || true)"; then
    true
  fi

  if [[ "${ai_backend_val}" == "k3s" ]]; then
    phase09_script="${REPO_ROOT}/phases/phase-09-k3s-portainer.sh"
    phase09_ai="${REPO_ROOT}/phases/phase-09-ai-stack-deployment.sh"
    if [[ -x "${phase09_script}" ]]; then
      log "AI stack backend=k3s: delegating to phase-09 K3s orchestration"
      # Source the main orchestrator to pick up the required lib/ functions,
      # then invoke the phase functions directly.
      # The main script sources lib/ on load; we source just enough to run phase 9.
      if [[ -x "${REPO_ROOT}/nixos-quick-deploy.sh" ]]; then
        RUN_AI_MODEL=true \
        SCRIPT_DIR="${REPO_ROOT}" \
        bash -c "source '${REPO_ROOT}/nixos-quick-deploy.sh' --phases-only 2>/dev/null || true; \
                 source '${phase09_script}'; phase_09_k3s_portainer 2>&1" \
          || log "Phase 09 K3s setup reported issues (check output above)"
        if [[ -x "${phase09_ai}" ]]; then
          RUN_AI_MODEL=true \
          SCRIPT_DIR="${REPO_ROOT}" \
          bash -c "source '${REPO_ROOT}/nixos-quick-deploy.sh' --phases-only 2>/dev/null || true; \
                   source '${phase09_ai}'; phase_09_ai_stack_deployment 2>&1" \
            || log "Phase 09 AI stack deployment reported issues (check output above)"
        fi
      else
        log "Cannot find nixos-quick-deploy.sh to source lib functions; skipping K3s orchestration."
        log "Run phases/phase-09-k3s-portainer.sh manually after deploy."
      fi
    else
      log "Phase 09 K3s script not found (${phase09_script}); skipping K3s orchestration."
    fi
  fi
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

log "Clean deployment complete"
