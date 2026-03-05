#!/usr/bin/env bash
set -euo pipefail

# Optional hook invoked between failed pre-deploy validation loop passes.
# Keep this script safe and idempotent. It should only perform low-risk
# remediations that do not mutate runtime state outside the repository.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

echo "[preflight-remediate] Running lightweight remediation hooks..."

# Ensure npm security policy seed exists (helps first-time eval paths).
if [[ ! -f "${ROOT_DIR}/config/security/npm-threat-intel.json" ]]; then
  echo "[preflight-remediate] Missing config/security/npm-threat-intel.json; skipping (requires repo fix)."
fi

# Guard script syntax for known deploy-critical shell scripts.
for script in \
  "${ROOT_DIR}/nixos-quick-deploy.sh" \
  "${ROOT_DIR}/scripts/security/npm-security-monitor.sh" \
  "${ROOT_DIR}/scripts/testing/validate-runtime-declarative.sh"
do
  if [[ -f "${script}" ]]; then
    bash -n "${script}"
  fi
done

echo "[preflight-remediate] Completed (no destructive actions taken)."
