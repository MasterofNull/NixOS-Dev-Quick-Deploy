#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

MODE="fast"
FLAKE_REF="."
NIXOS_TARGET="nixos-ai-dev"

if [[ -t 1 ]]; then
  C_RESET='\033[0m'
  C_BOLD='\033[1m'
  C_DIM='\033[2m'
  C_RED='\033[31m'
  C_GREEN='\033[32m'
  C_YELLOW='\033[33m'
  C_BLUE='\033[34m'
else
  C_RESET=''
  C_BOLD=''
  C_DIM=''
  C_RED=''
  C_GREEN=''
  C_YELLOW=''
  C_BLUE=''
fi

usage() {
  cat <<USAGE
Usage: scripts/quick-deploy-lint.sh [options]

Options:
  --mode <fast|full>        fast: static + contract checks (default)
                            full: includes dry builds and preflight-only loop
  --flake-ref <ref>         flake ref (default: .)
  --nixos-target <name>     nixos target (default: nixos-ai-dev)
  -h, --help                show this help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      MODE="${2:?missing value for --mode}"
      shift 2
      ;;
    --flake-ref)
      FLAKE_REF="${2:?missing value for --flake-ref}"
      shift 2
      ;;
    --nixos-target)
      NIXOS_TARGET="${2:?missing value for --nixos-target}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

[[ "${MODE}" == "fast" || "${MODE}" == "full" ]] || {
  echo "Invalid --mode: ${MODE} (expected fast|full)" >&2
  exit 2
}

TOTAL=5
if [[ "${MODE}" == "full" ]]; then
  TOTAL=7
fi
STEP=0

section() {
  printf '\n%s%s%s\n' "${C_BOLD}${C_BLUE}" "$*" "${C_RESET}"
}

run_step() {
  local title="$1"
  shift
  STEP=$((STEP + 1))
  printf '%s[%d/%d]%s %s%s%s\n' "${C_DIM}" "${STEP}" "${TOTAL}" "${C_RESET}" "${C_BOLD}" "${title}" "${C_RESET}"
  if "$@"; then
    printf '%s[PASS]%s %s\n' "${C_GREEN}" "${C_RESET}" "${title}"
  else
    local rc=$?
    printf '%s[FAIL]%s %s (exit=%s)\n' "${C_RED}" "${C_RESET}" "${title}" "${rc}"
    exit "${rc}"
  fi
}

section "Quick Deploy Lint"
printf '%sMode:%s %s\n' "${C_DIM}" "${C_RESET}" "${MODE}"
printf '%sFlake:%s %s  %sTarget:%s %s\n' "${C_DIM}" "${C_RESET}" "${FLAKE_REF}" "${C_DIM}" "${C_RESET}" "${NIXOS_TARGET}"

run_step "Shell syntax" \
  bash -n nixos-quick-deploy.sh scripts/check-dryrun-failure-modes.sh scripts/validate-runtime-declarative.sh

run_step "Quick deploy runtime contract" \
  ./nixos-quick-deploy.sh --self-check

run_step "Declarative runtime wiring" \
  bash scripts/validate-runtime-declarative.sh

run_step "Known failure-mode checks" \
  bash scripts/check-dryrun-failure-modes.sh --flake-ref "${FLAKE_REF}" --nixos-target "${NIXOS_TARGET}"

run_step "npm security monitor smoke" \
  bash scripts/check-npm-security-monitor-smoke.sh

if [[ "${MODE}" == "full" ]]; then
  run_step "NixOS dry build" \
    nix --extra-experimental-features 'nix-command flakes' build --no-link \
      "${FLAKE_REF}#nixosConfigurations.\"${NIXOS_TARGET}\".config.system.build.toplevel"

  run_step "Preflight-only loop" \
    env PRIME_SUDO_EARLY=false KEEP_SUDO_ALIVE=false PRECHECK_SHADOW_WITH_SUDO_PROMPT=false \
      ./nixos-quick-deploy.sh --preflight-only --skip-readiness-check --skip-roadmap-verification --skip-discovery
fi

section "Result"
printf '%sAll lint checks passed.%s\n' "${C_GREEN}${C_BOLD}" "${C_RESET}"
