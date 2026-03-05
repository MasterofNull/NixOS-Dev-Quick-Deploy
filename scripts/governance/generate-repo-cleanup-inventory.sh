#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT="${1:-${ROOT_DIR}/docs/operations/REPO-CLEANUP-INVENTORY.csv}"

cd "${ROOT_DIR}"
mkdir -p "$(dirname "${OUT}")"

echo 'path,type,scope,reference_count,suggested_target,notes' > "${OUT}"

count_refs() {
  local p="$1"
  rg -n --fixed-strings "$p" --glob '!archive/**' --glob '!docs/archive/**' --glob '!.git/**' . \
    | grep -v -F "${p}:" \
    | wc -l \
    | tr -d ' '
}

# docs root files
while IFS= read -r f; do
  refs="$(count_refs "$f")"
  base="$(basename "$f")"
  target="docs/archive/legacy-docs/${base}"
  echo "${f},doc,legacy-doc-root,${refs},${target},move after link/callsite audit" >> "${OUT}"
done < <(find docs -maxdepth 1 -type f -name '*.md' | sort)

# scripts root files
while IFS= read -r f; do
  refs="$(count_refs "$f")"
  base="$(basename "$f")"
  target="scripts/deprecated/${base}"
  echo "${f},script,legacy-script-root,${refs},${target},move with path rewrite + runtime validation" >> "${OUT}"
done < <(find scripts -maxdepth 1 -type f | sort)

echo "inventory_written=${OUT}"
