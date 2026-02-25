#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPLOY_SCRIPT="${ROOT_DIR}/nixos-quick-deploy.sh"

if [[ ! -f "${DEPLOY_SCRIPT}" ]]; then
  echo "[audit] ERROR: missing deploy script: ${DEPLOY_SCRIPT}" >&2
  exit 2
fi

tmpdir="$(mktemp -d)"
trap 'rm -rf "${tmpdir}"' EXIT

echo "[audit] Scanning deploy feature toggles and option parity..."

# 1) Help/usage flags must match case parser flags.
awk '/^Usage:/{p=1} p && /^  --/{print $1}' "${DEPLOY_SCRIPT}" | sort -u > "${tmpdir}/usage_flags.txt"
awk '/while \[\[ \$# -gt 0 \]\]/{p=1} p && /^[[:space:]]+--[a-z0-9-]+\)/{flag=$1; gsub(/[()]/,"",flag); print flag}' "${DEPLOY_SCRIPT}" | sort -u > "${tmpdir}/case_flags.txt"

echo "[audit] Flag parity (usage vs parser)"
usage_only="$(comm -23 "${tmpdir}/usage_flags.txt" "${tmpdir}/case_flags.txt" || true)"
case_only="$(comm -13 "${tmpdir}/usage_flags.txt" "${tmpdir}/case_flags.txt" || true)"
if [[ -n "${usage_only}" ]]; then
  echo "  - Declared in usage only:"
  echo "${usage_only}" | sed 's/^/    /'
else
  echo "  - No usage-only flags."
fi
if [[ -n "${case_only}" ]]; then
  echo "  - Parsed in case only:"
  echo "${case_only}" | sed 's/^/    /'
else
  echo "  - No case-only flags."
fi

# 2) Detect intentionally suppressed runtime paths.
echo "[audit] Intentional skip/suppression paths in deploy workflow"
rg -n "Skipping deprecated|Skipping imperative runtime orchestration|--skip-|RUN_.*=false|SKIP_.*=true" "${DEPLOY_SCRIPT}" \
  | sed 's/^/  /'

# 3) Find hard-force patterns in host/modules that override toggles.
echo "[audit] Hard-forced module settings (mkForce)"
rg -n "mkForce (true|false)" "${ROOT_DIR}/nix/hosts" "${ROOT_DIR}/nix/modules" -g'*.nix' \
  | sed 's/^/  /'

# 4) Docs drift: references to retired flags from legacy workflow.
legacy_flag_re="nixos-quick-deploy\\.sh.*--(with-ai-stack|dry-run|reset-state|rollback|version|list-phases|start-from-phase|run-phase|system-only|home-only|skip-phase|debug|quiet|verbose)"

echo "[audit] Active docs references to non-existent deploy flags"
rg -n -g '*.md' -g '!archive/**' -g '!**/archive/**' -- "${legacy_flag_re}" \
  "${ROOT_DIR}/docs" \
  | sed 's/^/  /' || true

echo "[audit] Archive docs references (informational)"
rg -n -g '**/archive/**/*.md' -- "${legacy_flag_re}" \
  "${ROOT_DIR}/docs" \
  | sed 's/^/  /' || true

echo "[audit] Done."
