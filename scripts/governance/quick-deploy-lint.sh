#!/usr/bin/env bash
# Run fast/full declarative pre-deploy lint and governance checks.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

MODE="fast"
FLAKE_REF="."
NIXOS_TARGET="nixos-ai-dev"
SCRIPT_HEADER_SCOPE="all"
SCRIPT_HEADER_BASE_REF=""
SCRIPT_HEADER_HEAD_REF=""

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
Usage: scripts/governance/quick-deploy-lint.sh [options]

Options:
  --mode <fast|full>        fast: static + contract checks (default)
                            full: includes dry builds and preflight-only loop
  --flake-ref <ref>         flake ref (default: .)
  --nixos-target <name>     nixos target (default: nixos-ai-dev)
  --script-header-scope <all|changed>
                            scope script header check to all scripts or only changed refs
  --base-ref <sha>          base ref for changed-scope script header checks
  --head-ref <sha>          head ref for changed-scope script header checks
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
    --script-header-scope)
      SCRIPT_HEADER_SCOPE="${2:?missing value for --script-header-scope}"
      shift 2
      ;;
    --base-ref)
      SCRIPT_HEADER_BASE_REF="${2:?missing value for --base-ref}"
      shift 2
      ;;
    --head-ref)
      SCRIPT_HEADER_HEAD_REF="${2:?missing value for --head-ref}"
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
[[ "${SCRIPT_HEADER_SCOPE}" == "all" || "${SCRIPT_HEADER_SCOPE}" == "changed" ]] || {
  echo "Invalid --script-header-scope: ${SCRIPT_HEADER_SCOPE} (expected all|changed)" >&2
  exit 2
}

TOTAL=22
if [[ "${MODE}" == "full" ]]; then
  TOTAL=24
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
  bash -n nixos-quick-deploy.sh scripts/testing/check-dryrun-failure-modes.sh scripts/testing/validate-runtime-declarative.sh

run_step "Quick deploy runtime contract" \
  ./nixos-quick-deploy.sh --self-check

run_step "Declarative runtime wiring" \
  bash scripts/testing/validate-runtime-declarative.sh

run_step "Known failure-mode checks" \
  bash scripts/testing/check-dryrun-failure-modes.sh --flake-ref "${FLAKE_REF}" --nixos-target "${NIXOS_TARGET}"

run_step "Repo structure policy" \
  bash scripts/governance/repo-structure-lint.sh --all

run_step "Repo allowlist integrity" \
  bash scripts/governance/check-repo-allowlist-integrity.sh

run_step "Root file hygiene" \
  bash scripts/governance/check-root-file-hygiene.sh

run_step "Script shim consistency" \
  bash scripts/governance/check-script-shim-consistency.sh

run_step "Root script shim-only policy" \
  bash scripts/governance/check-root-script-shim-only.sh

run_step "Active doc link integrity" \
  bash scripts/governance/check-doc-links.sh --active

run_step "Doc metadata standards" \
  bash scripts/governance/check-doc-metadata-standards.sh

run_step "Doc script-path migration" \
  bash scripts/governance/check-doc-script-path-migration.sh

run_step "Python tooling policy" \
  bash scripts/governance/check-python-tooling-policy.sh

script_header_cmd=(bash scripts/governance/check-script-header-standards.sh --all)
if [[ "${SCRIPT_HEADER_SCOPE}" == "changed" ]]; then
  script_header_cmd=(bash scripts/governance/check-script-header-standards.sh --changed)
  [[ -n "${SCRIPT_HEADER_BASE_REF}" ]] && script_header_cmd+=(--base "${SCRIPT_HEADER_BASE_REF}")
  [[ -n "${SCRIPT_HEADER_HEAD_REF}" ]] && script_header_cmd+=(--head "${SCRIPT_HEADER_HEAD_REF}")
fi

run_step "Script header standards" \
  "${script_header_cmd[@]}"

run_step "Naming/label consistency audit" \
  bash scripts/governance/check-naming-label-consistency.sh

run_step "Archive path consistency" \
  bash scripts/governance/check-archive-path-consistency.sh

run_step "Legacy deprecated-root guard" \
  bash scripts/governance/check-legacy-deprecated-root.sh

run_step "Generated artifact hygiene" \
  bash scripts/governance/check-generated-artifact-hygiene.sh

run_step "Deprecated docs location" \
  bash scripts/governance/check-deprecated-docs-location.sh

run_step "npm security monitor smoke" \
  bash scripts/testing/check-npm-security-monitor-smoke.sh

run_step "Security audit producer smoke" \
  bash scripts/testing/smoke-security-audit-producer.sh

run_step "Security audit compliance smoke" \
  bash scripts/testing/smoke-security-audit-compliance.sh

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
