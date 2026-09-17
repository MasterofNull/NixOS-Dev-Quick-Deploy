#!/usr/bin/env bash
set -euo pipefail

# pre-commit wrapper for pre-archive-scan.sh.
# Only staged deletions should be blocked; ordinary modifications are ignored.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${REPO_ROOT}"

deleted_files=()
while IFS= read -r f; do
  [[ -n "$f" ]] && deleted_files+=("$f")
done < <(git diff --cached --name-only --diff-filter=D)

if [[ ${#deleted_files[@]} -eq 0 ]]; then
  exit 0
fi

status=0
for f in "${deleted_files[@]}"; do
  if ! "${SCRIPT_DIR}/pre-archive-scan.sh" --staged-deletion "$f"; then
    status=1
  fi
done

exit "$status"
