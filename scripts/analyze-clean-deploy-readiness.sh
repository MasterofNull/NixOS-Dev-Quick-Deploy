#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

HOST_NAME="$(hostname -s 2>/dev/null || hostname)"
PROFILE="ai-dev"
FLAKE_REF="path:${REPO_ROOT}"
CHECK_UPDATE_LOCK=false
NIX_EVAL_TIMEOUT_SECONDS="${NIX_EVAL_TIMEOUT_SECONDS:-20}"
HOST_EXPLICIT=false

FAIL_COUNT=0
WARN_COUNT=0
PASS_COUNT=0

usage() {
  cat <<'USAGE'
Usage: ./scripts/analyze-clean-deploy-readiness.sh [options]

Analyze whether the current host is ready for a clean flake-first deployment.

Options:
  --host NAME         Hostname target (default: current host)
  --profile NAME      Profile target (default: ai-dev)
  --flake-ref REF     Flake ref to analyze (default: path:<repo-root>)
  --update-lock       Include update-lock network/git dependency checks
  -h, --help          Show this help
USAGE
}

log_section() {
  printf '\n[readiness] %s\n' "$1"
}

pass() {
  PASS_COUNT=$((PASS_COUNT + 1))
  printf '[PASS] %s\n' "$1"
}

warn() {
  WARN_COUNT=$((WARN_COUNT + 1))
  printf '[WARN] %s\n' "$1"
}

fail() {
  FAIL_COUNT=$((FAIL_COUNT + 1))
  printf '[FAIL] %s\n' "$1"
}

need_cmd() {
  local cmd="$1"
  local message="$2"
  if command -v "$cmd" >/dev/null 2>&1; then
    pass "$message"
  else
    fail "$message (missing: ${cmd})"
  fi
}

check_optional_cmd() {
  local cmd="$1"
  local present_msg="$2"
  local missing_msg="$3"
  if command -v "$cmd" >/dev/null 2>&1; then
    pass "$present_msg"
  else
    warn "$missing_msg"
  fi
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
    printf '[readiness] Host %s not found in flake; using discovered host %s
' "$HOST_NAME" "${detected_hosts[0]}"
    HOST_NAME="${detected_hosts[0]}"
  fi
}

check_account_lock_state() {
  local target_user="${SUDO_USER:-${USER:-$(id -un)}}"
  local status_line status_code

  if ! command -v passwd >/dev/null 2>&1; then
    warn "Could not inspect account lock state (passwd command missing)."
    return 0
  fi

  status_line="$(passwd -S "$target_user" 2>/dev/null || true)"
  if [[ -z "$status_line" ]]; then
    warn "Could not inspect account lock state for '${target_user}'."
    return 0
  fi

  status_code="$(printf '%s\n' "$status_line" | awk '{print $2}')"
  if [[ "$status_code" == "L" ]]; then
    if [[ "$target_user" == "root" ]]; then
      warn "Root account is locked by policy on this host; continuing (non-interactive root login commonly disabled)."
    else
      fail "Primary operator account '${target_user}' is locked."
    fi
  else
    pass "Primary operator account '${target_user}' is not locked (${status_code:-unknown})."
  fi
}

check_host_paths() {
  local flake_path host_dir host_default host_facts

  flake_path="$(resolve_local_flake_path "$FLAKE_REF")"
  if [[ -z "$flake_path" ]]; then
    warn "Non-local flake ref '${FLAKE_REF}' detected; local path checks skipped."
    return 0
  fi

  if [[ ! -d "$flake_path" ]]; then
    fail "Flake path does not exist: ${flake_path}"
    return 0
  fi

  if [[ -r "${flake_path}/flake.nix" ]]; then
    pass "flake.nix is readable."
  else
    fail "flake.nix is missing or unreadable."
  fi

  host_dir="${flake_path}/nix/hosts/${HOST_NAME}"
  host_default="${host_dir}/default.nix"
  host_facts="${host_dir}/facts.nix"

  if [[ -d "$host_dir" ]]; then
    pass "Host directory exists: nix/hosts/${HOST_NAME}"
  else
    warn "Host directory missing: nix/hosts/${HOST_NAME} (will be scaffolded by discovery)."
  fi

  if [[ -f "$host_default" ]]; then
    pass "Host default module present: nix/hosts/${HOST_NAME}/default.nix"
  else
    warn "Host default module missing: nix/hosts/${HOST_NAME}/default.nix (discovery will create)."
  fi

  if [[ -e "$host_facts" ]]; then
    if [[ -r "$host_facts" ]]; then
      pass "Host facts file is readable: nix/hosts/${HOST_NAME}/facts.nix"
    else
      fail "Host facts file exists but is unreadable: nix/hosts/${HOST_NAME}/facts.nix"
    fi
  else
    warn "Host facts file missing: nix/hosts/${HOST_NAME}/facts.nix (discovery will create)."
  fi
}

check_eval_capability() {
  local expr output
  expr="${FLAKE_REF}#nixosConfigurations.\"${HOST_NAME}-${PROFILE}\".config.system.stateVersion"
  if command -v timeout >/dev/null 2>&1; then
    output="$(timeout "${NIX_EVAL_TIMEOUT_SECONDS}" nix eval --raw "$expr" 2>/dev/null || true)"
  else
    output="$(nix eval --raw "$expr" 2>/dev/null || true)"
  fi
  if [[ -n "$output" ]]; then
    pass "Nix can evaluate target '${HOST_NAME}-${PROFILE}' (stateVersion=${output})."
  else
    warn "Nix evaluation for '${HOST_NAME}-${PROFILE}' failed in readiness check (may be expected before first discovery)."
  fi
}

check_update_lock_dependencies() {
  if [[ "$CHECK_UPDATE_LOCK" != true ]]; then
    return 0
  fi

  log_section "Update-Lock Dependency Checks"

  check_optional_cmd \
    "git" \
    "git is installed (native flake lock updates available)." \
    "git is not installed (deploy-clean will rely on nixpkgs#git fallback)."

  if command -v getent >/dev/null 2>&1 && getent hosts github.com >/dev/null 2>&1; then
    pass "DNS lookup for github.com succeeded."
  else
    warn "DNS lookup for github.com failed (update-lock may fail without connectivity)."
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host)
      HOST_NAME="${2:?missing value for --host}"
      HOST_EXPLICIT=true
      shift 2
      ;;
    --profile)
      PROFILE="${2:?missing value for --profile}"
      shift 2
      ;;
    --flake-ref)
      FLAKE_REF="${2:?missing value for --flake-ref}"
      shift 2
      ;;
    --update-lock)
      CHECK_UPDATE_LOCK=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf '[readiness] ERROR: Unknown argument: %s\n' "$1" >&2
      exit 1
      ;;
  esac
done

resolve_host_from_flake_if_needed

log_section "Core Commands"
need_cmd "nix" "nix command available."
need_cmd "nixos-rebuild" "nixos-rebuild available."

if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
  pass "Running as root (sudo is not required in this context)."
else
  need_cmd "sudo" "sudo available for privileged deployment steps."
fi

log_section "Optional Bootstrap Commands"
check_optional_cmd "home-manager" "home-manager command available." "home-manager not installed (deploy-clean fallback build path will be used)."
check_optional_cmd "flatpak" "flatpak command available." "flatpak not installed (profile sync may be skipped/non-critical)."
check_optional_cmd "lspci" "lspci available for richer GPU detection." "lspci missing (discovery will use fallback detection)."
check_optional_cmd "lsblk" "lsblk available for richer storage detection." "lsblk missing (storage type defaults may be less accurate)."
check_optional_cmd "jq" "jq available for optional tooling/diagnostics." "jq missing (non-core helper scripts may be limited)."

log_section "Host + Flake Structure"
check_host_paths

log_section "Account Safety"
check_account_lock_state

log_section "Flake Evaluation Capability"
check_eval_capability

check_update_lock_dependencies

printf '\n[readiness] Summary: %d pass, %d warn, %d fail\n' "$PASS_COUNT" "$WARN_COUNT" "$FAIL_COUNT"

if (( FAIL_COUNT > 0 )); then
  cat <<'REMEDIATION'

[readiness] Suggested remediation:
  1) If account is locked:
     sudo usermod -U "$USER" && sudo passwd "$USER"
  2) If facts file is unreadable:
     sudo chown "$USER:$(id -gn)" nix/hosts/<host>/facts.nix && sudo chmod 0644 nix/hosts/<host>/facts.nix
  3) Re-run analysis:
     ./scripts/deploy-clean.sh --host <host> --profile <profile> --analyze-only
REMEDIATION
  exit 1
fi

exit 0
