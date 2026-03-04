#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

FLAKE_REF="${FLAKE_REF:-.}"
NIXOS_TARGET="${NIXOS_TARGET:-nixos-ai-dev}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --flake-ref)
      FLAKE_REF="${2:?missing value for --flake-ref}"
      shift 2
      ;;
    --nixos-target)
      NIXOS_TARGET="${2:?missing value for --nixos-target}"
      shift 2
      ;;
    *)
      echo "check-dryrun-failure-modes: unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

if [[ -z "${FLAKE_REF}" ]]; then
  FLAKE_REF="."
fi

log() {
  printf '[check-dryrun-failure-modes] %s\n' "$*"
}

die() {
  log "FAIL: $*"
  exit 1
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "missing required command: $1"
}

need_cmd nix
need_cmd jq
need_cmd bash

cfg_ref="${FLAKE_REF}#nixosConfigurations.\"${NIXOS_TARGET}\".config"

nix_raw() {
  local expr="$1"
  nix --extra-experimental-features 'nix-command flakes' eval --raw "${cfg_ref}.${expr}" 2>/dev/null
}

nix_json() {
  local expr="$1"
  nix --extra-experimental-features 'nix-command flakes' eval --json "${cfg_ref}.${expr}" 2>/dev/null
}

assert_prefix() {
  local value="$1"
  local prefix="$2"
  local label="$3"
  [[ "${value}" == "${prefix}"* ]] || die "${label} must start with ${prefix} (got: ${value})"
}

assert_file_in_execstart() {
  local execstart="$1"
  local wanted="$2"
  [[ " ${execstart} " == *" ${wanted} "* ]] || die "ExecStart missing expected script path: ${wanted}"
  [[ -f "${wanted}" ]] || die "missing script referenced by ExecStart: ${wanted}"
}

assert_path_contains_pkg() {
  local path_json="$1"
  local pkg_pattern="$2"
  local label="$3"
  echo "${path_json}" | jq -e --arg re "${pkg_pattern}" 'map(test($re)) | any' >/dev/null \
    || die "${label} missing package matching ${pkg_pattern}"
}

log "Checking unit working directories"
npm_wd="$(nix_raw 'systemd.services.ai-npm-security-monitor.serviceConfig.WorkingDirectory')"
post_wd="$(nix_raw 'systemd.services.ai-post-deploy-converge.serviceConfig.WorkingDirectory')"
assert_prefix "${npm_wd}" "/var/lib/" "ai-npm-security-monitor WorkingDirectory"
assert_prefix "${post_wd}" "/var/lib/" "ai-post-deploy-converge WorkingDirectory"

log "Checking service executable wiring"
npm_exec="$(nix_raw 'systemd.services.ai-npm-security-monitor.serviceConfig.ExecStart')"
post_exec="$(nix_raw 'systemd.services.ai-post-deploy-converge.serviceConfig.ExecStart')"
assert_file_in_execstart "${npm_exec}" "${ROOT_DIR}/scripts/npm-security-monitor.sh"
assert_file_in_execstart "${post_exec}" "${ROOT_DIR}/scripts/post-deploy-converge.sh"

log "Checking package dependencies for monitored services"
npm_path_json="$(nix_json 'systemd.services.ai-npm-security-monitor.path')"
post_path_json="$(nix_json 'systemd.services.ai-post-deploy-converge.path')"
assert_path_contains_pkg "${npm_path_json}" 'jq-[0-9]' 'ai-npm-security-monitor path'
assert_path_contains_pkg "${npm_path_json}" 'bash' 'ai-npm-security-monitor path'
assert_path_contains_pkg "${post_path_json}" 'jq-[0-9]' 'ai-post-deploy-converge path'
assert_path_contains_pkg "${post_path_json}" 'python3-' 'ai-post-deploy-converge path'

log "Checking tmpfiles coverage for writable outputs"
tmpfiles_json="$(nix_json 'systemd.tmpfiles.rules')"
echo "${tmpfiles_json}" | jq -e 'any(.[]; contains("/security/npm"))' >/dev/null \
  || die "systemd.tmpfiles.rules missing /security/npm directory declaration"
echo "${tmpfiles_json}" | jq -e 'any(.[]; contains("/hybrid"))' >/dev/null \
  || die "systemd.tmpfiles.rules missing /hybrid directory declaration"

log "PASS: known dry-run failure modes validated"
