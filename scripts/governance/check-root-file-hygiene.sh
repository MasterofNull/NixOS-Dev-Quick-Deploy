#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

ALLOWLIST_FILE="${1:-config/root-file-allowlist.txt}"

if [[ ! -f "${ALLOWLIST_FILE}" ]]; then
  echo "[root-hygiene] FAIL: missing allowlist file: ${ALLOWLIST_FILE}" >&2
  exit 2
fi

tmp_actual="$(mktemp)"
tmp_allowed="$(mktemp)"
trap 'rm -f "${tmp_actual}" "${tmp_allowed}"' EXIT

git ls-files | awk -F/ 'NF==1 {print}' | while IFS= read -r f; do
  if [[ -e "${f}" ]]; then
    printf '%s\n' "${f}"
  fi
done | sort -u > "${tmp_actual}"

grep -Ev '^\s*(#|$)' "${ALLOWLIST_FILE}" | sed 's/[[:space:]]*$//' | sort -u > "${tmp_allowed}"

unexpected="$(comm -23 "${tmp_actual}" "${tmp_allowed}" || true)"
missing="$(comm -13 "${tmp_actual}" "${tmp_allowed}" || true)"

if [[ -n "${unexpected}" || -n "${missing}" ]]; then
  echo "[root-hygiene] FAIL: root tracked file set drift detected."
  if [[ -n "${unexpected}" ]]; then
    echo "[root-hygiene] Unexpected tracked root files:"
    while IFS= read -r line; do [[ -n "${line}" ]] && echo "  - ${line}"; done <<< "${unexpected}"
  fi
  if [[ -n "${missing}" ]]; then
    echo "[root-hygiene] Allowlisted but missing root files:"
    while IFS= read -r line; do [[ -n "${line}" ]] && echo "  - ${line}"; done <<< "${missing}"
  fi
  echo "[root-hygiene] Remediation: update ${ALLOWLIST_FILE} only when root-file changes are intentional."
  exit 1
fi

count="$(wc -l < "${tmp_actual}" | tr -d '[:space:]')"
echo "[root-hygiene] PASS: tracked root files match allowlist (${count} files)."
