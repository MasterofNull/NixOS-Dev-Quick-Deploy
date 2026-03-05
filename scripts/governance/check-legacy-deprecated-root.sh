#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

mapfile -t legacy_files < <(find deprecated -type f 2>/dev/null | sort || true)

if [[ ${#legacy_files[@]} -gt 0 ]]; then
  echo "[legacy-deprecated-root] FAIL: live files detected under legacy 'deprecated/' path."
  echo "[legacy-deprecated-root] Move these to 'archive/deprecated/' and update references."
  for f in "${legacy_files[@]:0:120}"; do
    echo "  - ${f}"
  done
  echo "[legacy-deprecated-root] Total files: ${#legacy_files[@]}"
  exit 1
fi

echo "[legacy-deprecated-root] PASS: no live files under legacy 'deprecated/' path."
