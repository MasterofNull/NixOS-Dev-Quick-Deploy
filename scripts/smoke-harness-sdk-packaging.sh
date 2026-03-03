#!/usr/bin/env bash
set -euo pipefail

ROOT="${ROOT:-/home/hyperd/Documents/NixOS-Dev-Quick-Deploy}"
SDK_DIR="${ROOT}/ai-stack/mcp-servers/hybrid-coordinator"
TMP_DIR="$(mktemp -d /tmp/smoke-harness-sdk-XXXXXX)"
trap 'rm -rf "$TMP_DIR"' EXIT

pass() { printf '[PASS] %s\n' "$*"; }
fail() { printf '[FAIL] %s\n' "$*" >&2; exit 1; }

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "missing command: $1"
}

need_cmd python
need_cmd npm
need_cmd node

python -m py_compile "${SDK_DIR}/harness_sdk.py" || fail "python sdk compile failed"
pass "python sdk compile"

node --check "${SDK_DIR}/harness_sdk.js" || fail "js sdk syntax failed"
pass "js sdk syntax"

# Python and npm SDK versions must stay in lockstep.
"${ROOT}/scripts/check-harness-sdk-version-parity.sh" >/dev/null || fail "SDK version parity check failed"
pass "sdk version parity"

# Generated SDK API docs drift check
"${ROOT}/scripts/generate-harness-sdk-api-docs.sh" --check >/dev/null || fail "generated sdk API docs are out of date"
pass "sdk API docs up-to-date"

# Python package build smoke (sdist + wheel)
(
  cd "${SDK_DIR}"
  python -m build --outdir "${TMP_DIR}/py-dist" >/dev/null
)
ls -1 "${TMP_DIR}/py-dist"/*.whl >/dev/null 2>&1 || fail "wheel not produced"
ls -1 "${TMP_DIR}/py-dist"/*.tar.gz >/dev/null 2>&1 || fail "sdist not produced"
pass "python package build (wheel + sdist)"

# npm packaging smoke
(
  cd "${SDK_DIR}"
  npm pack --dry-run >/dev/null
)
pass "npm pack dry run"

printf '\nSDK packaging smoke checks completed successfully.\n'
