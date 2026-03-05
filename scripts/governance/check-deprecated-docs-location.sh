#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

if [[ -d "archive/deprecated/docs" ]]; then
  mapfile -t files < <(find archive/deprecated/docs -type f | sort)
  if [[ ${#files[@]} -gt 0 ]]; then
    echo "[deprecated-docs-location] FAIL: deprecated docs found in non-canonical path:"
    for f in "${files[@]:0:120}"; do
      echo "  - ${f}"
    done
    echo "[deprecated-docs-location] Canonical location: docs/archive/deprecated/"
    exit 1
  fi
fi

echo "[deprecated-docs-location] PASS: deprecated docs located canonically."
