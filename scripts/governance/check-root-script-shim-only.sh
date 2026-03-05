#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ALLOWLIST_FILE="${ROOT_DIR}/config/root-script-shim-allowlist.txt"

if [[ ! -d "${ROOT_DIR}/scripts" ]]; then
  echo "[root-script-shim] FAIL: scripts directory missing" >&2
  exit 2
fi

allowlisted() {
  local rel="$1"
  [[ -f "${ALLOWLIST_FILE}" ]] || return 1
  grep -Ev '^\s*($|#)' "${ALLOWLIST_FILE}" | grep -Fx -- "${rel}" >/dev/null 2>&1
}

violations=0
while IFS= read -r path; do
  rel="${path#${ROOT_DIR}/}"
  first="$(sed -n '1p' "${path}" 2>/dev/null || true)"
  second="$(sed -n '2p' "${path}" 2>/dev/null || true)"

  # Non-script shebangs and explicitly allowlisted files are exempt.
  if allowlisted "${rel}"; then
    continue
  fi

  if [[ "${first}" != '#!'* ]]; then
    echo "[root-script-shim] FAIL: ${rel} missing shebang"
    violations=$((violations + 1))
    continue
  fi

  if [[ "${second}" != *"Compatibility shim"* ]]; then
    echo "[root-script-shim] FAIL: ${rel} is not a compatibility shim"
    violations=$((violations + 1))
  fi
done < <(find "${ROOT_DIR}/scripts" -maxdepth 1 -type f | sort)

if [[ ${violations} -ne 0 ]]; then
  echo "[root-script-shim] FAIL: ${violations} root script(s) violate shim-only policy."
  exit 1
fi

echo "[root-script-shim] PASS: all root scripts are compatibility shims or allowlisted."
