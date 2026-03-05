#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

mapfile -t tracked < <(git ls-files)
violations=()

for p in "${tracked[@]}"; do
  case "${p}" in
    .reports/*|reports/*)
      violations+=("${p}")
      ;;
    output.txt|file.tmp)
      violations+=("${p}")
      ;;
    *.tmp)
      # Keep tmp policy conservative: block tracked *.tmp outside docs/archive.
      if [[ "${p}" != docs/archive/* ]]; then
        violations+=("${p}")
      fi
      ;;
  esac
done

if [[ ${#violations[@]} -gt 0 ]]; then
  echo "[artifact-hygiene] FAIL: tracked generated/temp artifacts detected."
  for v in "${violations[@]:0:120}"; do
    echo "  - ${v}"
  done
  echo "[artifact-hygiene] Total violations: ${#violations[@]}"
  echo "[artifact-hygiene] Remediation: untrack artifacts and keep runtime output in .reports/ (untracked) or external stores."
  exit 1
fi

echo "[artifact-hygiene] PASS: no tracked generated/temp artifact paths detected."
