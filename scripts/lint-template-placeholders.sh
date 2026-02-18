#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
BASELINE_FILE="${PROJECT_ROOT}/config/template-placeholder-baseline.tsv"

if [[ ! -f "$BASELINE_FILE" ]]; then
  echo "Baseline file missing: $BASELINE_FILE" >&2
  exit 1
fi

declare -A baseline_counts=()
declare -A current_counts=()

list_placeholder_template_paths() {
  if command -v rg >/dev/null 2>&1; then
    rg -n "@[A-Z0-9_]+@" "${PROJECT_ROOT}/templates" -S | awk -F: '{print $1}' || true
    return
  fi

  grep -RInE "@[A-Z0-9_]+@" "${PROJECT_ROOT}/templates" 2>/dev/null | awk -F: '{print $1}' || true
}

while IFS=$'\t' read -r count path; do
  [[ -n "${count:-}" && -n "${path:-}" ]] || continue
  [[ "$count" =~ ^[0-9]+$ ]] || continue
  baseline_counts["$path"]="$count"
done < <(grep -vE '^\s*#|^\s*$' "$BASELINE_FILE")

while IFS= read -r line; do
  count="${line%% *}"
  path="${line#* }"
  [[ -n "${count:-}" && -n "${path:-}" ]] || continue
  current_counts["$path"]="$count"
done < <(
  list_placeholder_template_paths | \
    sed "s#^${PROJECT_ROOT}/##" | sort | uniq -c | awk '{print $1 " " $2}'
)

status=0

for path in "${!current_counts[@]}"; do
  current="${current_counts[$path]}"
  baseline="${baseline_counts[$path]:-}"
  if [[ -z "$baseline" ]]; then
    echo "New placeholder-bearing template not in baseline: $path (count=$current)" >&2
    status=1
    continue
  fi
  if (( current > baseline )); then
    echo "Placeholder count increased for $path: baseline=$baseline current=$current" >&2
    status=1
  fi
done

if (( status != 0 )); then
  echo "Template placeholder lint failed. If intentional, update $BASELINE_FILE." >&2
  exit $status
fi

echo "Template placeholder lint passed."
