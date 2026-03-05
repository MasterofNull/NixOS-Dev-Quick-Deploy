#!/usr/bin/env bash
set -euo pipefail

# Enforce script header standards for changed scripts (or all with --all).
# Standard:
# - Shebang on line 1
# - Purpose comment/docstring within first 8 lines

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MODE="added"
BASE_REF="${BASE_REF:-}"
HEAD_REF="${HEAD_REF:-}"
WAIVER_FILE="${ROOT_DIR}/config/script-header-waivers.txt"

usage() {
  cat <<'EOF'
Usage: scripts/governance/check-script-header-standards.sh [--all] [--added] [--base <sha>] [--head <sha>]
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --all)
      MODE="all"
      shift
      ;;
    --base)
      BASE_REF="${2:-}"
      shift 2
      ;;
    --head)
      HEAD_REF="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown arg: $1" >&2
      usage
      exit 1
      ;;
  esac
done

list_changed_scripts() {
  local diff_filter="A"
  [[ "${MODE}" == "changed" ]] && diff_filter="AM"
  if [[ -n "${BASE_REF}" && -n "${HEAD_REF}" ]]; then
    git -C "${ROOT_DIR}" diff --name-only --diff-filter="${diff_filter}" "${BASE_REF}" "${HEAD_REF}" -- \
      'scripts/**/*.sh' 'scripts/**/*.py' 'scripts/ai/mcp-db-validate' 'scripts/ai/mcp-server'
    return
  fi

  local prev=""
  prev="$(git -C "${ROOT_DIR}" rev-parse --verify HEAD^ 2>/dev/null || true)"
  if [[ -n "${prev}" ]]; then
    git -C "${ROOT_DIR}" diff --name-only --diff-filter="${diff_filter}" "${prev}" HEAD -- \
      'scripts/**/*.sh' 'scripts/**/*.py' 'scripts/ai/mcp-db-validate' 'scripts/ai/mcp-server'
  else
    git -C "${ROOT_DIR}" ls-files 'scripts/**/*.sh' 'scripts/**/*.py'
  fi
}

if [[ "${MODE}" == "all" ]]; then
  mapfile -t targets < <(
    cd "${ROOT_DIR}" && {
      git ls-files 'scripts/**/*.sh' 'scripts/**/*.py'
      [[ -f scripts/ai/mcp-db-validate ]] && echo scripts/ai/mcp-db-validate
      [[ -f scripts/ai/mcp-server ]] && echo scripts/ai/mcp-server
    } | sort -u
  )
else
  mapfile -t targets < <(list_changed_scripts | sed '/^$/d' | sort -u)
fi

if [[ ${#targets[@]} -eq 0 ]]; then
  echo "[script-header] PASS: no target scripts to validate."
  exit 0
fi

declare -a WAIVERS=()
if [[ -f "${WAIVER_FILE}" ]]; then
  while IFS= read -r line; do
    line="${line%%#*}"
    line="$(printf '%s' "${line}" | sed 's/[[:space:]]*$//')"
    [[ -z "${line}" ]] && continue
    WAIVERS+=("${line}")
  done < "${WAIVER_FILE}"
fi

is_waived() {
  local rel="$1"
  local w
  for w in "${WAIVERS[@]}"; do
    [[ "${w}" == "${rel}" ]] && return 0
  done
  return 1
}

fail=0
for rel in "${targets[@]}"; do
  path="${ROOT_DIR}/${rel}"
  [[ -f "${path}" ]] || continue
  if is_waived "${rel}"; then
    continue
  fi
  mapfile -t head < <(sed -n '1,8p' "${path}")

  first="${head[0]:-}"
  if [[ "${first}" != '#!'* ]]; then
    echo "[script-header] FAIL ${rel}: missing shebang on first line"
    fail=1
    continue
  fi

  has_purpose=0
  for ln in "${head[@]:1}"; do
    s="$(printf '%s' "${ln}" | sed 's/^[[:space:]]*//')"
    if [[ "${s}" == '#'* && ${#s} -ge 10 ]]; then
      has_purpose=1
      break
    fi
    if [[ "${s}" == '"""'* || "${s}" == "'''"* ]]; then
      has_purpose=1
      break
    fi
  done

  if [[ ${has_purpose} -ne 1 ]]; then
    echo "[script-header] FAIL ${rel}: missing purpose comment/docstring in first 8 lines"
    fail=1
  fi
done

if [[ ${fail} -ne 0 ]]; then
  exit 1
fi

echo "[script-header] PASS: header standards validated (${#targets[@]} files checked)."
