#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPLOY_SCRIPT="${REPO_ROOT}/nixos-quick-deploy.sh"

if [[ ! -f "${DEPLOY_SCRIPT}" ]]; then
  echo "[validate-deploy-doc-flags] ERROR: missing deploy script: ${DEPLOY_SCRIPT}" >&2
  exit 2
fi

# User-facing docs that should only reference currently supported quick-deploy flags.
DOC_FILES=(
  "${REPO_ROOT}/docs/QUICK_START.md"
  "${REPO_ROOT}/docs/TROUBLESHOOTING.md"
  "${REPO_ROOT}/docs/agent-guides/10-NIXOS-CONFIG.md"
  "${REPO_ROOT}/docs/agent-guides/12-DEBUGGING.md"
  "${REPO_ROOT}/docs/development/DEPLOYMENT.md"
  "${REPO_ROOT}/docs/development/KNOWN_ISSUES_TROUBLESHOOTING.md"
  "${REPO_ROOT}/docs/development/SECURITY-SETUP.md"
)

tmpdir="$(mktemp -d)"
trap 'rm -rf "${tmpdir}"' EXIT

awk '/^Usage:/{p=1} p && /^  --/{print $1}' "${DEPLOY_SCRIPT}" | sort -u > "${tmpdir}/supported-flags.txt"
# Keep standard short/long help aliases valid for docs.
printf '%s\n' "-h" "--help" >> "${tmpdir}/supported-flags.txt"
sort -u -o "${tmpdir}/supported-flags.txt" "${tmpdir}/supported-flags.txt"

invalid_count=0

for doc in "${DOC_FILES[@]}"; do
  [[ -f "${doc}" ]] || continue
  while IFS= read -r match; do
    lineno="${match%%:*}"
    line="${match#*:}"
    while IFS= read -r flag; do
      [[ -z "${flag}" ]] && continue
      if ! grep -Fxq -- "${flag}" "${tmpdir}/supported-flags.txt"; then
        if (( invalid_count == 0 )); then
          echo "[validate-deploy-doc-flags] Unsupported nixos-quick-deploy flags found:"
        fi
        printf '  %s:%s: %s\n' "${doc}" "${lineno}" "${flag}"
        invalid_count=$((invalid_count + 1))
      fi
    done < <(printf '%s\n' "${line}" | grep -oE -- '--[a-z0-9][a-z0-9-]*' || true)
  done < <(rg -n "nixos-quick-deploy\.sh" "${doc}" | sed 's/^\([^:]*\):\([0-9]\+\):/\2:/')
done

if (( invalid_count > 0 )); then
  echo "[validate-deploy-doc-flags] FAIL: ${invalid_count} unsupported flag reference(s)." >&2
  exit 1
fi

echo "[validate-deploy-doc-flags] PASS: deploy docs only reference supported quick-deploy flags."
