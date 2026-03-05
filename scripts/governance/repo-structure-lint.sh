#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

ALLOWLIST_FILE="${REPO_STRUCTURE_ALLOWLIST_FILE:-config/repo-structure-allowlist.txt}"
MODE="all"

DOC_ALLOWED_DIRS=(
  agent-guides api archive development generated harness-first prsi sql
  operations architecture security testing roadmap
)
SCRIPT_ALLOWED_DIRS=(
  lib governance ai data deploy health security testing utils
  reliability performance observability automation
)

usage() {
  cat <<USAGE
Usage: scripts/governance/repo-structure-lint.sh [--staged|--all]

Checks repository structure policy and blocks disallowed file placements.
Legacy paths can be grandfathered via: ${ALLOWLIST_FILE}
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --staged) MODE="staged"; shift ;;
    --all) MODE="all"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ ! -f "${ALLOWLIST_FILE}" ]]; then
  echo "Missing allowlist file: ${ALLOWLIST_FILE}" >&2
  exit 2
fi

is_allowlisted() {
  local path="$1"
  grep -Fvx '' "${ALLOWLIST_FILE}" | grep -Ev '^\s*#' | grep -Fx -- "$path" >/dev/null 2>&1
}

in_array() {
  local needle="$1"; shift
  local x
  for x in "$@"; do
    [[ "$x" == "$needle" ]] && return 0
  done
  return 1
}

collect_paths() {
  if [[ "${MODE}" == "staged" ]]; then
    git diff --cached --name-status --diff-filter=ACMR | while IFS=$'\t' read -r st p1 p2; do
      case "$st" in
        R*) [[ -n "${p2:-}" ]] && printf '%s\n' "$p2" ;;
        *) [[ -n "${p1:-}" ]] && printf '%s\n' "$p1" ;;
      esac
    done
  else
    git ls-files --cached --others --exclude-standard | while IFS= read -r p; do
      [[ -e "$p" ]] && printf '%s\n' "$p"
    done
  fi
}

violations=0
while IFS= read -r path; do
  [[ -z "$path" ]] && continue

  # Rule 1: root-level markdown is disallowed unless grandfathered.
  if [[ "$path" != */* && "$path" == *.md ]]; then
    if ! is_allowlisted "$path"; then
      echo "[repo-structure] FAIL root markdown disallowed: $path"
      ((violations+=1))
    fi
    continue
  fi

  # Rule 2: root-level executable/source files disallowed unless grandfathered.
  if [[ "$path" != */* && "$path" =~ \.(sh|py|js|ts|tsx|jsx)$ ]]; then
    if ! is_allowlisted "$path"; then
      echo "[repo-structure] FAIL root code/script disallowed: $path"
      ((violations+=1))
    fi
    continue
  fi

  # Rule 3: docs files must be in approved subject dirs (no docs/*.md) unless grandfathered.
  if [[ "$path" == docs/* ]]; then
    rel="${path#docs/}"
    if [[ "$rel" != */* ]]; then
      if ! is_allowlisted "$path"; then
        echo "[repo-structure] FAIL docs root file disallowed: $path (use docs/<subject>/...)"
        ((violations+=1))
      fi
      continue
    fi
    top="${rel%%/*}"
    if ! in_array "$top" "${DOC_ALLOWED_DIRS[@]}"; then
      if ! is_allowlisted "$path"; then
        echo "[repo-structure] FAIL docs subdir not in policy: $path (top=$top)"
        ((violations+=1))
      fi
    fi
    continue
  fi

  # Rule 4: scripts files must be in approved subject dirs (no scripts/* files) unless grandfathered.
  if [[ "$path" == scripts/* ]]; then
    rel="${path#scripts/}"
    if [[ "$rel" != */* ]]; then
      if ! is_allowlisted "$path"; then
        echo "[repo-structure] FAIL scripts root file disallowed: $path (use scripts/<subject>/...)"
        ((violations+=1))
      fi
      continue
    fi
    top="${rel%%/*}"
    if ! in_array "$top" "${SCRIPT_ALLOWED_DIRS[@]}"; then
      if ! is_allowlisted "$path"; then
        echo "[repo-structure] FAIL scripts subdir not in policy: $path (top=$top)"
        ((violations+=1))
      fi
    fi
    continue
  fi

done < <(collect_paths)

if [[ "$violations" -ne 0 ]]; then
  echo "[repo-structure] FAIL: ${violations} policy violation(s)."
  exit 1
fi

echo "[repo-structure] PASS: structure policy checks passed (${MODE})."
