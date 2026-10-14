#!/usr/bin/env bash
# tier0.d/check-gitleaks-ci-parity.sh — run the exact CI secret-detection
# command (security.yml "Run Gitleaks") locally so tier0 cannot pass what CI blocks.
set -euo pipefail
REPO_ROOT="${GITLEAKS_PARITY_ROOT:-$(git rev-parse --show-toplevel)}"
cd "${REPO_ROOT}"

if ! command -v gitleaks >/dev/null 2>&1; then
  echo "[tier0.d/check-gitleaks-ci-parity] WARN: gitleaks not on PATH - CI parity not verified (reach it via aq-tool gitleaks)"
  exit 0
fi

if out="$(gitleaks detect --no-banner --redact --config .gitleaks.toml --source . --no-git --exit-code 1 2>&1)"; then
  echo "[tier0.d/check-gitleaks-ci-parity] PASS: no gitleaks findings (CI-equivalent scan)"
  exit 0
fi
printf '%s\n' "${out}" | tail -40 >&2
echo "[tier0.d/check-gitleaks-ci-parity] FAIL: gitleaks findings; CI Secret Detection would block. Fix the value or allowlist in .gitleaks.toml" >&2
exit 1
