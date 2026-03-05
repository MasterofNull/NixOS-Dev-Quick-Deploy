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

canonical_script_target() {
  local base="$1"
  local stem ext kebab
  stem="${base%.*}"
  ext="${base##*.}"
  kebab="${stem//_/-}.${ext}"

  local candidate=""
  candidate="$(find scripts -mindepth 2 -type f -name "${base}" | sort | head -n1 || true)"
  if [[ -z "${candidate}" && "${base}" != "${kebab}" ]]; then
    candidate="$(find scripts -mindepth 2 -type f -name "${kebab}" | sort | head -n1 || true)"
  fi
  printf '%s' "${candidate}"
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
  canonical="$(canonical_script_target "${base}")"
  if [[ -n "${canonical}" ]]; then
    target="${canonical}"
    notes="migrated to canonical path; keep root shim until final root cleanup"
  else
    target="archive/deprecated/scripts/${base}"
    notes="move with path rewrite + runtime validation"
  fi
  echo "${f},script,legacy-script-root,${refs},${target},${notes}" >> "${OUT}"
done < <(find scripts -maxdepth 1 -type f | sort)

echo "inventory_written=${OUT}"
