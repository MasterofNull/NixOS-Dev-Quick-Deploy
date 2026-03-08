#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${ROOT:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"
SDK_DIR="${ROOT}/ai-stack/mcp-servers/hybrid-coordinator"
PYPROJECT="${SDK_DIR}/pyproject.toml"
NPM_PKG="${SDK_DIR}/package.json"

fail() { printf '[FAIL] %s\n' "$*" >&2; exit 1; }
pass() { printf '[PASS] %s\n' "$*"; }

[[ -f "$PYPROJECT" ]] || fail "missing ${PYPROJECT}"
[[ -f "$NPM_PKG" ]] || fail "missing ${NPM_PKG}"

py_ver="$(awk -F'"' '/^version[[:space:]]*=[[:space:]]*"/ {print $2; exit}' "$PYPROJECT")"
npm_ver="$(awk -F'"' '/"version"[[:space:]]*:/ {print $4; exit}' "$NPM_PKG")"

[[ -n "$py_ver" ]] || fail "could not read python SDK version"
[[ -n "$npm_ver" ]] || fail "could not read npm SDK version"

if [[ "$py_ver" != "$npm_ver" ]]; then
  fail "version mismatch: pyproject=${py_ver} package.json=${npm_ver}"
fi

if [[ "${1:-}" != "" ]]; then
  tag_ver="${1#harness-sdk-v}"
  if [[ "$tag_ver" != "$py_ver" ]]; then
    fail "tag/version mismatch: tag=${tag_ver} sdk=${py_ver}"
  fi
fi

pass "SDK version parity OK (${py_ver})"
