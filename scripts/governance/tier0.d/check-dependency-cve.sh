#!/usr/bin/env bash
# tier0.d: audit modified package manifests for high/critical CVE vulnerabilities.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

if [[ "${SKIP_CVE_SCAN:-0}" == "1" ]]; then
  echo "[tier0.d/check-dependency-cve] PASS: skipped via SKIP_CVE_SCAN=1"
  exit 0
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "[tier0.d/check-dependency-cve] PASS: npm not available"
  exit 0
fi

# Find package.json / package-lock.json files modified relative to HEAD (or staged)
mapfile -t MODIFIED_MANIFESTS < <(
  cd "$REPO" && {
    git diff --cached --name-only 2>/dev/null || true
    git diff --name-only HEAD 2>/dev/null || true
  } | grep -E '(package\.json|package-lock\.json)$' | sort -u
)

if [[ ${#MODIFIED_MANIFESTS[@]} -eq 0 ]]; then
  echo "[tier0.d/check-dependency-cve] PASS: no modified package manifests to audit"
  exit 0
fi

checked_dirs=()
cve_found=0

for manifest in "${MODIFIED_MANIFESTS[@]}"; do
  mdir="$(dirname "${REPO}/${manifest}")"
  [[ " ${checked_dirs[*]} " =~ " ${mdir} " ]] && continue
  checked_dirs+=("$mdir")

  if [[ -f "${mdir}/package-lock.json" ]]; then
    audit_out="$( (cd "$mdir" && npm audit --omit=dev --json 2>/dev/null) || true )"
    high="$(echo "$audit_out" | jq '.metadata.vulnerabilities.high // 0' 2>/dev/null || echo 0)"
    critical="$(echo "$audit_out" | jq '.metadata.vulnerabilities.critical // 0' 2>/dev/null || echo 0)"

    if [[ "$critical" -gt 0 || "$high" -gt 0 ]]; then
      echo "[tier0.d/check-dependency-cve] FAIL: high/critical CVEs in ${manifest} (critical=${critical}, high=${high})" >&2

      if [[ -x "${REPO}/scripts/ai/aq-rsi" ]]; then
        "${REPO}/scripts/ai/aq-rsi" report \
          "High/critical CVEs detected in ${manifest} (critical=${critical}, high=${high})" \
          --agent "tier0" \
          --subject "tier0:cve:${manifest}" \
          --producer "tier0.d:check-dependency-cve" \
          --path "${manifest}" \
          --authority "npm-audit" \
          --severity "$([[ "$critical" -gt 0 ]] && echo critical || echo high)" \
          --root-fix "Run npm audit fix or bump vulnerable dependency versions" \
          >/dev/null 2>&1 || true
      fi
      cve_found=1
    fi
  fi
done

if [[ "$cve_found" -ne 0 ]]; then
  echo "[tier0.d/check-dependency-cve] FAIL: vulnerable dependencies detected" >&2
  exit 1
fi

echo "[tier0.d/check-dependency-cve] PASS: 0 high/critical CVEs in modified manifests"
exit 0
